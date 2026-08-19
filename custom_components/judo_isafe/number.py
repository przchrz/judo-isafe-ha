"""Number platform.

Absence limits (5E/5F) read back from the device. The leakage limits are
written as one combined record via 50, and several firmware revisions never
answer the matching read (68), so those entities fall back to restoring their
last value from Home Assistant.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import JudoError
from .coordinator import SettingsData
from .entity import JudoSettingsEntity
from .models import AbsenceLimits, LeakageSettings

if TYPE_CHECKING:
    from . import JudoConfigEntry

LITERS_PER_HOUR = UnitOfVolumeFlowRate.LITERS_PER_HOUR


@dataclass(frozen=True, kw_only=True)
class JudoNumberDescription(NumberEntityDescription):
    """Describes a writable numeric setting."""

    field: str
    read_fn: Callable[[SettingsData], int | None]
    write_fn: Callable[[JudoConfigEntry, SettingsData, int], object]


def _write_absence(entry: JudoConfigEntry, data: SettingsData, field: str, value: int):
    current = data.absence_limits or AbsenceLimits(0, 0, 0)
    return entry.runtime_data.client.async_set_absence_limits(replace(current, **{field: value}))


def _write_leakage(entry: JudoConfigEntry, data: SettingsData, field: str, value: int):
    # Command 50 rewrites all four fields, so unchanged ones must be resent.
    current = data.leakage_settings or LeakageSettings(0, 0, 0, 0)
    return entry.runtime_data.client.async_set_leakage_settings(replace(current, **{field: value}))


ABSENCE_NUMBERS: tuple[JudoNumberDescription, ...] = (
    JudoNumberDescription(
        key="absence_max_flow",
        translation_key="absence_max_flow",
        native_unit_of_measurement=LITERS_PER_HOUR,
        native_min_value=0,
        native_max_value=5000,
        native_step=100,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        field="max_flow_lph",
        read_fn=lambda data: data.absence_limits.max_flow_lph if data.absence_limits else None,
        write_fn=lambda entry, data, value: _write_absence(entry, data, "max_flow_lph", value),
    ),
    JudoNumberDescription(
        key="absence_max_volume",
        translation_key="absence_max_volume",
        device_class=NumberDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        native_min_value=0,
        native_max_value=3000,
        native_step=5,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        field="max_volume_l",
        read_fn=lambda data: data.absence_limits.max_volume_l if data.absence_limits else None,
        write_fn=lambda entry, data, value: _write_absence(entry, data, "max_volume_l", value),
    ),
    JudoNumberDescription(
        key="absence_max_duration",
        translation_key="absence_max_duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=0,
        native_max_value=600,
        native_step=5,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        field="max_duration_min",
        read_fn=lambda data: data.absence_limits.max_duration_min if data.absence_limits else None,
        write_fn=lambda entry, data, value: _write_absence(entry, data, "max_duration_min", value),
    ),
)

LEAKAGE_NUMBERS: tuple[JudoNumberDescription, ...] = (
    JudoNumberDescription(
        key="max_flow",
        translation_key="max_flow",
        native_unit_of_measurement=LITERS_PER_HOUR,
        native_min_value=0,
        native_max_value=5000,
        native_step=100,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        field="max_flow_lph",
        read_fn=lambda data: data.leakage_settings.max_flow_lph if data.leakage_settings else None,
        write_fn=lambda entry, data, value: _write_leakage(entry, data, "max_flow_lph", value),
    ),
    JudoNumberDescription(
        key="max_volume",
        translation_key="max_volume",
        device_class=NumberDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        native_min_value=0,
        native_max_value=3000,
        native_step=5,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        field="max_volume_l",
        read_fn=lambda data: data.leakage_settings.max_volume_l if data.leakage_settings else None,
        write_fn=lambda entry, data, value: _write_leakage(entry, data, "max_volume_l", value),
    ),
    JudoNumberDescription(
        key="max_duration",
        translation_key="max_duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=0,
        native_max_value=300,
        native_step=5,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        field="max_duration_min",
        read_fn=lambda data: (
            data.leakage_settings.max_duration_min if data.leakage_settings else None
        ),
        write_fn=lambda entry, data, value: _write_leakage(entry, data, "max_duration_min", value),
    ),
)

SLEEP_DURATION = JudoNumberDescription(
    key="sleep_duration",
    translation_key="sleep_duration",
    native_unit_of_measurement=UnitOfTime.HOURS,
    native_min_value=1,
    native_max_value=10,
    native_step=1,
    mode=NumberMode.BOX,
    entity_category=EntityCategory.CONFIG,
    field="sleep_duration_h",
    read_fn=lambda data: data.sleep_duration_h,
    write_fn=lambda entry, data, value: entry.runtime_data.client.async_set_sleep_duration_h(value),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JudoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the writable numeric settings."""
    capabilities = entry.runtime_data.capabilities
    entities = [
        JudoNumber(entry, description, readable=capabilities.absence_limits)
        for description in ABSENCE_NUMBERS
    ]
    entities.extend(
        JudoNumber(entry, description, readable=capabilities.leakage_settings_read)
        for description in LEAKAGE_NUMBERS
    )
    entities.append(JudoNumber(entry, SLEEP_DURATION, readable=capabilities.sleep_duration_read))
    async_add_entities(entities)


class JudoNumber(JudoSettingsEntity, RestoreNumber):
    """A numeric setting, read from the device when the firmware allows it."""

    entity_description: JudoNumberDescription

    def __init__(
        self,
        entry: JudoConfigEntry,
        description: JudoNumberDescription,
        *,
        readable: bool,
    ) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description
        self._readable = readable
        self._restored_value: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._readable:
            return
        last = await self.async_get_last_number_data()
        if last is not None:
            self._restored_value = last.native_value

    @property
    def native_value(self) -> float | None:
        if self._readable:
            return self.entity_description.read_fn(self.coordinator.data)
        return self._restored_value

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.entity_description.write_fn(self.entry, self.coordinator.data, int(value))
        except JudoError as err:
            raise HomeAssistantError(str(err)) from err
        self._restored_value = value
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
