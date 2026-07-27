"""Replay a Reference Ride's power through the Rider Model over the Climb.

Hard-won rules, each the answer to a real failure mode (see CONTEXT.md,
Replay Validation):

- Climb only: recorded power cannot distinguish braking from coasting, so
  descents and stop-and-go flats always simulate too fast.
- GPS-anchored window: odometers drift between recordings (city routing
  varies ride to ride), so the climb boundaries are located per ride by
  proximity to the canonical boundary coordinates, never by raw distance.
- Position-indexed power: feeding power by time diverges — once the sim runs
  slow, recovery watts land on the wrong terrain and the error cascades.
- Windowed power (50 m ahead): point-sampling stalls on momentary coasts the
  real rider rolled through with momentum.
- Moving time vs moving records: mid-climb stops (junctions, photos) are
  rider choices the model cannot predict; both sides of the comparison
  exclude them.
"""
from __future__ import annotations

import bisect

from olias.physics import RiderModel
from olias.profile import RouteProfile
from olias.reference import ReferenceRide

POWER_WINDOW_M = 50.0
REPLAY_DT_S = 1.0
ENTRY_SPEED_MS = 3.0


def _odometer_nearest(ride: ReferenceRide, latlon: tuple[float, float], not_before: float = 0.0) -> float:
    """Ride odometer reading at the point geographically nearest to latlon."""
    tlat, tlon = latlon
    best_d, best_err = 0.0, float("inf")
    for distance, _power, lat, lon in ride.moving_records:
        if distance < not_before:
            continue
        # equirectangular; cos(36.7°) ≈ 0.8 corrects longitude shrink at this latitude
        err = (lat - tlat) ** 2 + ((lon - tlon) * 0.8) ** 2
        if err < best_err:
            best_err, best_d = err, distance
    return best_d


def _climb_window(ride: ReferenceRide, profile: RouteProfile) -> tuple[float, float]:
    start = _odometer_nearest(ride, profile.latlon_at(profile.climb.start_m))
    end = _odometer_nearest(ride, profile.latlon_at(profile.climb.end_m), not_before=start)
    return start, end


def real_climb_moving_time_s(ride: ReferenceRide, profile: RouteProfile) -> float:
    """Seconds of moving records inside the ride's own GPS-anchored climb window."""
    start, end = _climb_window(ride, profile)
    distances = [m[0] for m in ride.moving_records]
    return float(bisect.bisect_left(distances, end) - bisect.bisect_left(distances, start))


def climb_replay_time_s(model: RiderModel, ride: ReferenceRide, profile: RouteProfile) -> float:
    """Simulated moving time over the Climb using the ride's recorded power."""
    climb = profile.climb
    start, end = _climb_window(ride, profile)
    scale = (end - start) / (climb.end_m - climb.start_m)
    distances = [m[0] for m in ride.moving_records]
    powers = [m[1] for m in ride.moving_records]

    def power_near(position_m: float) -> float:
        ride_d = start + (position_m - climb.start_m) * scale
        i = bisect.bisect_left(distances, ride_d)
        j = max(bisect.bisect_left(distances, ride_d + POWER_WINDOW_M * scale), i + 1)
        window = powers[min(i, len(powers) - 1):min(j, len(powers))] or [powers[-1]]
        return sum(window) / len(window)

    v, position_m, t = ENTRY_SPEED_MS, climb.start_m, 0
    limit = int(ride.total_time_s * 2)
    while position_m < climb.end_m and t < limit:
        v = model.step(
            speed_ms=v,
            power_w=power_near(position_m),
            grade_pct=profile.grade_at(position_m),
            dt_s=REPLAY_DT_S,
        )
        position_m += v * REPLAY_DT_S
        t += 1
    return float(t)
