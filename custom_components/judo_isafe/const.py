"""Constants for the JUDO ZEWA i-SAFE integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "judo_isafe"

DEFAULT_PORT: Final = 80
DEFAULT_USERNAME: Final = "admin"
DEFAULT_PASSWORD: Final = "Connectivity"

CONF_FLOW_WINDOW: Final = "flow_window"
CONF_LIVE_INTERVAL: Final = "live_interval"
CONF_SETTINGS_INTERVAL: Final = "settings_interval"

DEFAULT_FLOW_WINDOW: Final = 120
DEFAULT_LIVE_INTERVAL: Final = 30
DEFAULT_SETTINGS_INTERVAL: Final = 300

# The i-SAFE reuses device type 0x44 across ZEWA i-SAFE, ZEWA i-SAFE FILT and
# PROM-i-SAFE; the variants differ only in which commands they answer.
DEVICE_TYPE_ISAFE: Final = 0x44

SERVICE_SET_ABSENCE_WINDOW: Final = "set_absence_window"
SERVICE_CLEAR_ABSENCE_WINDOW: Final = "clear_absence_window"
SERVICE_ACKNOWLEDGE_LEARN_MODE: Final = "acknowledge_learn_mode"


class Command(StrEnum):
    """REST command prefixes including the trailing separator byte.

    A request is ``/api/rest/<value><payload-hex>``; reads send no payload.
    """

    DEVICE_TYPE = "FF00"
    DEVICE_NUMBER = "0600"
    SW_VERSION = "0100"
    INSTALL_DATE = "0E00"
    OPERATING_HOURS = "2500"
    TOTAL_WATER = "2800"

    STATUS = "6900"
    LEAKAGE_SETTINGS_READ = "6800"
    LEAKAGE_SETTINGS_WRITE = "5000"
    ABSENCE_LIMITS_READ = "5E00"
    ABSENCE_LIMITS_WRITE = "5F00"
    SLEEP_DURATION_READ = "6600"
    SLEEP_DURATION_WRITE = "5300"
    MICROLEAK_MODE_READ = "6500"
    MICROLEAK_MODE_WRITE = "5B00"
    LEARN_MODE_STATUS = "6400"
    LEARN_MODE_ACK = "6B00"
    HOLIDAY_PROFILE_WRITE = "5600"
    PRIORITY_WRITE = "6A00"
    DEVICE_TIME_READ = "5900"
    DEVICE_TIME_WRITE = "5A00"

    VALVE_CLOSE = "5100"
    VALVE_OPEN = "5200"
    SLEEP_START = "5400"
    SLEEP_END = "5500"
    HOLIDAY_START = "5700"
    HOLIDAY_END = "5800"
    MICROLEAK_TEST = "5C00"
    LEARN_MODE_START = "5D00"
    RESET_MESSAGE = "6300"

    ABSENCE_WINDOW_READ = "6000"
    ABSENCE_WINDOW_WRITE = "6100"
    ABSENCE_WINDOW_CLEAR = "6200"


HOLIDAY_PROFILES: Final = ["off", "u1", "u2", "u3"]
MICROLEAK_MODES: Final = ["disabled", "notify", "notify_and_close"]
PRIORITY_MODES: Final = ["holiday", "special_rule"]
