import pytest

from olias.physics import RiderModel

MODEL = RiderModel(mass_kg=85)  # 75 kg rider + 10 kg bike


def ride_to_steady_state(model, power_w, grade_pct, v0=5.0):
    v = v0
    for _ in range(2400):  # 10 simulated minutes at 4 Hz
        v = model.step(speed_ms=v, power_w=power_w, grade_pct=grade_pct, dt_s=0.25)
    return v


def test_200w_on_flat_settles_near_textbook_speed():
    v = ride_to_steady_state(MODEL, power_w=200, grade_pct=0.0)
    assert v == pytest.approx(9.35, abs=0.35)  # ~33-34 km/h


def test_200w_on_seven_percent_grade_is_climbing_pace():
    v = ride_to_steady_state(MODEL, power_w=200, grade_pct=7.0)
    assert v == pytest.approx(3.1, abs=0.3)  # ~11 km/h
    assert v < ride_to_steady_state(MODEL, power_w=200, grade_pct=0.0) / 2


def test_coasting_accelerates_downhill_and_stops_on_flat():
    downhill = MODEL.step(speed_ms=5.0, power_w=0, grade_pct=-8.0, dt_s=0.25)
    assert downhill > 5.0
    v = ride_to_steady_state(MODEL, power_w=0, grade_pct=0.0)
    assert v == 0.0


def test_standstill_with_power_gets_moving():
    v = MODEL.step(speed_ms=0.0, power_w=200, grade_pct=5.0, dt_s=0.25)
    assert v > 0.0


def test_more_power_is_never_slower():
    for grade in (-5.0, 0.0, 8.0):
        low = MODEL.step(speed_ms=4.0, power_w=150, grade_pct=grade, dt_s=0.25)
        high = MODEL.step(speed_ms=4.0, power_w=250, grade_pct=grade, dt_s=0.25)
        assert high > low
