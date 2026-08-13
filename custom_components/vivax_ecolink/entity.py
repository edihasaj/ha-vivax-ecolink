"""Shared VIVAX EcoLink entity helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MODEL, CONF_SN8, DOMAIN
from .coordinator import VivaxCoordinator


class VivaxEntity(CoordinatorEntity[VivaxCoordinator]):
    """Base entity grouped under the VIVAX heat pump device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VivaxCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.appliance_code}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.appliance_code)},
            name="VIVAX EcoLink Heat Pump",
            manufacturer="VIVAX",
            model=coordinator.entry.data.get(CONF_MODEL) or "KJRH-120L",
            hw_version=coordinator.entry.data.get(CONF_SN8) or None,
        )
