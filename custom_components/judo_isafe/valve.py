"""Valve platform - only available when the device answers the status command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.valve import ValveDeviceClass, ValveEntity, ValveEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import JudoError
from .const import Command
from .entity import JudoLiveEntity
from .models import StatusBit

if TYPE_CHECKING:
    from . import JudoConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JudoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the valve if the firmware reports its position."""
    if entry.runtime_data.capabilities.status:
        async_add_entities([JudoValve(entry)])


class JudoValve(JudoLiveEntity, ValveEntity):
    """The leakage protection ball valve."""

    _attr_device_class = ValveDeviceClass.WATER
    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    def __init__(self, entry: JudoConfigEntry) -> None:
        super().__init__(entry, "leakage_protection")

    @property
    def _status(self) -> StatusBit:
        return self.coordinator.data.status or StatusBit(0)

    @property
    def is_closed(self) -> bool | None:
        status = self._status
        if StatusBit.VALVE_CLOSED in status:
            return True
        if StatusBit.VALVE_OPEN in status:
            return False
        return None

    @property
    def is_opening(self) -> bool:
        return StatusBit.VALVE_OPENING in self._status

    @property
    def is_closing(self) -> bool:
        return StatusBit.VALVE_CLOSING in self._status

    async def async_open_valve(self, **kwargs: Any) -> None:
        await self._async_send(Command.VALVE_OPEN)

    async def async_close_valve(self, **kwargs: Any) -> None:
        await self._async_send(Command.VALVE_CLOSE)

    async def _async_send(self, command: Command) -> None:
        try:
            await self.entry.runtime_data.client.async_command(command)
        except JudoError as err:
            raise HomeAssistantError(str(err)) from err
        # The valve takes seconds to travel; poll fast until motion clears.
        self.coordinator.note_valve_command()
        await self.coordinator.async_request_refresh()
