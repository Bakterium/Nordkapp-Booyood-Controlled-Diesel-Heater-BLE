"""Binary sensor platform for Booyood Parking Heater."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, CONF_NAME, DEFAULT_NAME, DOMAIN
from .coordinator import BooyoodCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Booyood binary sensors from config entry."""
    coordinator: BooyoodCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BooyoodRunningBinarySensor(coordinator, entry),
            BooyoodProblemBinarySensor(coordinator, entry),
        ]
    )


class BooyoodRunningBinarySensor(CoordinatorEntity[BooyoodCoordinator], BinarySensorEntity):
    """Indicates if the parking heater is actively running."""

    _attr_has_entity_name = True
    _attr_name = "Heating Running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: BooyoodCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._mac = entry.data[CONF_MAC]
        name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._attr_unique_id = f"{self._mac}_running"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=name,
            manufacturer="Nordkapp / Booyood",
            model=f"Air Gen 2 BLE ({coordinator.active_protocol.upper()})",
            connections={("bluetooth", self._mac)},
        )

    @property
    def is_on(self) -> bool:
        """Return True if heater is on."""
        return self.coordinator.status.is_on


class BooyoodProblemBinarySensor(CoordinatorEntity[BooyoodCoordinator], BinarySensorEntity):
    """Indicates if there is an error on the heater."""

    _attr_has_entity_name = True
    _attr_name = "Problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: BooyoodCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._mac = entry.data[CONF_MAC]
        name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._attr_unique_id = f"{self._mac}_problem"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=name,
            manufacturer="Nordkapp / Booyood",
            model=f"Air Gen 2 BLE ({coordinator.active_protocol.upper()})",
            connections={("bluetooth", self._mac)},
        )

    @property
    def is_on(self) -> bool:
        """Return True if there is an error code."""
        return self.coordinator.status.error_code > 0
