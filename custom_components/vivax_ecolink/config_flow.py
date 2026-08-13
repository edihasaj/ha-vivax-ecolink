"""Config flow for VIVAX EcoLink."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .cloud import AuthenticationError, CloudError, VivaxCloudClient
from .const import (
    CONF_APP_SECRET,
    CONF_APPLIANCE_CODE,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_NAME,
    CONF_ENCRYPTION_KEY,
    CONF_MODEL,
    CONF_REGION,
    CONF_SN8,
    DEFAULT_REGION,
    DOMAIN,
    REGION_EU,
    REGION_URLS,
    REGION_US,
)
from .models import ApplicationCredentials, VivaxDevice

SECRET_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

APPLICATION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_APP_SECRET): SECRET_SELECTOR,
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): SECRET_SELECTOR,
        vol.Required(CONF_ENCRYPTION_KEY): SECRET_SELECTOR,
    }
)

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): SECRET_SELECTOR,
        vol.Required(CONF_REGION, default=DEFAULT_REGION): SelectSelector(
            SelectSelectorConfig(
                options=[REGION_EU, REGION_US],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="region",
            )
        ),
    }
)


class VivaxEcoLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure VIVAX EcoLink."""

    VERSION = 3

    def __init__(self) -> None:
        self._application: dict[str, str] = {}
        self._account: dict[str, str] = {}
        self._devices: list[VivaxDevice] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect application credentials first."""
        if user_input is not None:
            self._application = dict(user_input)
            return await self.async_step_account()
        return self.async_show_form(step_id="user", data_schema=APPLICATION_SCHEMA)

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Authenticate the EcoLink account and discover devices."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._account = dict(user_input)
            application = ApplicationCredentials(
                app_secret=self._application[CONF_APP_SECRET],
                client_id=self._application[CONF_CLIENT_ID],
                client_secret=self._application[CONF_CLIENT_SECRET],
                encryption_key=self._application[CONF_ENCRYPTION_KEY],
            )
            client = VivaxCloudClient(
                async_get_clientsession(self.hass),
                REGION_URLS[self._account[CONF_REGION]],
                application,
            )
            try:
                await client.login(
                    self._account[CONF_EMAIL], self._account[CONF_PASSWORD]
                )
                self._devices = await client.devices()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except CloudError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            if not errors:
                if not self._devices:
                    errors["base"] = "no_devices"
                else:
                    return await self.async_step_device()
        return self.async_show_form(
            step_id="account", data_schema=ACCOUNT_SCHEMA, errors=errors
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select one appliance from the account."""
        choices = {device.appliance_code: device.name for device in self._devices}
        if user_input is not None:
            appliance_code = user_input[CONF_APPLIANCE_CODE]
            device = next(
                item for item in self._devices if item.appliance_code == appliance_code
            )
            await self.async_set_unique_id(
                f"{self._account[CONF_EMAIL].lower()}:{appliance_code}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="VIVAX EcoLink Heat Pump",
                data={
                    **self._application,
                    **self._account,
                    CONF_APPLIANCE_CODE: appliance_code,
                    CONF_DEVICE_NAME: device.name,
                    CONF_MODEL: device.model,
                    CONF_SN8: device.sn8,
                },
            )
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {vol.Required(CONF_APPLIANCE_CODE): vol.In(choices)}
            ),
        )
