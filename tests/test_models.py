"""Byte-level decoding tests against the vectors printed in JUDO's command list."""

from datetime import datetime

import pytest
from models import (
    AbsenceLimits,
    AbsenceWindow,
    LeakageSettings,
    LearnMode,
    ProtocolError,
    StatusBit,
    encode_device_time,
    leak_cause,
    parse_device_time,
    parse_operating_time,
    parse_sw_version,
    read_le,
)


def test_total_water_is_little_endian():
    # Documented: data=EC221000 -> 1057.516 m3
    assert read_le(bytes.fromhex("EC221000"), 0, 4) == 1057516


def test_status_word_bits():
    # Documented: data=04400000 -> holiday mode and valve open
    status = StatusBit(read_le(bytes.fromhex("04400000"), 0, 4))
    assert StatusBit.HOLIDAY_MODE in status
    assert StatusBit.VALVE_OPEN in status
    assert StatusBit.LEAKAGE not in status
    assert StatusBit.VALVE_CLOSED not in status


def test_absence_limits_read():
    # Documented: data=640005000500 -> 100 l/h, 5 l, 5 min
    limits = AbsenceLimits.from_bytes(bytes.fromhex("640005000500"))
    assert limits == AbsenceLimits(max_flow_lph=100, max_volume_l=5, max_duration_min=5)


def test_absence_limits_round_trip():
    limits = AbsenceLimits(max_flow_lph=2500, max_volume_l=500, max_duration_min=10)
    assert AbsenceLimits.from_bytes(limits.to_bytes()) == limits


def test_absence_limits_write_encoding_differs_from_manual_example():
    """The manual's 5F example is internally inconsistent.

    It shows ``5F009C04F4010A00`` annotated as 2500 l/h, but 9C04 decodes to
    1180 little-endian while the other two fields decode correctly. 2500 l/h
    encodes as C409, so the annotation - not the byte order - is wrong.
    """
    limits = AbsenceLimits(max_flow_lph=2500, max_volume_l=500, max_duration_min=10)
    assert limits.to_bytes().hex().upper() == "C409F4010A00"


def test_leakage_settings_read():
    # Documented: data=02D007FA000A00 -> U2, 2000 l/h, 250 l, 10 min
    settings = LeakageSettings.from_bytes(bytes.fromhex("02D007FA000A00"))
    assert settings == LeakageSettings(
        holiday_profile=2, max_flow_lph=2000, max_volume_l=250, max_duration_min=10
    )
    assert settings.to_bytes().hex().upper() == "02D007FA000A00"


def test_learn_mode():
    # Documented: data=011027 -> active, 10 m3 remaining
    assert LearnMode.from_bytes(bytes.fromhex("011027")) == LearnMode(
        active=True, remaining_water_l=10000
    )


def test_device_time_round_trip():
    # Documented: data=1c04170e041e -> 28.4.23 14:04:30
    value = parse_device_time(bytes.fromhex("1c04170e041e"))
    assert value == datetime(2023, 4, 28, 14, 4, 30)
    assert encode_device_time(value).hex() == "1c04170e041e"


@pytest.mark.parametrize(
    ("payload", "expected"),
    [("6b1502", "2.21k"), ("661301", "1.19f")],
)
def test_sw_version(payload, expected):
    assert parse_sw_version(bytes.fromhex(payload)) == expected


def test_operating_time():
    # Documented: data=060c7500 -> 117 days, 12 h, 6 min
    assert parse_operating_time(bytes.fromhex("060c7500")) == {
        "minutes": 6,
        "hours": 12,
        "days": 117,
    }


def test_absence_window_round_trip_and_empty():
    # Documented: data=020400030700 -> Tue 04:00 to Wed 07:00
    window = AbsenceWindow.from_bytes(bytes.fromhex("020400030700"))
    assert window == AbsenceWindow(2, 4, 0, 3, 7, 0)
    assert window.to_bytes().hex() == "020400030700"
    assert not window.is_empty
    assert AbsenceWindow.from_bytes(bytes(6)).is_empty


def test_leak_cause_prefers_the_most_specific_bit():
    assert leak_cause(StatusBit.FLOW_EXCEEDED | StatusBit.LEAKAGE) == "flow"
    assert leak_cause(StatusBit.LEAKAGE) == "leakage"
    assert leak_cause(StatusBit.VALVE_OPEN) == "none"


def test_short_payload_is_rejected():
    with pytest.raises(ProtocolError):
        read_le(b"\x01", 0, 4)
