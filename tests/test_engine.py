import pytest

from olias import config
from olias.engine import EngineState, SessionEngine
from olias.reference import ReferenceRide


@pytest.fixture(scope="module")
def profile():
    return config.load_route_profile()


@pytest.fixture(scope="module")
def reference():
    return ReferenceRide.load(config.RESOURCES / "olias-ride-001.fit")


@pytest.fixture
def engine(profile, reference):
    return SessionEngine(
        profile=profile, rider_model=config.default_rider_model(), reference=reference
    )


DT = 0.25  # 4 Hz


def test_armed_until_first_pedal_power(engine):
    for _ in range(8):
        snap = engine.tick(power_w=0.0, heart_rate_bpm=None, dt_s=DT)
    assert snap.state is EngineState.ARMED
    assert snap.elapsed_s == 0.0
    assert snap.position_m == 0.0

    snap = engine.tick(power_w=150.0, heart_rate_bpm=95, dt_s=DT)
    assert snap.state is EngineState.RIDING


def ride_ticks(engine, n, power_w=180.0):
    snap = None
    for _ in range(n):
        snap = engine.tick(power_w=power_w, heart_rate_bpm=140, dt_s=DT)
    return snap


def test_riding_advances_position_clock_and_burns_ascent(engine, profile):
    total_ascent = profile.remaining_ascent(0)
    snap = ride_ticks(engine, 240)  # one minute at 4 Hz
    assert snap.elapsed_s == pytest.approx(60.0)
    assert snap.position_m > 200  # 180 W moves a rider well past standstill
    assert 0 < snap.speed_ms < 20
    assert snap.remaining_ascent_m < total_ascent
    assert snap.heart_rate_bpm == 140


def test_trainer_commanded_on_start_then_only_on_meaningful_grade_change(engine):
    armed = engine.tick(power_w=0.0, heart_rate_bpm=None, dt_s=DT)
    assert armed.trainer_grade_pct is None

    first = engine.tick(power_w=180.0, heart_rate_bpm=None, dt_s=DT)
    assert first.trainer_grade_pct == pytest.approx(first.grade_pct)

    commands = 0
    last_commanded = first.trainer_grade_pct
    for _ in range(2400):  # ten minutes of riding
        snap = engine.tick(power_w=180.0, heart_rate_bpm=None, dt_s=DT)
        if snap.trainer_grade_pct is not None:
            assert abs(snap.trainer_grade_pct - last_commanded) >= 0.1
            last_commanded = snap.trainer_grade_pct
            commands += 1
    # the flat approach varies gently: commands happen, but far below once-per-tick
    assert 0 < commands < 600


def test_pause_freezes_the_ride_and_eases_the_trainer(engine):
    riding = ride_ticks(engine, 240)

    engine.pause()
    paused = engine.tick(power_w=0.0, heart_rate_bpm=None, dt_s=DT)
    assert paused.state is EngineState.PAUSED
    assert paused.trainer_grade_pct == 0.0
    for _ in range(400):  # dawdle off the bike
        snap = engine.tick(power_w=0.0, heart_rate_bpm=None, dt_s=DT)
    assert snap.elapsed_s == riding.elapsed_s
    assert snap.position_m == riding.position_m
    assert snap.trainer_grade_pct is None  # 0% commanded once, not respammed

    engine.resume()
    resumed = engine.tick(power_w=180.0, heart_rate_bpm=None, dt_s=DT)
    assert resumed.state is EngineState.RIDING
    assert resumed.elapsed_s == pytest.approx(riding.elapsed_s + DT)
    assert resumed.trainer_grade_pct == pytest.approx(resumed.grade_pct)
    assert resumed.speed_ms == pytest.approx(riding.speed_ms, abs=1.0)


def ride_until(engine, position_m, power_w, max_ticks=100_000):
    snap = engine.tick(power_w=power_w, heart_rate_bpm=None, dt_s=DT)
    ticks = 0
    while snap.position_m < position_m and ticks < max_ticks:
        snap = engine.tick(power_w=power_w, heart_rate_bpm=None, dt_s=DT)
        ticks += 1
    return snap


def test_climb_delta_appears_on_climb_and_trails_when_weak(engine, profile):
    before = ride_until(engine, profile.climb.start_m - 500, power_w=180.0)
    assert before.climb_delta_s is None

    # out-of-shape watts: reference-you climbed at ~183 W, current-you rides 120 W
    on_climb = ride_until(engine, profile.climb.start_m + 2000, power_w=120.0)
    assert on_climb.climb_delta_s is not None
    assert on_climb.climb_delta_s < 0  # trailing

    later = ride_until(engine, profile.climb.start_m + 4000, power_w=120.0)
    assert later.climb_delta_s < on_climb.climb_delta_s  # falling further behind
    assert later.climb_delta_s < -60  # by minutes, not seconds


