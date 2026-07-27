"""Wire-format tests for the FTMS and Heart Rate payloads (pure functions)."""
import struct

from olias.ble.heart import parse_heart_rate
from olias.ble.trainer import TrainerAdapter, parse_indoor_bike_data


def test_indoor_bike_data_power_extracted_after_speed_field():
    # bit6 set (power), bit0 clear (speed field present before it)
    payload = struct.pack("<H", 0x0040) + struct.pack("<H", 2500) + struct.pack("<h", 215)
    assert parse_indoor_bike_data(payload) == (215.0, None)


def test_indoor_bike_data_extracts_cadence_in_half_rpm():
    # speed + cadence + total distance (uint24) + power
    flags = 0x0040 | 0x0004 | 0x0010
    payload = (
        struct.pack("<H", flags)
        + struct.pack("<H", 2500)   # speed
        + struct.pack("<H", 170)    # cadence: 170 * 0.5 = 85 rpm
        + b"\x10\x27\x00"           # distance uint24
        + struct.pack("<h", 321)    # power
    )
    assert parse_indoor_bike_data(payload) == (321.0, 85.0)


def test_indoor_bike_data_without_power_returns_none():
    payload = struct.pack("<H", 0x0000) + struct.pack("<H", 2500)
    assert parse_indoor_bike_data(payload) == (None, None)


def test_sim_params_encode_grade_in_hundredths():
    op, wind, grade, crr, cw = struct.unpack("<BhhBB", TrainerAdapter._sim_params(5.5))
    assert (op, wind, grade, crr, cw) == (0x11, 0, 550, 40, 51)


def test_sim_params_negative_grade():
    _, _, grade, _, _ = struct.unpack("<BhhBB", TrainerAdapter._sim_params(-3.2))
    assert grade == -320


def test_heart_rate_both_wire_formats():
    assert parse_heart_rate(bytes([0x00, 142])) == 142
    assert parse_heart_rate(bytes([0x01, 0x90, 0x01])) == 400
