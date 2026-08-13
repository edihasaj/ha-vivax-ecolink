"""Lightweight Home Assistant stubs for protocol-only unit tests."""

from __future__ import annotations

import sys
from types import ModuleType

homeassistant = ModuleType("homeassistant")
config_entries = ModuleType("homeassistant.config_entries")
core = ModuleType("homeassistant.core")
config_entries.ConfigEntry = object
core.HomeAssistant = object

sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.config_entries", config_entries)
sys.modules.setdefault("homeassistant.core", core)
