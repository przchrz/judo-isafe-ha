"""Integration services for records that do not map onto entity state."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .api import JudoError
from .const import (
    DOMAIN,
    SERVICE_ACKNOWLEDGE_LEARN_MODE,
    SERVICE_CLEAR_ABSENCE_WINDOW,
    SERVICE_SET_ABSENCE_WINDOW,
)
from .models import AbsenceWindow

if TYPE_CHECKING:
    from . import JudoConfigEntry

ATTR_DEVICE_ID = "device_id"
ATTR_SLOT = "slot"
ATTR_ACCEPT = "accept"

SLOT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_SLOT): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
    }
)

SET_ABSENCE_WINDOW_SCHEMA = SLOT_SCHEMA.extend(
    {
        vol.Required("start_day"): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
        vol.Required("start_hour"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
        vol.Required("start_minute"): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
        vol.Required("stop_day"): vol.All(vol.Coerce(int), vol.Range(min=0, max=6)),
        vol.Required("stop_hour"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
        vol.Required("stop_minute"): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
    }
)

ACKNOWLEDGE_LEARN_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_ACCEPT): cv.boolean,
    }
)


def _resolve_entry(hass: HomeAssistant, device_id: str) -> JudoConfigEntry:
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(f"Unknown device id {device_id}")
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == DOMAIN:
            return entry
    raise ServiceValidationError(f"Device {device_id} is not a {DOMAIN} device")


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register the domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_ABSENCE_WINDOW):
        return

    async def _set_absence_window(call: ServiceCall) -> None:
        entry = _resolve_entry(hass, call.data[ATTR_DEVICE_ID])
        window = AbsenceWindow(
            start_day=call.data["start_day"],
            start_hour=call.data["start_hour"],
            start_minute=call.data["start_minute"],
            stop_day=call.data["stop_day"],
            stop_hour=call.data["stop_hour"],
            stop_minute=call.data["stop_minute"],
        )
        try:
            await entry.runtime_data.client.async_set_absence_window(call.data[ATTR_SLOT], window)
        except JudoError as err:
            raise HomeAssistantError(str(err)) from err

    async def _clear_absence_window(call: ServiceCall) -> None:
        entry = _resolve_entry(hass, call.data[ATTR_DEVICE_ID])
        try:
            await entry.runtime_data.client.async_clear_absence_window(call.data[ATTR_SLOT])
        except JudoError as err:
            raise HomeAssistantError(str(err)) from err

    async def _acknowledge_learn_mode(call: ServiceCall) -> None:
        entry = _resolve_entry(hass, call.data[ATTR_DEVICE_ID])
        try:
            await entry.runtime_data.client.async_acknowledge_learn_mode(call.data[ATTR_ACCEPT])
        except JudoError as err:
            raise HomeAssistantError(str(err)) from err
        await entry.runtime_data.settings.async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_SET_ABSENCE_WINDOW, _set_absence_window, SET_ABSENCE_WINDOW_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_ABSENCE_WINDOW, _clear_absence_window, SLOT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ACKNOWLEDGE_LEARN_MODE,
        _acknowledge_learn_mode,
        ACKNOWLEDGE_LEARN_MODE_SCHEMA,
    )
