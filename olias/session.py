"""Session runner: the asyncio shell around the pure SessionEngine.

Adapters are anything with the right attributes (trainer: latest_power_w,
connected, set_grade; heart: latest_bpm) — the real BLE classes and test
fakes both qualify.
"""
from __future__ import annotations

import asyncio
import time
from typing import Callable, Protocol

from olias.engine import EngineState, SessionEngine, Snapshot

TICK_INTERVAL_S = 0.25  # 4 Hz


class Trainer(Protocol):
    latest_power_w: float | None
    latest_cadence_rpm: float | None
    connected: bool

    def set_grade(self, grade_pct: float) -> None: ...


class HeartRate(Protocol):
    latest_bpm: int | None


class SessionRunner:
    def __init__(
        self,
        engine: SessionEngine,
        trainer: Trainer,
        heart: HeartRate,
        on_snapshot: Callable[[Snapshot, float], None],
        tick_interval_s: float = TICK_INTERVAL_S,
        engine_dt_s: float | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self._engine = engine
        self._trainer = trainer
        self._heart = heart
        self._on_snapshot = on_snapshot
        self._tick_interval_s = tick_interval_s
        # simulated seconds per tick; defaults to real time. Tests decouple the
        # two to ride the full route without sleeping.
        self._engine_dt_s = engine_dt_s if engine_dt_s is not None else tick_interval_s
        self._clock = clock
        self.stop = asyncio.Event()

    def pause_toggle(self) -> None:
        if self._engine.state is EngineState.PAUSED:
            self._engine.resume()
        else:
            self._engine.pause()

    async def run(self) -> None:
        while not self.stop.is_set():
            power = self._trainer.latest_power_w
            snapshot = self._engine.tick(
                power_w=power if power is not None else 0.0,  # disconnected -> coast
                heart_rate_bpm=self._heart.latest_bpm,
                cadence_rpm=getattr(self._trainer, "latest_cadence_rpm", None),
                dt_s=self._engine_dt_s,
            )
            if snapshot.trainer_grade_pct is not None:
                self._trainer.set_grade(snapshot.trainer_grade_pct)
            self._on_snapshot(snapshot, self._clock())
            if snapshot.state is EngineState.FINISHED:
                break
            if self._tick_interval_s > 0:
                await asyncio.sleep(self._tick_interval_s)
