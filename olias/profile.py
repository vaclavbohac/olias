"""Route Profile: the canonical distance-indexed elevation model of the route.

See CONTEXT.md for the domain terms (Route Profile, Remaining Ascent, the Climb).
"""
from __future__ import annotations

import bisect
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Segment:
    start_m: float
    end_m: float


class RouteProfile:
    def __init__(
        self,
        distances_m: list[float],
        altitudes_m: list[float],
        grades_pct: list[float],
        climb: Segment,
    ):
        self._distances_m = distances_m
        self._altitudes_m = altitudes_m
        self._grades_pct = grades_pct
        self.climb = climb
        # _ascent_after[i]: sum of positive altitude deltas from point i to the end
        self._ascent_after = [0.0] * len(altitudes_m)
        for i in range(len(altitudes_m) - 2, -1, -1):
            climb_delta = max(0.0, altitudes_m[i + 1] - altitudes_m[i])
            self._ascent_after[i] = self._ascent_after[i + 1] + climb_delta

    @classmethod
    def load(cls, csv_path: Path, climb: Segment) -> RouteProfile:
        with open(csv_path, newline="") as f:
            rows = list(csv.DictReader(f))
        return cls(
            distances_m=[float(r["distance_m"]) for r in rows],
            altitudes_m=[float(r["altitude_m"]) for r in rows],
            grades_pct=[float(r["grade_pct"]) for r in rows],
            climb=climb,
        )

    @property
    def total_distance_m(self) -> float:
        return self._distances_m[-1]

    def altitude_at(self, distance_m: float) -> float:
        return self._interpolate(self._altitudes_m, distance_m)

    def on_climb(self, distance_m: float) -> bool:
        return self.climb.start_m <= distance_m < self.climb.end_m

    def grade_at(self, distance_m: float) -> float:
        return self._interpolate(self._grades_pct, distance_m)

    def remaining_ascent(self, distance_m: float) -> float:
        ds = self._distances_m
        if distance_m <= ds[0]:
            return self._ascent_after[0]
        if distance_m >= ds[-1]:
            return 0.0
        i = bisect.bisect_right(ds, distance_m)
        partial = max(0.0, self._altitudes_m[i] - self.altitude_at(distance_m))
        return self._ascent_after[i] + partial

    def _interpolate(self, values: list[float], distance_m: float) -> float:
        ds = self._distances_m
        if distance_m <= ds[0]:
            return values[0]
        if distance_m >= ds[-1]:
            return values[-1]
        i = bisect.bisect_right(ds, distance_m)
        frac = (distance_m - ds[i - 1]) / (ds[i] - ds[i - 1])
        return values[i - 1] + (values[i] - values[i - 1]) * frac
