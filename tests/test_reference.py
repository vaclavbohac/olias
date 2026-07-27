from pathlib import Path

import pytest

from olias.reference import ReferenceRide

RESOURCES = Path(__file__).parent.parent / "resources"


@pytest.fixture(scope="module")
def ride_001():
    return ReferenceRide.load(RESOURCES / "olias-ride-001.fit")


def test_load_reports_riding_time_and_distance(ride_001):
    assert ride_001.total_time_s == pytest.approx(6993, abs=2)
    assert ride_001.total_distance_m == pytest.approx(36258, abs=5)


def test_elapsed_time_grows_monotonically_with_position(ride_001):
    assert ride_001.elapsed_s_at(0) == 0.0
    assert ride_001.elapsed_s_at(ride_001.total_distance_m) == pytest.approx(
        ride_001.total_time_s, abs=2
    )
    marks = [ride_001.elapsed_s_at(d) for d in range(0, 36000, 1000)]
    assert all(a < b for a, b in zip(marks, marks[1:], strict=False))
    # reaching halfway through the Climb takes a meaningful chunk of the ride
    assert 1000 < ride_001.elapsed_s_at(13000) < 6000


def test_power_gaps_read_as_zero_watts():
    ride_002 = ReferenceRide.load(RESOURCES / "olias-ride-002.fit")
    powers = [ride_002.power_at_second(t) for t in range(int(ride_002.total_time_s))]
    assert all(isinstance(p, float) for p in powers)
    # ride 002 has ~650 missing power samples; with true 0 W moments on top,
    # zeros must be at least that many
    assert sum(1 for p in powers if p == 0.0) > 600


def test_power_beyond_ride_end_is_zero(ride_001):
    assert ride_001.power_at_second(10**6) == 0.0
