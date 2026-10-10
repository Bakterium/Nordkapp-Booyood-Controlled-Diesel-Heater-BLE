"""Button platform for Booyood / Nordkapp Parking Heater."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
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
    """Set up Booyood buttons from config entry."""
    coordinator: BooyoodCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BooyoodSyncTimeButton(coordinator, entry)])


class BooyoodSyncTimeButton(CoordinatorEntity[BooyoodCoordinator], ButtonEntity):
    """Button to synchronize the heater's clock with Home Assistant time."""

    _attr_has_entity_name = True
    _attr_name = "Synchronize Clock"
    _attr_icon = "mdi:clock-sync-outline"

    def __init__(self, coordinator: BooyoodCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._mac = entry.data[CONF_MAC]
        name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._attr_unique_id = f"{self._mac}_sync_time"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=name,
            manufacturer="Nordkapp / Booyood",
            model=f"Air Gen 2 BLE ({coordinator.active_protocol.upper()})",
            connections={("bluetooth", self._mac)},
        )

    async def async_press(self) -> None:
        """Handle button press to synchronize time."""
        await self.coordinator.async_sync_time()
