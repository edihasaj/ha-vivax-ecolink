"""Verified Zone-1 power actions for the KJRH-120L."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import VivaxCoordinator
from .entity import VivaxEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Expose a power switch only for the exact verified controller model."""
    coordinator: VivaxCoordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.supports_power_control:
        async_add_entities([VivaxZone1PowerSwitch(coordinator)])


class VivaxZone1PowerSwitch(VivaxEntity, SwitchEntity):
    """Power the house heating/cooling zone, not domestic hot water."""

    _attr_translation_key = "zone1_power"
    _attr_icon = "mdi:heat-pump"

    def __init__(self, coordinator: VivaxCoordinator) -> None:
        super().__init__(coordinator, "zone1_power")

    @property
    def is_on(self) -> bool:
        """Use observed state, never the last requested command."""
        return self.coordinator.data.controller_power

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on Zone 1 without changing its target, mode or curve."""
        await self.coordinator.async_set_zone1_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off Zone 1 without cutting power to the controller itself."""
        await self.coordinator.async_set_zone1_power(False)
