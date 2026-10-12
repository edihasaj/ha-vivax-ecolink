"""VIVAX EcoLink integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_APP_SECRET,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENCRYPTION_KEY,
    DOMAIN,
    PLATFORMS,
)

LEGACY_APPLICATION_FIELDS = {
    CONF_APP_SECRET,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENCRYPTION_KEY,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VIVAX EcoLink from a config entry."""
    from .coordinator import VivaxCoordinator

    coordinator = VivaxCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_discover_model()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a VIVAX EcoLink config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate private prototype entries to the public package format."""
    data = {
        key: value
        for key, value in entry.data.items()
        if key not in LEGACY_APPLICATION_FIELDS
    }
    if entry.version < 4 or entry.title != "VIVAX EcoLink Heat Pump":
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            title="VIVAX EcoLink Heat Pump",
            version=4,
        )
    return True
