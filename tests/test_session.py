"""Full simulated session: fake devices -> runner -> engine -> recorder -> FIT."""
import asyncio
import itertools
from pathlib import Path

import pytest

from olias import config
from olias.engine import SessionEngine
from olias.recording import SessionRecorder
from olias.reference import ReferenceRide
from olias.session import SessionRunner


class FakeTrainer:
    def __init__(self, power_w=250.0):
        self.latest_power_w = power_w
        self.latest_cadence_rpm = 85.0
        self.connected = True
        self.grades = []

    def set_grade(self, grade_pct):
        self.grades.append(grade_pct)


class FakeHeart:
    latest_bpm = 142


@pytest.fixture(scope="module")
def session_result(tmp_path_factory):
    """Ride the whole route at 250 W as fast as asyncio allows; write the FIT."""
    profile = config.load_route_profile()
    engine = SessionEngine(
        profile=profile,
        rider_model=config.default_rider_model(),
        reference=ReferenceRide.load(config.RESOURCES / "olias-ride-001.fit"),
    )
    trainer = FakeTrainer()
    recorder = SessionRecorder(profile)
    wall = itertools.count(1_753_600_000)  # deterministic 1 s wall clock per tick

    last = {}
    runner = SessionRunner(
        engine=engine,
        trainer=trainer,
        heart=FakeHeart(),
        on_snapshot=lambda snap, t: (recorder.on_snapshot(snap, t), last.update(snap=snap)),
        tick_interval_s=0,  # no sleeping; engine still ticks 0.25 s frames
        engine_dt_s=0.25,
        clock=lambda: float(next(wall)),
    )
    asyncio.run(runner.run())
    final = last["snap"]
    fit_path = tmp_path_factory.mktemp("sessions") / "test-session.fit"
    written = recorder.write(fit_path)
    return final, trainer, written


def test_session_finishes_and_commands_grades(session_result):
    final, trainer, _ = session_result
    assert final.state.name == "FINISHED"
    assert final.position_m == pytest.approx(36255, abs=10)
    assert len(trainer.grades) > 50  # grade followed the route
    assert max(trainer.grades) > 8   # including the steep bits


def test_session_recording_reads_back_as_a_reference_ride(session_result):
    final, _, written = session_result
    assert written is not None
    ride = ReferenceRide.load(written)
    # structurally identical to a Reference Ride: same loaders work
    assert ride.total_distance_m == pytest.approx(final.position_m, abs=10)
    assert ride.total_time_s == pytest.approx(final.elapsed_s, abs=2)
    assert ride.power_at_second(int(ride.total_time_s / 2)) == 250.0
    # GPS trace maps onto the real road: first moving record sits at the route start
    _, _, lat, lon = ride.moving_records[0]
    assert lat == pytest.approx(36.699, abs=0.005)
    assert lon == pytest.approx(-4.437, abs=0.005)