def test_climb_time_runs_on_climb_and_freezes_at_the_shoulder(engine, profile):
    before = ride_until(engine, profile.climb.start_m - 500, power_w=180.0)
    assert before.climb_time_s is None

    mid = ride_until(engine, profile.climb.start_m + 3000, power_w=180.0)
    assert mid.climb_time_s is not None and mid.climb_time_s > 0

    later = ride_until(engine, profile.climb.start_m + 5000, power_w=180.0)
    assert later.climb_time_s > mid.climb_time_s  # still ticking

    past = ride_until(engine, profile.climb.end_m + 500, power_w=180.0)
    frozen = ride_until(engine, profile.climb.end_m + 1500, power_w=180.0)
    assert frozen.climb_time_s == past.climb_time_s  # the result, kept on screen


def test_summit_eta_adapts_to_todays_pace(engine, profile):
    before = ride_until(engine, profile.climb.start_m - 500, power_w=180.0)
    assert before.summit_eta_s is None

    # ride a good stretch of the climb at out-of-shape watts
    early = ride_until(engine, profile.climb.start_m + 2500, power_w=120.0)
    assert early.summit_eta_s is not None

    reference_remaining = engine._reference.elapsed_s_at(
        profile.climb.end_m
    ) - engine._reference.elapsed_s_at(early.position_m)
    # slower than reference today -> ETA must exceed reference pacing from here
    assert early.summit_eta_s > reference_remaining

    later = ride_until(engine, profile.climb.start_m + 5000, power_w=120.0)
    assert later.summit_eta_s < early.summit_eta_s  # progress shrinks the ETA

    past = ride_until(engine, profile.climb.end_m + 100, power_w=180.0)
    assert past.summit_eta_s is None  # gone once the shoulder is crested


def test_climb_delta_leads_when_strong(engine, profile):
    ride_until(engine, profile.climb.start_m - 100, power_w=180.0)
    snap = ride_until(engine, profile.climb.start_m + 3000, power_w=300.0)
    assert snap.climb_delta_s > 0


def test_restore_continues_a_ride_mid_climb(engine, profile):
    engine.restore(
        position_m=12000.0,  # mid-climb
        elapsed_s=2000.0,
        climb_started_at_s=1300.0,
        cadence_sum=8000.0,
        cadence_samples=100,
    )
    armed = engine.tick(power_w=0.0, heart_rate_bpm=None, dt_s=DT)
    assert armed.state is EngineState.ARMED  # pedal to (re)start
    assert armed.position_m == 12000.0

    snap = engine.tick(power_w=150.0, heart_rate_bpm=None, cadence_rpm=90.0, dt_s=DT)
    assert snap.state is EngineState.RIDING
    assert snap.elapsed_s == pytest.approx(2000.0 + DT)
    assert snap.position_m > 12000.0
    assert snap.remaining_ascent_m < profile.remaining_ascent(0)
    assert snap.climb_delta_s is not None  # climb comparison carries on
    assert snap.climb_time_s == pytest.approx(2000.25 - 1300.0)
    assert snap.avg_cadence_rpm == pytest.approx((8000 + 90) / 101)


def test_average_cadence_excludes_coasting(engine):
    engine.tick(power_w=150.0, heart_rate_bpm=None, cadence_rpm=80.0, dt_s=DT)
    engine.tick(power_w=150.0, heart_rate_bpm=None, cadence_rpm=90.0, dt_s=DT)
    snap = engine.tick(power_w=0.0, heart_rate_bpm=None, cadence_rpm=0.0, dt_s=DT)
    assert snap.cadence_rpm == 0.0
    assert snap.avg_cadence_rpm == pytest.approx(85.0)  # zeros are coasting, not pedaling


def test_reaching_route_end_finishes_the_session(engine, profile):
    snap = ride_until(engine, profile.total_distance_m, power_w=250.0)
    assert snap.state is EngineState.FINISHED
    assert snap.remaining_ascent_m == 0.0

    frozen = engine.tick(power_w=250.0, heart_rate_bpm=None, dt_s=DT)
    assert frozen.state is EngineState.FINISHED
    assert frozen.elapsed_s == snap.elapsed_s
    assert frozen.position_m == snap.position_m
    assert frozen.trainer_grade_pct is None
