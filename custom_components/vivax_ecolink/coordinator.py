"""Data coordinator for VIVAX EcoLink."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud import AuthenticationError, CloudError, VivaxCloudClient
from .const import (
    CONF_APPLIANCE_CODE,
    CONF_REGION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REGION_URLS,
)
from .models import VivaxTelemetry
from .protocol import ProtocolError, decode_telemetry
from .vendor import APPLICATION


class VivaxCoordinator(DataUpdateCoordinator[VivaxTelemetry]):
    """Poll one VIVAX KJRH-120L through the EcoLink cloud."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self.appliance_code = str(entry.data[CONF_APPLIANCE_CODE])
        self.client = VivaxCloudClient(
            async_get_clientsession(hass),
            REGION_URLS[entry.data[CONF_REGION]],
            APPLICATION,
        )

    async def _login(self) -> None:
        await self.client.login(
            self.entry.data[CONF_EMAIL], self.entry.data[CONF_PASSWORD]
        )

    async def _poll(self) -> VivaxTelemetry:
        status = await self.client.payload(self.appliance_code, 0x01)
        unit = await self.client.payload(self.appliance_code, 0x10)
        return decode_telemetry(status, unit)

    async def _async_update_data(self) -> VivaxTelemetry:
        try:
            if not self.client.authenticated:
                await self._login()
            return await self._poll()
        except AuthenticationError:
            try:
                await self._login()
                return await self._poll()
            except (AuthenticationError, CloudError, ProtocolError) as err:
                raise UpdateFailed("EcoLink authentication refresh failed") from err
        except (CloudError, ProtocolError) as err:
            raise UpdateFailed("Unable to update VIVAX EcoLink") from err
