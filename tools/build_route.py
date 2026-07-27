"""Synthesize the canonical Olias route profile from the reference ride.

Reads the reference recording (olias-ride-001.fit, the best-calibrated ride),
resamples it onto a uniform distance grid, smooths altitude, and derives grade
from the smoothed altitude — recorded per-second grade has spikes (up to ±22%
in some rides) that must not reach the trainer.

Run:  uv run --with fitdecode tools/build_route.py
Output: resources/olias-route.csv  (distance_m, lat, lon, altitude_m, grade_pct)
"""

import bisect
import csv
from pathlib import Path

import fitdecode

REF = Path(__file__).parent.parent / "resources" / "olias-ride-001.fit"
OUT = Path(__file__).parent.parent / "resources" / "olias-route.csv"

GRID_STEP = 5.0  # m between output points
ALT_SMOOTH_WIN = 11  # points (55 m) moving average over altitude
GRADE_SPAN = 3  # grade from altitude difference over +-3 points (30 m)
GRADE_CLAMP = 18.0  # % safety clamp, generous vs the route's real ~12% max

SEMI_TO_DEG = 180 / 2**31


def load_reference(path):
    """Monotonic (distance, altitude, lat, lon) samples from the FIT records."""
    samples = []
    last_d = -1.0
    for frame in fitdecode.FitReader(path):
        if not (isinstance(frame, fitdecode.FitDataMessage) and frame.name == "record"):
            continue
        r = {f.name: f.value for f in frame.fields}
        d, alt = r.get("distance"), r.get("altitude")
        lat, lon = r.get("position_lat"), r.get("position_long")
        if d is None or alt is None or lat is None or lon is None:
            continue
        if d <= last_d:  # stationary or GPS hiccup: keep distances strictly increasing
            continue
        last_d = d
        samples.append((d, alt, lat * SEMI_TO_DEG, lon * SEMI_TO_DEG))
    return samples


def interp_column(samples, col, d):
    ds = [s[0] for s in samples]
    i = bisect.bisect_left(ds, d)
    if i == 0:
        return samples[0][col]
    if i >= len(samples):
        return samples[-1][col]
    (d0, *_), (d1, *_) = samples[i - 1], samples[i]
    v0, v1 = samples[i - 1][col], samples[i][col]
    return v0 + (v1 - v0) * (d - d0) / (d1 - d0)


def moving_average(values, window):
    half = window // 2
    out = []
    for i in range(len(values)):
        lo, hi = max(0, i - half), min(len(values), i + half + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def main():
    samples = load_reference(REF)
    total = samples[-1][0]
    grid = [i * GRID_STEP for i in range(int(total / GRID_STEP) + 1)]

    alt = [interp_column(samples, 1, d) for d in grid]
    lat = [interp_column(samples, 2, d) for d in grid]
    lon = [interp_column(samples, 3, d) for d in grid]

    alt = moving_average(alt, ALT_SMOOTH_WIN)

    grade = []
    for i in range(len(grid)):
        lo, hi = max(0, i - GRADE_SPAN), min(len(grid) - 1, i + GRADE_SPAN)
        g = (alt[hi] - alt[lo]) / ((hi - lo) * GRID_STEP) * 100
        grade.append(max(-GRADE_CLAMP, min(GRADE_CLAMP, g)))

    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["distance_m", "lat", "lon", "altitude_m", "grade_pct"])
        for row in zip(grid, lat, lon, alt, grade, strict=True):
            w.writerow(
                [
                    f"{row[0]:.0f}",
                    f"{row[1]:.6f}",
                    f"{row[2]:.6f}",
                    f"{row[3]:.1f}",
                    f"{row[4]:.2f}",
                ]
            )

    ascent = sum(max(0.0, b - a) for a, b in zip(alt, alt[1:], strict=False))
    print(f"{OUT.name}: {len(grid)} points, {total / 1000:.2f} km")
    print(f"altitude {min(alt):.1f}..{max(alt):.1f} m, ascent {ascent:.0f} m")
    print(f"grade {min(grade):.1f}..{max(grade):.1f} %")


if __name__ == "__main__":
    main()
