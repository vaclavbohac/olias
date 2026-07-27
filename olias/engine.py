"""Session engine: the fixed-tick loop that advances a ride (pure, no I/O)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from olias.physics import RiderModel
from olias.profile import RouteProfile
from olias.reference import ReferenceRide


class EngineState(Enum):
    ARMED = auto()
    RIDING = auto()
    PAUSED = auto()
    FINISHED = auto()


@dataclass(frozen=True)
class Snapshot:
    state: EngineState
    elapsed_s: float
    position_m: float
    speed_ms: float
    grade_pct: float
    remaining_ascent_m: float
    power_w: float
    heart_rate_bpm: int | None
    climb_delta_s: float | None
    trainer_grade_pct: float | None


class SessionEngine:
    def __init__(
        self,
        profile: RouteProfile,
        rider_model: RiderModel,
        reference: ReferenceRide,
        start_power_w: float = 20.0,
        grade_epsilon_pct: float = 0.1,
    ):
        self._profile = profile
        self._model = rider_model
        self._reference = reference
        self._start_power_w = start_power_w
        self._grade_epsilon_pct = grade_epsilon_pct
        self._state = EngineState.ARMED
        self._elapsed_s = 0.0
        self._position_m = 0.0
        self._speed_ms = 0.0
        self._commanded_grade_pct: float | None = None
        self._climb_started_at_s: float | None = None

    def tick(self, power_w: float, heart_rate_bpm: int | None, dt_s: float) -> Snapshot:
        if self._state is EngineState.ARMED and power_w >= self._start_power_w:
            self._state = EngineState.RIDING
        if self._state is EngineState.RIDING:
            self._advance(power_w, dt_s)
        return self._snapshot(power_w, heart_rate_bpm)

    def _advance(self, power_w: float, dt_s: float) -> None:
        self._elapsed_s += dt_s
        self._speed_ms = self._model.step(
            speed_ms=self._speed_ms,
            power_w=power_w,
            grade_pct=self._profile.grade_at(self._position_m),
            dt_s=dt_s,
        )
        self._position_m += self._speed_ms * dt_s
        if self._climb_started_at_s is None and self._profile.on_climb(self._position_m):
            self._climb_started_at_s = self._elapsed_s
        if self._position_m >= self._profile.total_distance_m:
            self._position_m = self._profile.total_distance_m
            self._speed_ms = 0.0
            self._state = EngineState.FINISHED

    def pause(self) -> None:
        if self._state is EngineState.RIDING:
            self._state = EngineState.PAUSED

    def resume(self) -> None:
        if self._state is EngineState.PAUSED:
            self._state = EngineState.RIDING
            self._commanded_grade_pct = None  # recommand real grade on next tick

    def _grade_command(self) -> float | None:
        """Grade to send to the trainer, or None if the last command still stands."""
        if self._state is EngineState.PAUSED:
            if self._commanded_grade_pct != 0.0:
                self._commanded_grade_pct = 0.0
                return 0.0
            return None
        if self._state is not EngineState.RIDING:
            return None
        grade = self._profile.grade_at(self._position_m)
        if (
            self._commanded_grade_pct is None
            or abs(grade - self._commanded_grade_pct) >= self._grade_epsilon_pct
        ):
            self._commanded_grade_pct = grade
            return grade
        return None

    def _climb_delta_s(self) -> float | None:
        """Reference time minus rider time to reach this position, climb-start-zeroed.

        Positive: rider is ahead of the Reference Ride. Shown only on the Climb.
        """
        if self._climb_started_at_s is None or not self._profile.on_climb(self._position_m):
            return None
        climb_start = self._profile.climb.start_m
        reference_time = self._reference.elapsed_s_at(self._position_m) - self._reference.elapsed_s_at(climb_start)
        rider_time = self._elapsed_s - self._climb_started_at_s
        return reference_time - rider_time

    def _snapshot(self, power_w: float, heart_rate_bpm: int | None) -> Snapshot:
        return Snapshot(
            state=self._state,
            elapsed_s=self._elapsed_s,
            position_m=self._position_m,
            speed_ms=self._speed_ms,
            grade_pct=self._profile.grade_at(self._position_m),
            remaining_ascent_m=self._profile.remaining_ascent(self._position_m),
            power_w=power_w,
            heart_rate_bpm=heart_rate_bpm,
            climb_delta_s=self._climb_delta_s(),
            trainer_grade_pct=self._grade_command(),
        )
