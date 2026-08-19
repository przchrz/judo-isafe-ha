"""The JUDO ZEWA i-SAFE integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Capabilities, DeviceIdentity, JudoAuthError, JudoClient, JudoError
from .const import (
    CONF_FLOW_WINDOW,
    CONF_LIVE_INTERVAL,
    CONF_SETTINGS_INTERVAL,
    DEFAULT_FLOW_WINDOW,
    DEFAULT_LIVE_INTERVAL,
    DEFAULT_SETTINGS_INTERVAL,
)
from .coordinator import JudoLiveCoordinator, JudoSettingsCoordinator
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.VALVE,
]


@dataclass(slots=True)
class JudoRuntimeData:
    client: JudoClient
    identity: DeviceIdentity
    capabilities: Capabilities
    live: JudoLiveCoordinator
    settings: JudoSettingsCoordinator


type JudoConfigEntry = ConfigEntry[JudoRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: JudoConfigEntry) -> bool:
    """Set up a configured device."""
    client = JudoClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    try:
        identity = await client.async_get_identity()
        capabilities = await client.async_probe_capabilities()
    except JudoAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except JudoError as err:
        raise ConfigEntryNotReady(str(err)) from err

    _LOGGER.debug("Detected capabilities for %s: %s", identity.device_number, capabilities)

    options = entry.options
    live = JudoLiveCoordinator(
        hass,
        entry,
        client,
        capabilities,
        timedelta(seconds=options.get(CONF_LIVE_INTERVAL, DEFAULT_LIVE_INTERVAL)),
        timedelta(seconds=options.get(CONF_FLOW_WINDOW, DEFAULT_FLOW_WINDOW)),
    )
    settings = JudoSettingsCoordinator(
        hass,
        entry,
        client,
        capabilities,
        timedelta(seconds=options.get(CONF_SETTINGS_INTERVAL, DEFAULT_SETTINGS_INTERVAL)),
    )

    await live.async_config_entry_first_refresh()
    await settings.async_config_entry_first_refresh()

    entry.runtime_data = JudoRuntimeData(client, identity, capabilities, live, settings)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: JudoConfigEntry) -> bool:
    """Tear down a configured device."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: JudoConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
