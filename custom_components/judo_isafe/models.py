"""Protocol data models and byte-level parsers.

Kept free of Home Assistant and aiohttp imports so the wire format can be
unit tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntFlag


class ProtocolError(ValueError):
    """Raised when a response cannot be decoded."""


def read_le(data: bytes, offset: int, size: int) -> int:
    """Read a little-endian unsigned integer out of a response payload."""
    if len(data) < offset + size:
        raise ProtocolError(f"expected at least {offset + size} bytes, got {len(data)}")
    return int.from_bytes(data[offset : offset + size], "little")


class StatusBit(IntFlag):
    """Bit layout of the 4-byte little-endian status word (command 69)."""

    HOMING = 1 << 0
    CLOSED_MANUAL_OR_U3 = 1 << 1
    HOLIDAY_MODE = 1 << 2
    VOLUME_EXCEEDED = 1 << 3
    FLOW_EXCEEDED = 1 << 4
    DURATION_EXCEEDED = 1 << 5
    LEAKAGE = 1 << 6
    SLEEP_MODE = 1 << 7
    MICROLEAK_NOTIFY_AND_CLOSE = 1 << 8
    MICROLEAK_NOTIFY = 1 << 9
    MICROLEAK_NOT_DETECTED = 1 << 10
    MICROLEAK_TEST_IMPOSSIBLE = 1 << 11
    VALVE_OPENING = 1 << 12
    VALVE_CLOSING = 1 << 13
    VALVE_OPEN = 1 << 14
    VALVE_CLOSED = 1 << 15
    LEARN_VOLUME_EXCEEDED = 1 << 16
    LEARN_FLOW_EXCEEDED = 1 << 17
    LEARN_DURATION_EXCEEDED = 1 << 18
    NO_FLOW_15_DAYS = 1 << 19
    LEARN_MODE_FINISHED = 1 << 20
    CLOSED_VIA_LS_INPUT = 1 << 21
    SLEEP_VIA_LS_INPUT = 1 << 22
    LEARN_MODE_ACTIVE = 1 << 24
    SPECIAL_RULE_ACTIVE = 1 << 25


LEAK_CAUSE_OPTIONS = [
    "none",
    "flow",
    "volume",
    "duration",
    "microleak",
    "manual",
    "leakage",
]


def leak_cause(status: StatusBit) -> str:
    """Collapse the alarm bits into a single enum value, most specific first."""
    if StatusBit.FLOW_EXCEEDED in status:
        return "flow"
    if StatusBit.VOLUME_EXCEEDED in status:
        return "volume"
    if StatusBit.DURATION_EXCEEDED in status:
        return "duration"
    if status & (StatusBit.MICROLEAK_NOTIFY | StatusBit.MICROLEAK_NOTIFY_AND_CLOSE):
        return "microleak"
    if StatusBit.LEAKAGE in status:
        return "leakage"
    if StatusBit.CLOSED_MANUAL_OR_U3 in status:
        return "manual"
    return "none"


@dataclass(frozen=True, slots=True)
class LeakageSettings:
    """Payload of commands 68 (read) and 50 (write)."""

    holiday_profile: int
    max_flow_lph: int
    max_volume_l: int
    max_duration_min: int

    @classmethod
    def from_bytes(cls, data: bytes) -> LeakageSettings:
        return cls(
            holiday_profile=read_le(data, 0, 1),
            max_flow_lph=read_le(data, 1, 2),
            max_volume_l=read_le(data, 3, 2),
            max_duration_min=read_le(data, 5, 2),
        )

    def to_bytes(self) -> bytes:
        return (
            self.holiday_profile.to_bytes(1, "little")
            + self.max_flow_lph.to_bytes(2, "little")
            + self.max_volume_l.to_bytes(2, "little")
            + self.max_duration_min.to_bytes(2, "little")
        )


@dataclass(frozen=True, slots=True)
class AbsenceLimits:
    """Payload of commands 5E (read) and 5F (write)."""

    max_flow_lph: int
    max_volume_l: int
    max_duration_min: int

    @classmethod
    def from_bytes(cls, data: bytes) -> AbsenceLimits:
        return cls(
            max_flow_lph=read_le(data, 0, 2),
            max_volume_l=read_le(data, 2, 2),
            max_duration_min=read_le(data, 4, 2),
        )

    def to_bytes(self) -> bytes:
        return (
            self.max_flow_lph.to_bytes(2, "little")
            + self.max_volume_l.to_bytes(2, "little")
            + self.max_duration_min.to_bytes(2, "little")
        )


@dataclass(frozen=True, slots=True)
class LearnMode:
    """Payload of command 64."""

    active: bool
    remaining_water_l: int

    @classmethod
    def from_bytes(cls, data: bytes) -> LearnMode:
        return cls(active=read_le(data, 0, 1) == 1, remaining_water_l=read_le(data, 1, 2))


@dataclass(frozen=True, slots=True)
class AbsenceWindow:
    """Payload of commands 60 (read) and 61 (write); weekdays are 0=Sunday."""

    start_day: int
    start_hour: int
    start_minute: int
    stop_day: int
    stop_hour: int
    stop_minute: int

    @classmethod
    def from_bytes(cls, data: bytes) -> AbsenceWindow:
        return cls(*(read_le(data, i, 1) for i in range(6)))

    def to_bytes(self) -> bytes:
        return bytes(
            (
                self.start_day,
                self.start_hour,
                self.start_minute,
                self.stop_day,
                self.stop_hour,
                self.stop_minute,
            )
        )

    @property
    def is_empty(self) -> bool:
        return self.to_bytes() == bytes(6)


def parse_device_time(data: bytes) -> datetime:
    """Decode command 59: day, month, 2-digit year, hour, minute, second."""
    day, month, year, hour, minute, second = (read_le(data, i, 1) for i in range(6))
    return datetime(2000 + year, month, day, hour, minute, second)  # noqa: DTZ001


def encode_device_time(value: datetime) -> bytes:
    """Encode a local datetime for command 5A."""
    return bytes(
        (
            value.day,
            value.month,
            value.year % 100,
            value.hour,
            value.minute,
            value.second,
        )
    )


def parse_sw_version(data: bytes) -> str:
    """Decode command 01: 3 bytes rendered as ``<major>.<minor><patch-char>``."""
    if len(data) < 3:
        raise ProtocolError(f"expected 3 version bytes, got {len(data)}")
    return f"{data[2]}.{data[1]}{chr(data[0])}"


def parse_operating_time(data: bytes) -> dict[str, int]:
    """Decode command 25: minutes, hours, then days as a little-endian u16."""
    return {
        "minutes": read_le(data, 0, 1),
        "hours": read_le(data, 1, 1),
        "days": read_le(data, 2, 2),
    }
