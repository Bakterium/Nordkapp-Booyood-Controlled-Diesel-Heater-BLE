"""Switch platform for Booyood / Nordkapp Parking Heater."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, CONF_NAME, DEFAULT_NAME, DOMAIN
from .coordinator import BooyoodCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Booyood switches from config entry."""
    coordinator: BooyoodCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        BooyoodPowerSwitch(coordinator, entry),
        BooyoodAutoStartStopSwitch(coordinator, entry),
    ])


class BooyoodPowerSwitch(CoordinatorEntity[BooyoodCoordinator], SwitchEntity):
    """Direct On / Off switch for the parking heater."""

    _attr_has_entity_name = True
    _attr_translation_key = "power"
    _attr_name = "Power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator: BooyoodCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._mac = entry.data[CONF_MAC]
        name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._attr_unique_id = f"{self._mac}_power"
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on heater."""
        await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off heater."""
        await self.coordinator.async_turn_off()


class BooyoodAutoStartStopSwitch(CoordinatorEntity[BooyoodCoordinator], SwitchEntity):
    """Switch to toggle Auto Start/Stop in temperature mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "auto_start_stop"
    _attr_name = "Auto Start/Stop (Thermostat)"
    _attr_icon = "mdi:autorenew"

    def __init__(self, coordinator: BooyoodCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._mac = entry.data[CONF_MAC]
        name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._attr_unique_id = f"{self._mac}_auto_start_stop"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=name,
            manufacturer="Nordkapp / Booyood",
            model=f"Air Gen 2 BLE ({coordinator.active_protocol.upper()})",
            connections={("bluetooth", self._mac)},
        )

    @property
    def is_on(self) -> bool:
        """Return True if auto start/stop is enabled."""
        return self.coordinator.status.auto_start_stop

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on auto start/stop."""
        await self.coordinator.async_set_auto_start_stop(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off auto start/stop."""
        await self.coordinator.async_set_auto_start_stop(False)
