"""Async REST client for the JUDO connectivity module."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

import aiohttp

from .const import Command
from .models import (
    AbsenceLimits,
    AbsenceWindow,
    LeakageSettings,
    LearnMode,
    ProtocolError,
    StatusBit,
    encode_device_time,
    parse_device_time,
    parse_operating_time,
    parse_sw_version,
    read_le,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class JudoError(Exception):
    """Base error for all client failures."""


class JudoConnectionError(JudoError):
    """The module could not be reached."""


class JudoAuthError(JudoError):
    """The module rejected the credentials."""


class JudoCommandUnsupported(JudoError):
    """The device does not answer this command."""


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    device_type: int
    device_number: int
    sw_version: str


@dataclass(frozen=True, slots=True)
class Capabilities:
    """Which optional commands this unit actually answers.

    Firmware varies: several shipping i-SAFE units reject the documented status
    (69) and leakage-settings read (68) commands, so both are probed at setup
    instead of being inferred from the device type.
    """

    status: bool
    leakage_settings_read: bool
    absence_limits: bool
    sleep_duration_read: bool


class JudoClient:
    """Talks to ``/api/rest`` on the connectivity module."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._base_url = f"http://{host}:{port}/api/rest"
        self._auth = aiohttp.BasicAuth(username, password)
        # The module serves one request at a time; concurrent calls time out.
        self._lock = asyncio.Lock()

    async def _request(self, command: Command, payload: bytes = b"") -> bytes:
        url = f"{self._base_url}/{command.value}{payload.hex().upper()}"
        async with self._lock:
            try:
                async with self._session.get(
                    url, auth=self._auth, timeout=REQUEST_TIMEOUT
                ) as response:
                    if response.status == 401:
                        raise JudoAuthError("invalid username or password")
                    if response.status >= 400:
                        raise JudoCommandUnsupported(
                            f"{command.name} returned HTTP {response.status}"
                        )
                    body = await response.json(content_type=None)
            except TimeoutError as err:
                raise JudoConnectionError(f"{command.name} timed out") from err
            except aiohttp.ClientError as err:
                raise JudoConnectionError(f"{command.name} failed: {err}") from err

        if not isinstance(body, dict) or "data" not in body:
            raise JudoCommandUnsupported(f"{command.name} returned no data field")
        try:
            return bytes.fromhex(str(body["data"]))
        except ValueError as err:
            raise ProtocolError(f"{command.name} returned malformed hex") from err

    async def async_command(self, command: Command, payload: bytes = b"") -> None:
        """Send a command whose response carries no readable payload."""
        await self._request(command, payload)

    async def async_get_identity(self) -> DeviceIdentity:
        device_type = read_le(await self._request(Command.DEVICE_TYPE), 0, 1)
        device_number = read_le(await self._request(Command.DEVICE_NUMBER), 0, 4)
        sw_version = parse_sw_version(await self._request(Command.SW_VERSION))
        return DeviceIdentity(device_type, device_number, sw_version)

    async def async_probe_capabilities(self) -> Capabilities:
        return Capabilities(
            status=await self._supports(Command.STATUS),
            leakage_settings_read=await self._supports(Command.LEAKAGE_SETTINGS_READ),
            absence_limits=await self._supports(Command.ABSENCE_LIMITS_READ),
            sleep_duration_read=await self._supports(Command.SLEEP_DURATION_READ),
        )

    async def _supports(self, command: Command) -> bool:
        """Probe a read-only command.

        Only commands documented as reads are ever probed: command IDs are
        reused across JUDO device families, so blindly sweeping them could
        trigger a write - on this device 0x51 closes the main water valve.
        """
        try:
            await self._request(command)
        except (JudoCommandUnsupported, ProtocolError):
            return False
        return True

    async def async_get_total_water_l(self) -> int:
        return read_le(await self._request(Command.TOTAL_WATER), 0, 4)

    async def async_get_status(self) -> StatusBit:
        return StatusBit(read_le(await self._request(Command.STATUS), 0, 4))

    async def async_get_leakage_settings(self) -> LeakageSettings:
        return LeakageSettings.from_bytes(await self._request(Command.LEAKAGE_SETTINGS_READ))

    async def async_set_leakage_settings(self, settings: LeakageSettings) -> None:
        await self._request(Command.LEAKAGE_SETTINGS_WRITE, settings.to_bytes())

    async def async_get_absence_limits(self) -> AbsenceLimits:
        return AbsenceLimits.from_bytes(await self._request(Command.ABSENCE_LIMITS_READ))

    async def async_set_absence_limits(self, limits: AbsenceLimits) -> None:
        await self._request(Command.ABSENCE_LIMITS_WRITE, limits.to_bytes())

    async def async_get_sleep_duration_h(self) -> int:
        return read_le(await self._request(Command.SLEEP_DURATION_READ), 0, 1)

    async def async_set_sleep_duration_h(self, hours: int) -> None:
        await self._request(Command.SLEEP_DURATION_WRITE, bytes([hours]))

    async def async_get_microleak_mode(self) -> int:
        return read_le(await self._request(Command.MICROLEAK_MODE_READ), 0, 1)

    async def async_set_microleak_mode(self, mode: int) -> None:
        await self._request(Command.MICROLEAK_MODE_WRITE, bytes([mode]))

    async def async_get_learn_mode(self) -> LearnMode:
        return LearnMode.from_bytes(await self._request(Command.LEARN_MODE_STATUS))

    async def async_acknowledge_learn_mode(self, accept: bool) -> None:
        await self._request(Command.LEARN_MODE_ACK, bytes([1 if accept else 0]))

    async def async_set_holiday_profile(self, profile: int) -> None:
        await self._request(Command.HOLIDAY_PROFILE_WRITE, bytes([profile]))

    async def async_set_priority(self, priority: int) -> None:
        await self._request(Command.PRIORITY_WRITE, bytes([priority]))

    async def async_get_device_time(self) -> datetime:
        return parse_device_time(await self._request(Command.DEVICE_TIME_READ))

    async def async_set_device_time(self, value: datetime) -> None:
        await self._request(Command.DEVICE_TIME_WRITE, encode_device_time(value))

    async def async_get_operating_time(self) -> dict[str, int]:
        return parse_operating_time(await self._request(Command.OPERATING_HOURS))

    async def async_get_absence_window(self, slot: int) -> AbsenceWindow:
        return AbsenceWindow.from_bytes(
            await self._request(Command.ABSENCE_WINDOW_READ, bytes([slot]))
        )

    async def async_set_absence_window(self, slot: int, window: AbsenceWindow) -> None:
        await self._request(Command.ABSENCE_WINDOW_WRITE, bytes([slot]) + window.to_bytes())

    async def async_clear_absence_window(self, slot: int) -> None:
        await self._request(Command.ABSENCE_WINDOW_CLEAR, bytes([slot]))
