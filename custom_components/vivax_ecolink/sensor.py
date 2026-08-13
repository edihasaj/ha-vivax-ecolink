"""Sensors exposed by VIVAX EcoLink."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import VivaxCoordinator
from .entity import VivaxEntity
from .models import VivaxTelemetry


@dataclass(frozen=True, kw_only=True)
class VivaxSensorDescription(SensorEntityDescription):
    """Describe one telemetry-backed sensor."""

    value_fn: Callable[[VivaxTelemetry], str | int | float | None]


DESCRIPTIONS = (
    VivaxSensorDescription(
        key="zone1_target",
        translation_key="zone1_target",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.zone1_target,
    ),
    VivaxSensorDescription(
        key="controller_power",
        translation_key="controller_power",
        icon="mdi:power",
        value_fn=lambda data: "on" if data.controller_power else "off",
    ),
    VivaxSensorDescription(
        key="operating_mode",
        translation_key="operating_mode",
        icon="mdi:heat-pump",
        value_fn=lambda data: data.operating_mode,
    ),
    VivaxSensorDescription(
        key="compressor_frequency",
        translation_key="compressor_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.compressor_frequency,
    ),
    VivaxSensorDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.outdoor_temperature,
    ),
    VivaxSensorDescription(
        key="water_inlet_temperature",
        translation_key="water_inlet_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.water_inlet_temperature,
    ),
    VivaxSensorDescription(
        key="water_outlet_temperature",
        translation_key="water_outlet_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.water_outlet_temperature,
    ),
    VivaxSensorDescription(
        key="current_power",
        translation_key="current_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.current_power,
    ),
    VivaxSensorDescription(
        key="total_electricity",
        translation_key="total_electricity",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_electricity,
    ),
    VivaxSensorDescription(
        key="total_thermal_energy",
        translation_key="total_thermal_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_thermal_energy,
    ),
    VivaxSensorDescription(
        key="heating_electricity",
        translation_key="heating_electricity",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.heating_electricity,
    ),
    VivaxSensorDescription(
        key="heating_thermal_energy",
        translation_key="heating_thermal_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.heating_thermal_energy,
    ),
    VivaxSensorDescription(
        key="cooling_electricity",
        translation_key="cooling_electricity",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.cooling_electricity,
    ),
    VivaxSensorDescription(
        key="cooling_thermal_energy",
        translation_key="cooling_thermal_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.cooling_thermal_energy,
    ),
    VivaxSensorDescription(
        key="lifetime_cop",
        translation_key="lifetime_cop",
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.lifetime_cop,
    ),
    VivaxSensorDescription(
        key="heating_cop",
        translation_key="heating_cop",
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.heating_cop,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all verified VIVAX sensors."""
    coordinator: VivaxCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        VivaxSensor(coordinator, description) for description in DESCRIPTIONS
    )


class VivaxSensor(VivaxEntity, SensorEntity):
    """One VIVAX telemetry sensor."""

    entity_description: VivaxSensorDescription

    def __init__(
        self, coordinator: VivaxCoordinator, description: VivaxSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        """Return the latest decoded value."""
        return self.entity_description.value_fn(self.coordinator.data)
