"""Session Recording: persist a ride as a FIT activity (ADR-0003).

Records are written at 1 Hz of riding time only; pauses become FIT timer
stop/start events, exactly like the head-unit recordings in resources/.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import Event, EventType, FileType, Manufacturer, Sport

from olias.engine import EngineState, Snapshot
from olias.profile import RouteProfile


@dataclass(frozen=True)
class _Sample:
    wall_ms: int
    position_m: float
    lat: float
    lon: float
    altitude_m: float
    grade_pct: float
    speed_ms: float
    power_w: float
    heart_rate_bpm: int | None
    cadence_rpm: float | None


class SessionRecorder:
    """Feed it every snapshot; it keeps 1 Hz samples and writes the FIT at the end."""

    SEMICIRCLE_TO_DEG = 180 / 2**31

    def __init__(self, profile: RouteProfile):
        self._profile = profile
        self._samples: list[_Sample] = []
        self._events: list[tuple[int, EventType]] = []  # (wall_ms, START/STOP)
        self._last_state: EngineState | None = None
        self._last_recorded_second: int | None = None

    @property
    def seeded_cadence(self) -> tuple[float, int]:
        """(sum, count) of nonzero cadence samples — engine restore input."""
        values = [s.cadence_rpm for s in self._samples if s.cadence_rpm]
        return sum(values), len(values)

    @classmethod
    def resume_from(cls, fit_path: Path, profile: RouteProfile) -> SessionRecorder:
        """Seed a recorder with a previous session so the final FIT is one ride."""
        import fitdecode

        recorder = cls(profile)
        for frame in fitdecode.FitReader(fit_path):
            if not (isinstance(frame, fitdecode.FitDataMessage) and frame.name == "record"):
                continue
            f = {x.name: x.value for x in frame.fields}
            if f.get("timestamp") is None or f.get("distance") is None:
                continue
            recorder._samples.append(
                _Sample(
                    wall_ms=int(f["timestamp"].timestamp() * 1000),
                    position_m=f["distance"],
                    lat=(f.get("position_lat") or 0) * cls.SEMICIRCLE_TO_DEG,
                    lon=(f.get("position_long") or 0) * cls.SEMICIRCLE_TO_DEG,
                    altitude_m=f.get("altitude") or 0.0,
                    grade_pct=f.get("grade") or 0.0,
                    speed_ms=f.get("speed") or 0.0,
                    power_w=float(f.get("power") or 0),
                    heart_rate_bpm=f.get("heart_rate"),
                    cadence_rpm=float(f["cadence"]) if f.get("cadence") is not None else None,
                )
            )
        if recorder._samples:
            # the gap between sessions becomes a proper timer stop; the
            # continuation's first RIDING snapshot adds the matching start
            recorder._events.append((recorder._samples[0].wall_ms, EventType.START))
            recorder._events.append((recorder._samples[-1].wall_ms + 1000, EventType.STOP))
            recorder._last_recorded_second = len(recorder._samples) - 1
        return recorder

    def on_snapshot(self, snapshot: Snapshot, wall_time_s: float) -> None:
        wall_ms = int(wall_time_s * 1000)
        state = snapshot.state
        if state is not self._last_state:
            if state is EngineState.RIDING:
                self._events.append((wall_ms, EventType.START))
            elif self._last_state is EngineState.RIDING:
                self._events.append((wall_ms, EventType.STOP))
            self._last_state = state

        if state is not EngineState.RIDING:
            return
        second = int(snapshot.elapsed_s)
        if second == self._last_recorded_second:
            return
        self._last_recorded_second = second
        lat, lon = self._profile.latlon_at(snapshot.position_m)
        self._samples.append(
            _Sample(
                wall_ms=wall_ms,
                position_m=snapshot.position_m,
                lat=lat,
                lon=lon,
                altitude_m=self._profile.altitude_at(snapshot.position_m),
                grade_pct=snapshot.grade_pct,
                speed_ms=snapshot.speed_ms,
                power_w=snapshot.power_w,
                heart_rate_bpm=snapshot.heart_rate_bpm,
                cadence_rpm=snapshot.cadence_rpm,
            )
        )

    def write(self, path: Path) -> Path | None:
        """Write the FIT activity; returns None if nothing was ridden."""
        if not self._samples:
            return None
        builder = FitFileBuilder(auto_define=True)

        file_id = FileIdMessage()
        file_id.type = FileType.ACTIVITY
        file_id.manufacturer = Manufacturer.DEVELOPMENT.value
        file_id.product = 0
        file_id.time_created = self._samples[0].wall_ms
        file_id.serial_number = 1
        builder.add(file_id)

        for wall_ms, event_type in self._events:
            event = EventMessage()
            event.timestamp = wall_ms
            event.event = Event.TIMER
            event.event_type = event_type
            builder.add(event)

        for s in self._samples:
            record = RecordMessage()
            record.timestamp = s.wall_ms
            record.distance = s.position_m
            # the route's real coordinates: the virtual ride maps onto the
            # actual Malaga-Olias road on Strava and friends
            record.position_lat = s.lat
            record.position_long = s.lon
            record.altitude = s.altitude_m
            record.grade = s.grade_pct
            record.speed = s.speed_ms
            record.power = round(s.power_w)
            if s.heart_rate_bpm is not None:
                record.heart_rate = s.heart_rate_bpm
            if s.cadence_rpm is not None:
                record.cadence = round(s.cadence_rpm)
            builder.add(record)

        first, last = self._samples[0], self._samples[-1]
        timer_s = float(len(self._samples))
        elapsed_s = (last.wall_ms - first.wall_ms) / 1000 + 1

        lap = LapMessage()
        lap.timestamp = last.wall_ms
        lap.start_time = first.wall_ms
        lap.total_elapsed_time = elapsed_s
        lap.total_timer_time = timer_s
        lap.total_distance = last.position_m
        builder.add(lap)

        session = SessionMessage()
        session.timestamp = last.wall_ms
        session.start_time = first.wall_ms
        session.total_elapsed_time = elapsed_s
        session.total_timer_time = timer_s
        session.total_distance = last.position_m
        session.sport = Sport.CYCLING
        powers = [s.power_w for s in self._samples]
        session.avg_power = round(sum(powers) / len(powers))
        session.max_power = round(max(powers))
        heart_rates = [s.heart_rate_bpm for s in self._samples if s.heart_rate_bpm is not None]
        if heart_rates:
            session.avg_heart_rate = round(sum(heart_rates) / len(heart_rates))
            session.max_heart_rate = max(heart_rates)
        cadences = [s.cadence_rpm for s in self._samples if s.cadence_rpm]  # nonzero: pedaling
        if cadences:
            session.avg_cadence = round(sum(cadences) / len(cadences))
            session.max_cadence = round(max(cadences))
        builder.add(session)

        activity = ActivityMessage()
        activity.timestamp = last.wall_ms
        activity.total_timer_time = timer_s
        activity.num_sessions = 1
        builder.add(activity)

        path.parent.mkdir(parents=True, exist_ok=True)
        builder.build().to_file(str(path))
        return path
