"""Sensor platform for Booyood Parking Heater."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)

try:
    from homeassistant.const import UnitOfElectricPotential
    UNIT_VOLT = UnitOfElectricPotential.VOLT
except ImportError:
    try:
        from homeassistant.const import ELECTRIC_POTENTIAL_VOLT as UNIT_VOLT
    except ImportError:
        UNIT_VOLT = "V"
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, CONF_NAME, DEFAULT_NAME, DOMAIN, FAULT_CODES, MODE_NAMES, RUN_STEPS
from .coordinator import BooyoodCoordinator
from .protocol import HeaterStatus


@dataclass(frozen=True, kw_only=True)
class BooyoodSensorEntityDescription(SensorEntityDescription):
    """Describes Booyood sensor entity."""

    value_fn: Callable[[BooyoodCoordinator], Any]


SENSOR_DESCRIPTIONS: tuple[BooyoodSensorEntityDescription, ...] = (
    BooyoodSensorEntityDescription(
        key="voltage",
        name="Supply Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UNIT_VOLT,
        value_fn=lambda c: c.status.voltage,
    ),
    BooyoodSensorEntityDescription(
        key="heat_exchanger_temp",
        name="Heat Exchanger Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda c: c.status.heat_exchanger_temp,
    ),
    BooyoodSensorEntityDescription(
        key="ambient_temp",
        name="Ambient Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda c: c.status.ambient_temp,
    ),
    BooyoodSensorEntityDescription(
        key="current_gear",
        name="Current Gear",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan",
        value_fn=lambda c: c.status.current_gear,
    ),
    BooyoodSensorEntityDescription(
        key="fuel_consumption",
        name="Current Fuel Consumption",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fuel",
        native_unit_of_measurement="L/h",
        value_fn=lambda c: c.estimated_fuel_rate,
    ),
    BooyoodSensorEntityDescription(
        key="operating_step",
        name="Operating Phase",
        icon="mdi:progress-clock",
        value_fn=lambda c: RUN_STEPS.get(c.status.run_step, f"Step {c.status.run_step}"),
    ),
    BooyoodSensorEntityDescription(
        key="co_ppm",
        name="Carbon Monoxide",
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        value_fn=lambda c: c.status.co_ppm,
    ),
    BooyoodSensorEntityDescription(
        key="altitude",
        name="Altitude",
        device_class=getattr(SensorDeviceClass, "DISTANCE", None),
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        value_fn=lambda c: c.status.altitude,
    ),
    BooyoodSensorEntityDescription(
        key="remaining_runtime",
        name="Remaining Runtime",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda c: c.status.remaining_minutes,
    ),
    BooyoodSensorEntityDescription(
        key="mode",
        name="Operating Mode",
        icon="mdi:tune-variant",
        value_fn=lambda c: MODE_NAMES.get(
            c.effective_mode if c.status.is_on else 0,
            f"Mode {c.status.run_mode}"
        ),
    ),
    BooyoodSensorEntityDescription(
        key="error_code",
        name="Fault Status",
        icon="mdi:alert-circle-outline",
        value_fn=lambda c: FAULT_CODES.get(c.status.error_code, f"Error {c.status.error_code}"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Booyood sensors from config entry."""
    coordinator: BooyoodCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BooyoodSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class BooyoodSensor(CoordinatorEntity[BooyoodCoordinator], SensorEntity):
    """Representation of a Booyood sensor."""

    entity_description: BooyoodSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BooyoodCoordinator,
        entry: ConfigEntry,
        description: BooyoodSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._mac = entry.data[CONF_MAC]
        name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._attr_unique_id = f"{self._mac}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=name,
            manufacturer="Nordkapp / Booyood",
            model=f"Air Gen 2 BLE ({coordinator.active_protocol.upper()})",
            connections={("bluetooth", self._mac)},
        )

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def available(self) -> bool:
        """Return True if sensor is available.

        CO sensor is unavailable if the hardware CO detector is not installed.
        Remaining runtime is only available when the heater is running and an active timer is set.
        """
        if not super().available:
            return False
        if self.entity_description.key == "co_ppm":
            return self.coordinator.status.co_ppm is not None
        if self.entity_description.key == "remaining_runtime":
            return bool(self.coordinator.status.is_on and self.coordinator.status.remaining_minutes is not None)
        return True


