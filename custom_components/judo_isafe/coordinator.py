"""Update coordinators.

Two of them: valve motion needs sub-minute resolution, while the settings
commands return values that change at most when a user edits them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import Capabilities, JudoAuthError, JudoClient, JudoError
from .const import DOMAIN
from .flow_tracker import FlowTracker
from .models import AbsenceLimits, LeakageSettings, LearnMode, StatusBit

_LOGGER = logging.getLogger(__name__)

# While the ball valve travels, poll fast enough to animate the transition.
MOVING_INTERVAL = timedelta(seconds=3)


@dataclass(slots=True)
class LiveData:
    total_water_l: int
    flow_l_per_min: float | None
    is_flowing: bool
    status: StatusBit | None


@dataclass(slots=True)
class SettingsData:
    absence_limits: AbsenceLimits | None
    leakage_settings: LeakageSettings | None
    sleep_duration_h: int | None
    microleak_mode: int | None
    learn_mode: LearnMode | None
    device_time: datetime | None
    operating_days: int | None


class JudoLiveCoordinator(DataUpdateCoordinator[LiveData]):
    """Polls the water counter and, when supported, the status word."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: JudoClient,
        capabilities: Capabilities,
        interval: timedelta,
        flow_window: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_live",
            update_interval=interval,
        )
        self._client = client
        self._capabilities = capabilities
        self._idle_interval = interval
        self._flow = FlowTracker(flow_window)

    async def _async_update_data(self) -> LiveData:
        try:
            total_water_l = await self._client.async_get_total_water_l()
            status = await self._client.async_get_status() if self._capabilities.status else None
        except JudoAuthError as err:
            raise UpdateFailed(str(err)) from err
        except JudoError as err:
            raise UpdateFailed(str(err)) from err

        self._flow.add(total_water_l, dt_util.utcnow())
        self._apply_motion_backoff(status)

        # A closed valve cannot pass water; suppress the stale averaging window.
        closed = status is not None and StatusBit.VALVE_CLOSED in status
        flow = 0.0 if closed else self._flow.flow_l_per_min
        return LiveData(
            total_water_l=total_water_l,
            flow_l_per_min=flow,
            is_flowing=False if closed else self._flow.is_flowing,
            status=status,
        )

    def _apply_motion_backoff(self, status: StatusBit | None) -> None:
        if status is None:
            return
        moving = bool(status & (StatusBit.VALVE_OPENING | StatusBit.VALVE_CLOSING))
        wanted = MOVING_INTERVAL if moving else self._idle_interval
        if self.update_interval != wanted:
            self.update_interval = wanted

    def note_valve_command(self) -> None:
        """Speed up polling right after an open/close so motion is picked up."""
        self.update_interval = MOVING_INTERVAL


class JudoSettingsCoordinator(DataUpdateCoordinator[SettingsData]):
    """Polls the readable configuration commands."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: JudoClient,
        capabilities: Capabilities,
        interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_settings",
            update_interval=interval,
        )
        self._client = client
        self._capabilities = capabilities

    async def _async_update_data(self) -> SettingsData:
        try:
            absence_limits = (
                await self._client.async_get_absence_limits()
                if self._capabilities.absence_limits
                else None
            )
            leakage_settings = (
                await self._client.async_get_leakage_settings()
                if self._capabilities.leakage_settings_read
                else None
            )
            sleep_duration_h = (
                await self._client.async_get_sleep_duration_h()
                if self._capabilities.sleep_duration_read
                else None
            )
            microleak_mode = await self._client.async_get_microleak_mode()
            learn_mode = await self._client.async_get_learn_mode()
            device_time = await self._client.async_get_device_time()
            operating_days = (await self._client.async_get_operating_time())["days"]
        except JudoError as err:
            raise UpdateFailed(str(err)) from err

        return SettingsData(
            absence_limits=absence_limits,
            leakage_settings=leakage_settings,
            sleep_duration_h=sleep_duration_h,
            microleak_mode=microleak_mode,
            learn_mode=learn_mode,
            device_time=device_time,
            operating_days=operating_days,
        )
