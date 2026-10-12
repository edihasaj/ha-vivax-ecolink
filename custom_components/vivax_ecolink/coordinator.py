"""Data coordinator for VIVAX EcoLink."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TypeVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud import AuthenticationError, CloudError, VivaxCloudClient
from .const import (
    CONF_APPLIANCE_CODE,
    CONF_MODEL,
    CONF_REGION,
    CONF_SN8,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REGION_URLS,
    SUPPORTED_SN8,
)
from .control import async_set_zone1_power, validate_power_status
from .models import VivaxTelemetry
from .protocol import ProtocolError, decode_telemetry
from .vendor import APPLICATION

_LOGGER = logging.getLogger(__name__)
_Result = TypeVar("_Result")


class VivaxCoordinator(DataUpdateCoordinator[VivaxTelemetry]):
    """Poll one VIVAX KJRH-120L through the EcoLink cloud."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self._io_lock = asyncio.Lock()
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

    @property
    def supports_power_control(self) -> bool:
        """Never enable writes for a missing or different model code."""
        return self.entry.data.get(CONF_SN8) == SUPPORTED_SN8

    async def async_discover_model(self) -> None:
        """Backfill a prototype entry's missing model through the owned device."""
        if self.entry.data.get(CONF_SN8):
            return
        try:
            async with self._io_lock:
                devices = await self._with_auth(self.client.devices)
        except CloudError:
            _LOGGER.warning("EcoLink model discovery failed; power control unavailable")
            return
        for device in devices:
            if device.appliance_code == self.appliance_code and device.sn8:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_SN8: device.sn8,
                        CONF_MODEL: device.model,
                    },
                )
                return

    async def _with_auth(self, operation: Callable[[], Awaitable[_Result]]) -> _Result:
        """Retry only an explicit authentication rejection, not an uncertain write."""
        if not self.client.authenticated:
            await self._login()
        try:
            return await operation()
        except AuthenticationError:
            await self._login()
            return await operation()

    async def _status(self) -> bytes:
        status = await self._with_auth(
            lambda: self.client.payload(self.appliance_code, 0x01)
        )
        if self.supports_power_control:
            validate_power_status(status)
        return status

    async def _telemetry(self, status: bytes) -> VivaxTelemetry:
        unit = await self._with_auth(
            lambda: self.client.payload(self.appliance_code, 0x10)
        )
        return decode_telemetry(status, unit)

    async def _poll(self) -> VivaxTelemetry:
        return await self._telemetry(await self._status())

    async def async_set_zone1_power(self, enabled: bool) -> None:
        """Run a serialized, verified action; never publish optimistic state."""
        if not self.supports_power_control:
            raise HomeAssistantError("Power control is not verified for this model")
        if type(enabled) is not bool:
            raise HomeAssistantError("Zone-1 power must be a boolean")
        try:
            async with self._io_lock:
                status = await async_set_zone1_power(
                    self._status,
                    lambda value: self._with_auth(
                        lambda: self.client.set_zone1_power(self.appliance_code, value)
                    ),
                    enabled,
                )
                self.async_set_updated_data(await self._telemetry(status))
        except (CloudError, ProtocolError) as err:
            # An uncertain action must still refresh observed state. No retry or
            # automatic inverse command: another client may have changed it.
            await self.async_request_refresh()
            raise HomeAssistantError(
                "Unable to confirm heat-pump power; check EcoLink before retrying"
            ) from err

    async def _async_update_data(self) -> VivaxTelemetry:
        try:
            async with self._io_lock:
                return await self._poll()
        except (CloudError, ProtocolError) as err:
            raise UpdateFailed("Unable to update VIVAX EcoLink") from err
