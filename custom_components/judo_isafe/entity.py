"""Shared entity base classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JudoLiveCoordinator, JudoSettingsCoordinator

if TYPE_CHECKING:
    from . import JudoConfigEntry


def build_device_info(entry: JudoConfigEntry) -> DeviceInfo:
    identity = entry.runtime_data.identity
    return DeviceInfo(
        identifiers={(DOMAIN, str(identity.device_number))},
        manufacturer="JUDO",
        model="ZEWA i-SAFE",
        name=entry.title,
        serial_number=str(identity.device_number),
        sw_version=identity.sw_version,
    )


class JudoLiveEntity(CoordinatorEntity[JudoLiveCoordinator]):
    """Entity backed by the fast coordinator."""

    _attr_has_entity_name = True

    def __init__(self, entry: JudoConfigEntry, key: str) -> None:
        super().__init__(entry.runtime_data.live)
        self.entry = entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = build_device_info(entry)


class JudoSettingsEntity(CoordinatorEntity[JudoSettingsCoordinator]):
    """Entity backed by the slow coordinator."""

    _attr_has_entity_name = True

    def __init__(self, entry: JudoConfigEntry, key: str) -> None:
        super().__init__(entry.runtime_data.settings)
        self.entry = entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = build_device_info(entry)
