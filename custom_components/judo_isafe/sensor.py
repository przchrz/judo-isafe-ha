"""Sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LiveData, SettingsData
from .entity import JudoLiveEntity, JudoSettingsEntity
from .models import LEAK_CAUSE_OPTIONS, StatusBit, leak_cause

if TYPE_CHECKING:
    from . import JudoConfigEntry


@dataclass(frozen=True, kw_only=True)
class JudoLiveSensorDescription(SensorEntityDescription):
    value_fn: Callable[[LiveData], float | str | None]
    requires_status: bool = False


@dataclass(frozen=True, kw_only=True)
class JudoSettingsSensorDescription(SensorEntityDescription):
    value_fn: Callable[[SettingsData], float | datetime | None]


LIVE_SENSORS: tuple[JudoLiveSensorDescription, ...] = (
    JudoLiveSensorDescription(
        key="total_water",
        translation_key="total_water",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        value_fn=lambda data: data.total_water_l,
    ),
    JudoLiveSensorDescription(
        key="water_flow",
        translation_key="water_flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        suggested_display_precision=2,
        value_fn=lambda data: data.flow_l_per_min,
    ),
    JudoLiveSensorDescription(
        key="leak_cause",
        translation_key="leak_cause",
        device_class=SensorDeviceClass.ENUM,
        options=LEAK_CAUSE_OPTIONS,
        requires_status=True,
        value_fn=lambda data: leak_cause(data.status or StatusBit(0)),
    ),
)

SETTINGS_SENSORS: tuple[JudoSettingsSensorDescription, ...] = (
    JudoSettingsSensorDescription(
        key="learn_mode_remaining_water",
        translation_key="learn_mode_remaining_water",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=0,
        value_fn=lambda data: data.learn_mode.remaining_water_l if data.learn_mode else None,
    ),
    JudoSettingsSensorDescription(
        key="operating_days",
        translation_key="operating_days",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.operating_days,
    ),
    JudoSettingsSensorDescription(
        key="device_time",
        translation_key="device_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        # The device clock is naive local time; anchor it to the HA time zone.
        value_fn=lambda data: (
            dt_util.as_utc(data.device_time.replace(tzinfo=dt_util.get_default_time_zone()))
            if data.device_time
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JudoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors supported by this unit."""
    has_status = entry.runtime_data.capabilities.status
    entities: list[SensorEntity] = [
        JudoLiveSensor(entry, description)
        for description in LIVE_SENSORS
        if has_status or not description.requires_status
    ]
    entities.extend(JudoSettingsSensor(entry, description) for description in SETTINGS_SENSORS)
    async_add_entities(entities)


class JudoLiveSensor(JudoLiveEntity, SensorEntity):
    """A measurement from the fast coordinator."""

    entity_description: JudoLiveSensorDescription

    def __init__(self, entry: JudoConfigEntry, description: JudoLiveSensorDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | str | None:
        return self.entity_description.value_fn(self.coordinator.data)


class JudoSettingsSensor(JudoSettingsEntity, SensorEntity):
    """A value from the slow coordinator."""

    entity_description: JudoSettingsSensorDescription

    def __init__(self, entry: JudoConfigEntry, description: JudoSettingsSensorDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | datetime | None:
        return self.entity_description.value_fn(self.coordinator.data)
