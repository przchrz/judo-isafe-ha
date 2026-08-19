"""Config and options flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JudoAuthError, JudoClient, JudoConnectionError, JudoError
from .const import (
    CONF_FLOW_WINDOW,
    CONF_LIVE_INTERVAL,
    CONF_SETTINGS_INTERVAL,
    DEFAULT_FLOW_WINDOW,
    DEFAULT_LIVE_INTERVAL,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_SETTINGS_INTERVAL,
    DEFAULT_USERNAME,
    DEVICE_TYPE_ISAFE,
    DOMAIN,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
    }
)


class JudoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = JudoClient(
                async_get_clientsession(self.hass),
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                identity = await client.async_get_identity()
            except JudoAuthError:
                errors["base"] = "invalid_auth"
            except JudoConnectionError:
                errors["base"] = "cannot_connect"
            except JudoError:
                errors["base"] = "unknown"
            else:
                if identity.device_type != DEVICE_TYPE_ISAFE:
                    errors["base"] = "unsupported_device"
                else:
                    await self.async_set_unique_id(str(identity.device_number))
                    self._abort_if_unique_id_configured(updates=user_input)
                    return self.async_create_entry(
                        title=f"ZEWA i-SAFE {identity.device_number}", data=user_input
                    )

        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return JudoOptionsFlow()


class JudoOptionsFlow(OptionsFlow):
    """Tune polling behaviour after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LIVE_INTERVAL,
                    default=options.get(CONF_LIVE_INTERVAL, DEFAULT_LIVE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=600)),
                vol.Required(
                    CONF_SETTINGS_INTERVAL,
                    default=options.get(CONF_SETTINGS_INTERVAL, DEFAULT_SETTINGS_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
                vol.Required(
                    CONF_FLOW_WINDOW,
                    default=options.get(CONF_FLOW_WINDOW, DEFAULT_FLOW_WINDOW),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=1800)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
