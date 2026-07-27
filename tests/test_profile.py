import csv
from pathlib import Path

import pytest

from olias.config import CLIMB
from olias.profile import RouteProfile

ROUTE_CSV = Path(__file__).parent.parent / "resources" / "olias-route.csv"


@pytest.fixture(scope="module")
def profile():
    return RouteProfile.load(ROUTE_CSV, climb=CLIMB)


@pytest.fixture(scope="module")
def rows():
    with open(ROUTE_CSV, newline="") as f:
        return list(csv.DictReader(f))


def test_load_reports_total_distance(profile):
    assert profile.total_distance_m == pytest.approx(36255, abs=5)


def test_altitude_interpolates_between_grid_points(profile, rows):
    d0, a0 = float(rows[100]["distance_m"]), float(rows[100]["altitude_m"])
    d1, a1 = float(rows[101]["distance_m"]), float(rows[101]["altitude_m"])

    assert profile.altitude_at(d0) == pytest.approx(a0)
    assert profile.altitude_at((d0 + d1) / 2) == pytest.approx((a0 + a1) / 2)


def test_altitude_clamps_beyond_route_ends(profile):
    assert profile.altitude_at(-50) == profile.altitude_at(0)
    assert profile.altitude_at(10**9) == profile.altitude_at(profile.total_distance_m)


def test_remaining_ascent_at_start_is_total_ascent(profile):
    assert profile.remaining_ascent(0) == pytest.approx(583, abs=2)


def test_remaining_ascent_at_route_end_is_zero(profile):
    assert profile.remaining_ascent(profile.total_distance_m) == 0


def test_remaining_ascent_never_increases_along_the_route(profile):
    samples = [profile.remaining_ascent(d) for d in range(0, 36255, 500)]
    assert all(a >= b for a, b in zip(samples, samples[1:]))


def test_grade_matches_route_data_at_grid_points(profile, rows):
    d, g = float(rows[2500]["distance_m"]), float(rows[2500]["grade_pct"])
    assert profile.grade_at(d) == pytest.approx(g)
    # mid-climb the route is meaningfully uphill
    assert profile.grade_at(13000) > 3.0


def test_on_climb_includes_start_and_excludes_end(profile):
    assert not profile.on_climb(CLIMB.start_m - 1)
    assert profile.on_climb(CLIMB.start_m)
    assert profile.on_climb((CLIMB.start_m + CLIMB.end_m) / 2)
    assert not profile.on_climb(CLIMB.end_m)


def test_latlon_matches_route_data_at_grid_points(profile, rows):
    r = rows[3000]
    lat, lon = profile.latlon_at(float(r["distance_m"]))
    assert lat == pytest.approx(float(r["lat"]), abs=1e-6)
    assert lon == pytest.approx(float(r["lon"]), abs=1e-6)
