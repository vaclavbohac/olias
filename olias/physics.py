"""Rider Model: computes speed from measured power and grade (see ADR-0001)."""
from __future__ import annotations

import math
from dataclasses import dataclass

G = 9.81
# below this speed, propulsive force is computed as if moving at it,
# so P/v stays finite when starting from a standstill
MIN_PROPULSION_SPEED_MS = 0.5


@dataclass(frozen=True)
class RiderModel:
    mass_kg: float
    crr: float = 0.005
    cda_m2: float = 0.32
    air_density: float = 1.225

    def step(self, speed_ms: float, power_w: float, grade_pct: float, dt_s: float) -> float:
        theta = math.atan(grade_pct / 100)
        propulsion = power_w / max(speed_ms, MIN_PROPULSION_SPEED_MS)
        gravity = self.mass_kg * G * math.sin(theta)
        rolling = self.mass_kg * G * self.crr * math.cos(theta)
        aero = 0.5 * self.air_density * self.cda_m2 * speed_ms**2
        accel = (propulsion - gravity - rolling - aero) / self.mass_kg
        return max(0.0, speed_ms + accel * dt_s)
