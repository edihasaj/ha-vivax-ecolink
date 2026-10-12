"""Constants for VIVAX EcoLink."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "vivax_ecolink"
PLATFORMS: Final = ["sensor", "switch"]

CONF_APPLIANCE_CODE: Final = "appliance_code"
CONF_APP_SECRET: Final = "app_secret"
CONF_CLIENT_ID: Final = "client_id"
CONF_CLIENT_SECRET: Final = "client_secret"
CONF_ENCRYPTION_KEY: Final = "encryption_key"
CONF_DEVICE_NAME: Final = "device_name"
CONF_MODEL: Final = "model"
CONF_REGION: Final = "region"
CONF_SN8: Final = "sn8"

REGION_EU: Final = "eu"
REGION_US: Final = "us"
DEFAULT_REGION: Final = REGION_EU
REGION_URLS: Final = {
    REGION_EU: "https://eu.dollin.net",
    REGION_US: "https://us.dollin.net",
}

APP_ID: Final = "7501"
APP_KEY: Final = "meicloud"
APP_VERSION: Final = "1.0.2"
DEFAULT_SCAN_INTERVAL: Final = 60
SUPPORTED_SN8: Final = "17100003"

SECRET_FIELDS: Final = {
    CONF_APP_SECRET,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENCRYPTION_KEY,
    "password",
}
