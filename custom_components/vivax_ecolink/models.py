"""Data models for VIVAX EcoLink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ApplicationCredentials:
    """Credentials identifying the official VIVAX application."""

    app_secret: str
    client_id: str
    client_secret: str
    encryption_key: str


@dataclass(frozen=True, slots=True)
class VivaxDevice:
    """A cloud appliance associated with an EcoLink account."""

    appliance_code: str
    name: str
    model: str
    sn8: str

    @classmethod
    def from_cloud(cls, data: dict[str, Any]) -> VivaxDevice:
        """Create a device from a cloud appliance response."""
        code = str(data.get("applianceCode", ""))
        name = next(
            (
                str(data[key])
                for key in ("applianceName", "nickname", "name")
                if data.get(key)
            ),
            code,
        )
        return cls(
            appliance_code=code,
            name=name,
            model=str(data.get("modelNumber", "")),
            sn8=str(data.get("sn8", "")),
        )


@dataclass(frozen=True, slots=True)
class VivaxTelemetry:
    """Verified KJRH-120L monitoring values."""

    controller_power: bool
    operating_mode: str
    zone1_target: float
    compressor_frequency: int
    outdoor_temperature: float | None
    water_inlet_temperature: float | None
    water_outlet_temperature: float | None
    current_power: int
    total_electricity: int
    total_thermal_energy: int
    heating_electricity: int
    heating_thermal_energy: int
    cooling_electricity: int
    cooling_thermal_energy: int
    lifetime_cop: float | None
    heating_cop: float | None
