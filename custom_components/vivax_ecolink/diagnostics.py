"""Diagnostics support for VIVAX EcoLink."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import SECRET_FIELDS


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted config-entry diagnostics."""
    return {
        "entry": async_redact_data(dict(entry.data), SECRET_FIELDS),
        "version": entry.version,
    }
