"""Replay Validation: the Rider Model must reproduce real climbs (see CONTEXT.md).

Feeds each Reference Ride's recorded power through the calibrated Rider Model
over the Climb and compares simulated moving time to the ride's real moving
time. Ride 001 is in-sample (the calibration target); the others are
out-of-sample and carry looser bounds — they were ridden under different
conditions (wind, tires, season), which a single Crr cannot capture exactly.
"""
import pytest

from olias import config
from olias.reference import ReferenceRide
from olias.replay import climb_replay_time_s, real_climb_moving_time_s


@pytest.fixture(scope="module")
def profile():
    return config.load_route_profile()


def replay_error(name, profile):
    ride = ReferenceRide.load(config.RESOURCES / f"olias-ride-{name}.fit")
    sim = climb_replay_time_s(config.default_rider_model(), ride, profile)
    real = real_climb_moving_time_s(ride, profile)
    return sim / real - 1


def test_replay_of_ride_001_matches_reality_in_sample(profile):
    assert abs(replay_error("001", profile)) < 0.02


@pytest.mark.parametrize("name,bound", [("002", 0.06), ("004", 0.06)])
def test_replay_out_of_sample_within_condition_variance(profile, name, bound):
    assert abs(replay_error(name, profile)) < bound


def test_replay_of_oldest_ride_within_loose_bound(profile):
    # ride 003 is 2.5 years older than the calibration ride; conditions drifted
    assert abs(replay_error("003", profile)) < 0.12
