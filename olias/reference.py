"""Reference Ride: a recorded real ride, indexed by riding time and position.

Records are 1 Hz and exist only while the timer runs, so a record's index IS its
riding-time second — wall-clock gaps (auto-pauses) never count. Missing power
samples read as 0 W (coasting rule, see CONTEXT.md).
"""

from __future__ import annotations

import bisect
from pathlib import Path

import fitdecode


class ReferenceRide:
    SEMICIRCLE_TO_DEG = 180 / 2**31

    def __init__(
        self,
        distances_m: list[float],
        powers_w: list[float],
        moving: list[tuple[float, float, float, float]],
    ):
        self._distances_m = distances_m
        self._powers_w = powers_w
        # moving records only (odometer advanced): (distance, power, lat, lon)
        self._moving = moving

    @classmethod
    def load(cls, fit_path: Path) -> ReferenceRide:
        distances, powers, moving = [], [], []
        last_distance = 0.0
        for frame in fitdecode.FitReader(fit_path):
            if not (isinstance(frame, fitdecode.FitDataMessage) and frame.name == "record"):
                continue
            fields = {f.name: f.value for f in frame.fields}
            distance = fields.get("distance")
            power = fields.get("power")
            power_w = float(power) if power is not None else 0.0
            if distance is not None:
                if distance > last_distance and fields.get("position_lat") is not None:
                    moving.append(
                        (
                            distance,
                            power_w,
                            fields["position_lat"] * cls.SEMICIRCLE_TO_DEG,
                            fields["position_long"] * cls.SEMICIRCLE_TO_DEG,
                        )
                    )
                last_distance = distance
            distances.append(last_distance)
            powers.append(power_w)
        return cls(distances_m=distances, powers_w=powers, moving=moving)

    @property
    def moving_records(self) -> list[tuple[float, float, float, float]]:
        """1 Hz records where the odometer advanced: (distance_m, power_w, lat, lon)."""
        return self._moving

    @property
    def total_time_s(self) -> float:
        return float(len(self._powers_w))

    @property
    def total_distance_m(self) -> float:
        return self._distances_m[-1]

    def elapsed_s_at(self, distance_m: float) -> float:
        ds = self._distances_m
        if distance_m <= ds[0]:
            return 0.0
        if distance_m >= ds[-1]:
            return float(len(ds) - 1)
        i = bisect.bisect_right(ds, distance_m)
        # records at identical distance (stopped) all map to the first of them
        if ds[i] == ds[i - 1]:
            return float(i - 1)
        frac = (distance_m - ds[i - 1]) / (ds[i] - ds[i - 1])
        return (i - 1) + frac

    def power_at_second(self, t_s: float) -> float:
        i = int(t_s)
        if 0 <= i < len(self._powers_w):
            return self._powers_w[i]
        return 0.0
