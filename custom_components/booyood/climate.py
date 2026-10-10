"""Climate platform for Booyood Parking Heater."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_EXTERNAL_TEMP_SENSOR,
    CONF_MAC,
    CONF_NAME,
    DEFAULT_NAME,
    DOMAIN,
    MODE_GEAR,
    MODE_TEMPERATURE,
    MODE_VENTILATION,
    RUN_STEPS,
)
from .coordinator import BooyoodCoordinator

_LOGGER = logging.getLogger(__name__)

GEAR_MODES = [f"Gear {i}" for i in range(1, 11)]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Booyood climate entity from config entry."""
    coordinator: BooyoodCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BooyoodClimateEntity(coordinator, entry)])


class BooyoodClimateEntity(CoordinatorEntity[BooyoodCoordinator], ClimateEntity):
    """Climate entity representation of the Booyood diesel heater."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 8.0
    _attr_max_temp = 36.0
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.FAN_ONLY]
    _attr_fan_modes = GEAR_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: BooyoodCoordinator, entry: ConfigEntry) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._mac = entry.data[CONF_MAC]
        self._name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._external_temp_sensor: str | None = entry.options.get(
            CONF_EXTERNAL_TEMP_SENSOR, entry.data.get(CONF_EXTERNAL_TEMP_SENSOR)
        )
        self._attr_unique_id = f"{self._mac}_climate"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=self._name,
            manufacturer="Nordkapp / Booyood",
            model=f"Air Gen 2 BLE ({coordinator.active_protocol.upper()})",
            connections={("bluetooth", self._mac)},
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks and external sensor listener."""
        await super().async_added_to_hass()
        if self._external_temp_sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._external_temp_sensor],
                    self._async_external_temp_changed,
                )
            )

    async def _async_external_temp_changed(self, event: Any) -> None:
        """Handle state changes from the configured external temperature sensor."""
        self.async_write_ha_state()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC operation mode."""
        st = self.coordinator.status
        if st.is_on:
            if st.run_mode == MODE_VENTILATION or st.run_step in (6, 7):
                return HVACMode.FAN_ONLY
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action."""
        if not self.coordinator.status.is_on:
            return HVACAction.OFF
        step = self.coordinator.status.run_step
        if self.coordinator.status.run_mode == MODE_VENTILATION or step in (6, 7):
            return HVACAction.FAN
        if step in (1, 2, 3):
            return HVACAction.HEATING
        if step in (4, 5):
            return HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return the current room temperature from external sensor if configured, else onboard."""
        if self._external_temp_sensor:
            state = self.hass.states.get(self._external_temp_sensor)
            if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    return round(float(state.state), 1)
                except (ValueError, TypeError):
                    pass
        return self.coordinator.status.ambient_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature (°C)."""
        if self.coordinator.status.run_mode == MODE_TEMPERATURE:
            return float(self.coordinator.status.run_param)
        return getattr(self, "_target_temp", 22.0)

    @property
    def fan_mode(self) -> str | None:
        """Return current gear level as fan mode."""
        gear = self.coordinator.status.current_gear
        if 1 <= gear <= 10:
            return f"Gear {gear}"
        return f"Gear {self.coordinator.status.run_param}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return heater diagnostic attributes."""
        st = self.coordinator.status
        step_desc = RUN_STEPS.get(st.run_step, f"Step {st.run_step}")
        attrs: dict[str, Any] = {
            "run_step_code": st.run_step,
            "run_step_name": step_desc,
            "run_mode": st.run_mode,
            "heat_exchanger_temperature": st.heat_exchanger_temp,
            "onboard_ambient_temperature": st.ambient_temp,
            "voltage": st.voltage,
            "co_ppm": st.co_ppm,
            "altitude": st.altitude,
            "error_code": st.error_code,
            "remaining_runtime_minutes": st.remaining_minutes,
            "auto_start_stop": st.auto_start_stop,
            "startup_temp_difference": st.startup_temp_diff,
            "shutdown_temp_difference": st.shutdown_temp_diff,
            "protocol_version": self.coordinator.active_protocol,
        }
        if self._external_temp_sensor:
            attrs["external_temperature_sensor"] = self._external_temp_sensor
        return attrs

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.async_turn_on(mode=MODE_GEAR)
        elif hvac_mode == HVACMode.FAN_ONLY:
            await self.coordinator.async_set_ventilation()
        elif hvac_mode == HVACMode.OFF:
            await self.coordinator.async_turn_off()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._target_temp = float(temp)
            await self.coordinator.async_set_temperature(temp)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set heater power gear (Gear 1 .. 10) or ventilation speed."""
        if fan_mode.startswith("Gear "):
            try:
                gear = int(fan_mode.replace("Gear ", ""))
                if (
                    self.hvac_mode == HVACMode.FAN_ONLY
                    or self.coordinator.status.run_mode == MODE_VENTILATION
                ):
                    await self.coordinator.async_set_ventilation(gear)
                else:
                    await self.coordinator.async_set_gear(gear)
            except ValueError:
                pass

    async def async_turn_on(self) -> None:
        """Turn on the heater."""
        await self.coordinator.async_turn_on()

    async def async_turn_off(self) -> None:
        """Turn off the heater."""
        await self.coordinator.async_turn_off()
