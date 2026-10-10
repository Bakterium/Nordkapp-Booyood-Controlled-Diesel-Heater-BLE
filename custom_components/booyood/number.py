"""Number platform for Booyood Parking Heater (Startup & Shutdown temperature offsets)."""

from __future__ import annotations

from collections.abc import Callable
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, CONF_NAME, DEFAULT_NAME, DOMAIN
from .coordinator import BooyoodCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class BooyoodNumberEntityDescription(NumberEntityDescription):
    """Describes Booyood number entity."""

    value_fn: Callable[[BooyoodCoordinator], float | None]
    set_fn: Callable[[BooyoodCoordinator, float], Any]


NUMBER_DESCRIPTIONS: tuple[BooyoodNumberEntityDescription, ...] = (
    BooyoodNumberEntityDescription(
        key="timer_duration",
        translation_key="timer_duration",
        name="Timer Duration",
        icon="mdi:timer-outline",
        native_min_value=0.0,
        native_max_value=1440.0,
        native_step=10.0,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        value_fn=lambda coord: float(coord.status.remaining_minutes or 0),
        set_fn=lambda coord, val: coord.async_set_remaining_runtime(int(val)),
    ),
    BooyoodNumberEntityDescription(
        key="startup_temp_diff",
        translation_key="startup_temp_diff",
        name="Startup Temperature Offset",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=1.0,
        native_max_value=10.0,
        native_step=1.0,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_fn=lambda coord: float(coord.status.startup_temp_diff) if coord.status.startup_temp_diff is not None else 2.0,
        set_fn=lambda coord, val: coord.async_set_startup_temp_diff(int(val)),
    ),
    BooyoodNumberEntityDescription(
        key="shutdown_temp_diff",
        translation_key="shutdown_temp_diff",
        name="Shutdown Temperature Offset",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=1.0,
        native_max_value=10.0,
        native_step=1.0,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_fn=lambda coord: float(coord.status.shutdown_temp_diff) if coord.status.shutdown_temp_diff is not None else 2.0,
        set_fn=lambda coord, val: coord.async_set_shutdown_temp_diff(int(val)),
    ),
    BooyoodNumberEntityDescription(
        key="ventilation_speed",
        translation_key="ventilation_speed",
        name="Ventilation Fan Speed",
        icon="mdi:fan",
        native_min_value=1.0,
        native_max_value=10.0,
        native_step=1.0,
        mode=NumberMode.SLIDER,
        value_fn=lambda coord: float(coord.status.run_param if coord.status.run_mode == 3 else coord.status.current_gear or 5),
        set_fn=lambda coord, val: coord.async_set_ventilation(int(val)),
    ),
    BooyoodNumberEntityDescription(
        key="tank_volume",
        translation_key="tank_volume",
        name="Tank Capacity",
        icon="mdi:gas-station",
        native_min_value=0.0,
        native_max_value=50.0,
        native_step=1.0,
        native_unit_of_measurement="L",
        mode=NumberMode.SLIDER,
        value_fn=lambda coord: float(coord.tank_volume_liters),
        set_fn=lambda coord, val: coord.async_set_tank_volume_liters(float(val)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Booyood number entities from config entry."""
    coordinator: BooyoodCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BooyoodNumberEntity(coordinator, entry, description)
            for description in NUMBER_DESCRIPTIONS
        ]
    )


class BooyoodNumberEntity(CoordinatorEntity[BooyoodCoordinator], NumberEntity):
    """Number entity for Booyood temperature offset parameters."""

    entity_description: BooyoodNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BooyoodCoordinator,
        entry: ConfigEntry,
        description: BooyoodNumberEntityDescription,
    ) -> None:
        """Initialize number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        mac = entry.data[CONF_MAC]
        name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._attr_unique_id = f"{mac}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=name,
            manufacturer="Nordkapp / Booyood",
            model=f"Air Gen 2 BLE ({coordinator.active_protocol.upper()})",
            connections={("bluetooth", mac)},
        )

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        The timer duration and ventilation speed can only be adjusted when the heater is connected and running.
        """
        if not super().available:
            return False
        if self.entity_description.key == "timer_duration":
            return bool(self.coordinator.status.is_on)
        return True

    async def async_set_native_value(self, value: float) -> None:
        """Update the number value."""
        await self.entity_description.set_fn(self.coordinator, value)

