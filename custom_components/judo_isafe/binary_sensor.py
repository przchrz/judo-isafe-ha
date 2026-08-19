"""Binary sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LiveData
from .entity import JudoLiveEntity
from .models import StatusBit

if TYPE_CHECKING:
    from . import JudoConfigEntry


@dataclass(frozen=True, kw_only=True)
class JudoBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a binary sensor and how to derive it from live data."""

    value_fn: Callable[[LiveData], bool]
    requires_status: bool = True


def _bit(mask: StatusBit) -> Callable[[LiveData], bool]:
    return lambda data: bool((data.status or StatusBit(0)) & mask)


BINARY_SENSORS: tuple[JudoBinarySensorDescription, ...] = (
    JudoBinarySensorDescription(
        key="water_flowing",
        translation_key="water_flowing",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda data: data.is_flowing,
        requires_status=False,
    ),
    JudoBinarySensorDescription(
        key="leakage",
        translation_key="leakage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_bit(StatusBit.LEAKAGE),
    ),
    JudoBinarySensorDescription(
        key="flow_limit_exceeded",
        translation_key="flow_limit_exceeded",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_bit(StatusBit.FLOW_EXCEEDED),
    ),
    JudoBinarySensorDescription(
        key="volume_limit_exceeded",
        translation_key="volume_limit_exceeded",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_bit(StatusBit.VOLUME_EXCEEDED),
    ),
    JudoBinarySensorDescription(
        key="duration_limit_exceeded",
        translation_key="duration_limit_exceeded",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_bit(StatusBit.DURATION_EXCEEDED),
    ),
    JudoBinarySensorDescription(
        key="microleak_detected",
        translation_key="microleak_detected",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_bit(StatusBit.MICROLEAK_NOTIFY | StatusBit.MICROLEAK_NOTIFY_AND_CLOSE),
    ),
    JudoBinarySensorDescription(
        key="no_flow_15_days",
        translation_key="no_flow_15_days",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_bit(StatusBit.NO_FLOW_15_DAYS),
    ),
    JudoBinarySensorDescription(
        key="sleep_mode",
        translation_key="sleep_mode",
        value_fn=_bit(StatusBit.SLEEP_MODE),
    ),
    JudoBinarySensorDescription(
        key="holiday_mode",
        translation_key="holiday_mode",
        value_fn=_bit(StatusBit.HOLIDAY_MODE),
    ),
    JudoBinarySensorDescription(
        key="learn_mode_active",
        translation_key="learn_mode_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_bit(StatusBit.LEARN_MODE_ACTIVE),
    ),
    JudoBinarySensorDescription(
        key="special_rule_active",
        translation_key="special_rule_active",
        value_fn=_bit(StatusBit.SPECIAL_RULE_ACTIVE),
    ),
    JudoBinarySensorDescription(
        key="homing",
        translation_key="homing",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_bit(StatusBit.HOMING),
    ),
    JudoBinarySensorDescription(
        key="closed_manually",
        translation_key="closed_manually",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_bit(StatusBit.CLOSED_MANUAL_OR_U3),
    ),
    JudoBinarySensorDescription(
        key="closed_via_ls_input",
        translation_key="closed_via_ls_input",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_bit(StatusBit.CLOSED_VIA_LS_INPUT),
    ),
    JudoBinarySensorDescription(
        key="sleep_via_ls_input",
        translation_key="sleep_via_ls_input",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_bit(StatusBit.SLEEP_VIA_LS_INPUT),
    ),
    JudoBinarySensorDescription(
        key="microleak_test_impossible",
        translation_key="microleak_test_impossible",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_bit(StatusBit.MICROLEAK_TEST_IMPOSSIBLE),
    ),
    JudoBinarySensorDescription(
        key="learn_mode_finished",
        translation_key="learn_mode_finished",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_bit(StatusBit.LEARN_MODE_FINISHED),
    ),
    JudoBinarySensorDescription(
        key="learn_limits_exceeded",
        translation_key="learn_limits_exceeded",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_bit(
            StatusBit.LEARN_VOLUME_EXCEEDED
            | StatusBit.LEARN_FLOW_EXCEEDED
            | StatusBit.LEARN_DURATION_EXCEEDED
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JudoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors supported by this unit."""
    has_status = entry.runtime_data.capabilities.status
    async_add_entities(
        JudoBinarySensor(entry, description)
        for description in BINARY_SENSORS
        if has_status or not description.requires_status
    )


class JudoBinarySensor(JudoLiveEntity, BinarySensorEntity):
    """A boolean derived from the status word or the flow tracker."""

    entity_description: JudoBinarySensorDescription

    def __init__(self, entry: JudoConfigEntry, description: JudoBinarySensorDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)
