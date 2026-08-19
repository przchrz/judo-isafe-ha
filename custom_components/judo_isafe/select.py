"""Select platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .api import JudoError
from .const import HOLIDAY_PROFILES, MICROLEAK_MODES, PRIORITY_MODES
from .entity import JudoSettingsEntity

if TYPE_CHECKING:
    from . import JudoConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JudoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the enumerated settings."""
    async_add_entities(
        [
            JudoMicroleakModeSelect(entry),
            JudoHolidayProfileSelect(entry),
            JudoPrioritySelect(entry),
        ]
    )


class JudoMicroleakModeSelect(JudoSettingsEntity, SelectEntity):
    """Automatic microleakage check mode (read 65, write 5B)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = MICROLEAK_MODES

    def __init__(self, entry: JudoConfigEntry) -> None:
        super().__init__(entry, "microleak_mode")

    @property
    def current_option(self) -> str | None:
        mode = self.coordinator.data.microleak_mode
        if mode is None or mode >= len(MICROLEAK_MODES):
            return None
        return MICROLEAK_MODES[mode]

    async def async_select_option(self, option: str) -> None:
        try:
            await self.entry.runtime_data.client.async_set_microleak_mode(
                MICROLEAK_MODES.index(option)
            )
        except JudoError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()


class JudoWriteOnlySelect(JudoSettingsEntity, SelectEntity, RestoreEntity):
    """Base for settings the device accepts but never reports back."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: JudoConfigEntry, key: str, options: list[str]) -> None:
        super().__init__(entry, key)
        self._attr_options = options
        self._attr_current_option = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in self.options:
            self._attr_current_option = last_state.state

    async def async_select_option(self, option: str) -> None:
        try:
            await self._async_write(self.options.index(option))
        except JudoError as err:
            raise HomeAssistantError(str(err)) from err
        self._attr_current_option = option
        self.async_write_ha_state()

    async def _async_write(self, value: int) -> None:
        raise NotImplementedError


class JudoHolidayProfileSelect(JudoWriteOnlySelect):
    """Holiday profile (write 56)."""

    def __init__(self, entry: JudoConfigEntry) -> None:
        super().__init__(entry, "holiday_profile", list(HOLIDAY_PROFILES))

    async def _async_write(self, value: int) -> None:
        await self.entry.runtime_data.client.async_set_holiday_profile(value)


class JudoPrioritySelect(JudoWriteOnlySelect):
    """Priority between holiday mode and the special rule (write 6A)."""

    def __init__(self, entry: JudoConfigEntry) -> None:
        super().__init__(entry, "priority", list(PRIORITY_MODES))

    async def _async_write(self, value: int) -> None:
        await self.entry.runtime_data.client.async_set_priority(value)
