"""Select platform for Booyood / Nordkapp Parking Heater."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_MAC,
    CONF_NAME,
    DEFAULT_NAME,
    DOMAIN,
    MODE_GEAR,
    MODE_TEMPERATURE,
    MODE_VENTILATION,
    MODE_HIGH_HEAT,
)
from .coordinator import BooyoodCoordinator

_LOGGER = logging.getLogger(__name__)

OPTION_GEAR = "Gear / Level (1..10)"
OPTION_THERMOSTAT = "Thermostat (°C)"
OPTION_VENTILATION = "Ventilation / Fan (Lüftung)"
OPTION_BOOST = "Boost / High Heat"

OPTION_TO_MODE = {
    OPTION_GEAR: MODE_GEAR,
    OPTION_THERMOSTAT: MODE_TEMPERATURE,
    OPTION_VENTILATION: MODE_VENTILATION,
    OPTION_BOOST: MODE_HIGH_HEAT,
}

MODE_TO_OPTION = {v: k for k, v in OPTION_TO_MODE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Booyood select entities from config entry."""
    coordinator: BooyoodCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        BooyoodModeSelectEntity(coordinator, entry),
    ])


class BooyoodModeSelectEntity(CoordinatorEntity[BooyoodCoordinator], SelectEntity):
    """Allows selecting the operational mode of the heater."""

    _attr_has_entity_name = True
    _attr_name = "Operating Mode"
    _attr_translation_key = "mode"
    _attr_icon = "mdi:tune-variant"
    _attr_options = [
        OPTION_GEAR,
        OPTION_THERMOSTAT,
        OPTION_VENTILATION,
        OPTION_BOOST,
    ]

    def __init__(self, coordinator: BooyoodCoordinator, entry: ConfigEntry) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._mac = entry.data[CONF_MAC]
        self._name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._attr_unique_id = f"{self._mac}_mode_select"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=self._name,
            manufacturer="Nordkapp / Booyood",
            model=f"Air Gen 2 BLE ({coordinator.active_protocol.upper()})",
            connections={("bluetooth", self._mac)},
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return MODE_TO_OPTION.get(self.coordinator.effective_mode, OPTION_GEAR)

    async def async_select_option(self, option: str) -> None:
        """Change the operating mode."""
        if option in OPTION_TO_MODE:
            target_mode = OPTION_TO_MODE[option]
            await self.coordinator.async_set_mode(target_mode)


