"""Button platform.

The device exposes its actions as fire-and-forget commands with no read-back,
so they are modelled as buttons rather than switches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import JudoError
from .const import Command
from .entity import JudoLiveEntity

if TYPE_CHECKING:
    from . import JudoConfigEntry


@dataclass(frozen=True, kw_only=True)
class JudoButtonDescription(ButtonEntityDescription):
    command: Command
    # Valve control is a button only when no status read-back exists to back a
    # proper valve entity.
    only_without_status: bool = False


BUTTONS: tuple[JudoButtonDescription, ...] = (
    JudoButtonDescription(
        key="valve_close",
        translation_key="valve_close",
        icon="mdi:water-pump-off",
        command=Command.VALVE_CLOSE,
        only_without_status=True,
    ),
    JudoButtonDescription(
        key="valve_open",
        translation_key="valve_open",
        icon="mdi:water-pump",
        command=Command.VALVE_OPEN,
        only_without_status=True,
    ),
    JudoButtonDescription(
        key="sleep_mode_start",
        translation_key="sleep_mode_start",
        icon="mdi:sleep",
        command=Command.SLEEP_START,
    ),
    JudoButtonDescription(
        key="sleep_mode_end",
        translation_key="sleep_mode_end",
        icon="mdi:sleep-off",
        command=Command.SLEEP_END,
    ),
    JudoButtonDescription(
        key="holiday_mode_start",
        translation_key="holiday_mode_start",
        icon="mdi:home-export-outline",
        command=Command.HOLIDAY_START,
    ),
    JudoButtonDescription(
        key="holiday_mode_end",
        translation_key="holiday_mode_end",
        icon="mdi:home-import-outline",
        command=Command.HOLIDAY_END,
    ),
    JudoButtonDescription(
        key="microleak_test",
        translation_key="microleak_test",
        icon="mdi:pipe-leak",
        command=Command.MICROLEAK_TEST,
    ),
    JudoButtonDescription(
        key="learn_mode_start",
        translation_key="learn_mode_start",
        icon="mdi:school",
        command=Command.LEARN_MODE_START,
    ),
    JudoButtonDescription(
        key="reset_message",
        translation_key="reset_message",
        icon="mdi:lock-reset",
        command=Command.RESET_MESSAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JudoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the action buttons."""
    has_status = entry.runtime_data.capabilities.status
    async_add_entities(
        JudoButton(entry, description)
        for description in BUTTONS
        if not (description.only_without_status and has_status)
    )


class JudoButton(JudoLiveEntity, ButtonEntity):
    """Sends a single command."""

    entity_description: JudoButtonDescription

    def __init__(self, entry: JudoConfigEntry, description: JudoButtonDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        try:
            await self.entry.runtime_data.client.async_command(self.entity_description.command)
        except JudoError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
