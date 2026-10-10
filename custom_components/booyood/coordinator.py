"""DataUpdateCoordinator for Booyood Parking Heater BLE."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BOOYOOD_CHAR_UUID,
    CONF_MAC,
    CONF_PIN,
    CONF_PROTOCOL_VERSION,
    DOMAIN,
    MODE_GEAR,
    MODE_TEMPERATURE,
    MODE_VENTILATION,
    PROTOCOL_AUTO,
    PROTOCOL_V1,
    PROTOCOL_V21,
)
from .protocol import (
    HeaterStatus,
    build_v1_read,
    build_v1_set_auto_start_stop,
    build_v1_set_mode,
    build_v1_set_param,
    build_v1_start,
    build_v1_stop,
    build_v1_sync_time,
    build_v21_handshake,
    build_v21_read,
    build_v21_set_attributes,
    build_v21_set_auto_start_stop,
    build_v21_set_tank,
    build_v21_start,
    build_v21_stop,
    build_v21_sync_time,
    decrypt_v21_response,
    parse_v1_status,
    parse_v21_status,
)

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=5)


class BooyoodCoordinator(DataUpdateCoordinator[HeaterStatus]):
    """Coordinates BLE communication with the Booyood heater."""

    def __init__(self, hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=POLL_INTERVAL,
        )
        self.mac: str = entry_data[CONF_MAC]
        self.pin: str = entry_data.get(CONF_PIN, "1234")
        self.configured_protocol: str = entry_data.get(
            CONF_PROTOCOL_VERSION, PROTOCOL_AUTO
        )
        self.active_protocol: str = (
            PROTOCOL_V21 if self.configured_protocol == PROTOCOL_AUTO else self.configured_protocol
        )

        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self.status = HeaterStatus()
        self._handshake_done = False
        self._preferred_mode: int | None = None

    @property
    def effective_mode(self) -> int:
        """Return the current operating mode or preferred mode when off."""
        if self._preferred_mode is not None:
            return self._preferred_mode
        return self.status.run_mode or MODE_GEAR

    @property
    def estimated_fuel_rate(self) -> float:
        """Estimated diesel fuel consumption rate in Liters per hour (L/h).

        Standard diesel air heaters (2kW - 8kW) burn:
        - Standby / Fan only: 0.0 L/h
        - Heating active (run_step 1..4): ~0.14 L/h at Gear 1 up to ~0.46 L/h at Gear 10
        Scaled by pump stroke volume if configured (16ul, 22ul, 28ul, 32ul).
        """
        # When off or in fan-only ventilation mode (mode 3 or run_step 6,7)
        if not self.status.is_on or self.status.run_mode == MODE_VENTILATION or self.status.run_step in (0, 6, 7):
            return 0.0

        # Heating active (1=preheat, 2=ignition, 3=heating, 4=cooling)
        gear = max(1, min(10, self.status.current_gear or self.status.run_param or 1))
        # Pump multiplier relative to standard 22ul pump
        pump_multipliers = {0: 16.0 / 22.0, 1: 1.0, 2: 28.0 / 22.0, 3: 32.0 / 22.0}
        mult = pump_multipliers.get(self.status.pump_model, 1.0)

        # Baseline: gear 1 is ~0.14 L/h, gear 10 is ~0.46 L/h
        base_rate = 0.10 + (gear * 0.036)
        return round(base_rate * mult, 2)

    @property
    def tank_volume_liters(self) -> float:
        """Return the current configured tank volume in Liters (0.0 if disabled)."""
        idx = self.status.oil_volume or 0
        if 1 <= idx <= 10:
            return float(idx * 5)
        return 0.0


    async def _async_get_client(self) -> BleakClient:
        """Get or establish an active BLE connection."""
        if self._client and self._client.is_connected:
            return self._client

        device = bluetooth.async_ble_device_from_address(
            self.hass, self.mac, connectable=True
        )
        if not device:
            raise UpdateFailed(f"Could not find Bluetooth device for {self.mac}")

        _LOGGER.debug("Connecting to Booyood device %s", self.mac)
        client = await establish_connection(
            BleakClient,
            device,
            name=self.mac,
            disconnected_callback=self._on_disconnected,
            max_attempts=3,
        )

        self._client = client
        self._handshake_done = False

        # Start notifications on UART characteristic
        await client.start_notify(BOOYOOD_CHAR_UUID, self._on_notification)
        _LOGGER.debug("Subscribed to BLE notifications on %s", BOOYOOD_CHAR_UUID)

        # If v2.1 (or auto), perform handshake
        if self.active_protocol == PROTOCOL_V21:
            await self._perform_handshake()

        return self._client

    def _on_disconnected(self, client: BleakClient) -> None:
        """Handle disconnection event."""
        _LOGGER.info("Booyood device %s disconnected", self.mac)
        self._handshake_done = False
        self._client = None

    def _on_notification(self, _: Any, data: bytearray) -> None:
        """Handle incoming BLE notification packet."""
        raw = bytes(data)
        _LOGGER.debug("Received raw BLE notification (%d bytes): %s", len(raw), raw.hex())

        parsed: HeaterStatus | None = None

        # Try V2.1 decryption with MAC address without colons
        dec = decrypt_v21_response(raw, self.mac)
        if dec:
            _LOGGER.debug("Decrypted V2.1 frame (%d bytes): %s", len(dec), dec.hex())
            # Check if this is a handshake ACK (cmd_1 = 0x86)
            if len(dec) >= 9 and dec[6] == 0x86:
                if dec[8] == 1:
                    _LOGGER.info("V2.1 Handshake authenticated successfully")
                    self._handshake_done = True
                else:
                    _LOGGER.warning("V2.1 Handshake authentication failed: check PIN!")
            else:
                parsed = parse_v21_status(dec)
                if parsed:
                    self.active_protocol = PROTOCOL_V21
        elif raw.startswith(b"\xaa\x55") or raw.startswith(b"\xaa\x66"):
            # Legacy V1 packet
            parsed = parse_v1_status(raw)
            if parsed:
                self.active_protocol = PROTOCOL_V1

        if parsed:
            self.status = parsed
            self.async_set_updated_data(self.status)

    async def _perform_handshake(self) -> None:
        """Send v2.1 authentication handshake."""
        handshake_pkt = build_v21_handshake(self.mac, self.pin)
        _LOGGER.debug("Sending V2.1 handshake packet (%s)", handshake_pkt.hex())
        try:
            await self._client.write_gatt_char(
                BOOYOOD_CHAR_UUID, handshake_pkt, response=False
            )
            await asyncio.sleep(0.3)
        except Exception as ex:
            _LOGGER.warning("Failed to send handshake: %s", ex)

    async def _async_update_data(self) -> HeaterStatus:
        """Poll the heater for updated telemetry status."""
        async with self._lock:
            try:
                client = await self._async_get_client()

                if self.active_protocol == PROTOCOL_V21:
                    if not self._handshake_done:
                        await self._perform_handshake()
                    query_pkt = build_v21_read(self.mac)
                else:
                    query_pkt = build_v1_read(self.pin)

                await client.write_gatt_char(BOOYOOD_CHAR_UUID, query_pkt, response=False)
            except BleakError as err:
                raise UpdateFailed(f"BLE Communication error: {err}") from err
            except Exception as ex:
                raise UpdateFailed(f"Unexpected error updating Booyood heater: {ex}") from ex

            return self.status

    async def async_send_raw(self, packet: bytes) -> None:
        """Send raw packet to UART characteristic."""
        async with self._lock:
            client = await self._async_get_client()
            await client.write_gatt_char(BOOYOOD_CHAR_UUID, packet, response=False)
            # Short pause to allow BLE device processing
            await asyncio.sleep(0.2)

    async def async_turn_on(
        self,
        mode: int | None = None,
        param: int | None = None,
        remain_minutes: int = 0
    ) -> None:
        """Turn on the heater with optional mode and parameter."""
        target_mode = mode or self._preferred_mode or self.status.run_mode or MODE_GEAR
        target_param = param or self.status.run_param or (5 if target_mode == MODE_GEAR else 20)
        self._preferred_mode = target_mode

        _LOGGER.info(
            "Turning ON Booyood heater: mode=%s, param=%s", target_mode, target_param
        )
        if self.active_protocol == PROTOCOL_V21:
            pkt = build_v21_start(self.mac, target_mode, target_param, remain_minutes)
            await self.async_send_raw(pkt)
        else:
            await self.async_send_raw(build_v1_start(self.pin))
            await self.async_send_raw(build_v1_set_mode(self.pin, target_mode))
            await self.async_send_raw(build_v1_set_param(self.pin, target_param))

        await self.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off the heater."""
        _LOGGER.info("Turning OFF Booyood heater")
        if self.active_protocol == PROTOCOL_V21:
            pkt = build_v21_stop(
                self.mac,
                run_mode=self.status.run_mode or self._preferred_mode or MODE_GEAR,
                run_param=self.status.run_param or 5,
                remain_minutes=self.status.remaining_minutes or 65535,
            )
            await self.async_send_raw(pkt)
        else:
            await self.async_send_raw(build_v1_stop(self.pin))

        await self.async_request_refresh()

    async def async_set_temperature(self, temp: float) -> None:
        """Set target temperature (°C)."""
        temp_int = int(round(temp))
        temp_int = max(8, min(36, temp_int))
        self._preferred_mode = MODE_TEMPERATURE
        _LOGGER.info("Setting target temperature: %d °C", temp_int)

        if self.active_protocol == PROTOCOL_V21:
            # Matches App: both when on and when switching mode in standby, send start frame
            pkt = build_v21_start(
                self.mac,
                run_mode=MODE_TEMPERATURE,
                run_param=temp_int,
                remain_minutes=self.status.remaining_minutes or 65535 if not self.status.is_on else (self.status.remaining_minutes or 0),
            )
            await self.async_send_raw(pkt)
        else:
            await self.async_send_raw(build_v1_set_mode(self.pin, MODE_TEMPERATURE))
            await self.async_send_raw(build_v1_set_param(self.pin, temp_int))

        self.status.run_mode = MODE_TEMPERATURE
        self.status.run_param = temp_int
        await self.async_request_refresh()

    async def async_set_gear(self, gear: int) -> None:
        """Set heating gear level (1..10)."""
        gear = max(1, min(10, gear))
        self._preferred_mode = MODE_GEAR
        _LOGGER.info("Setting heating gear: %d", gear)

        if self.active_protocol == PROTOCOL_V21:
            pkt = build_v21_start(
                self.mac,
                run_mode=MODE_GEAR,
                run_param=gear,
                remain_minutes=self.status.remaining_minutes or 65535 if not self.status.is_on else (self.status.remaining_minutes or 0),
            )
            await self.async_send_raw(pkt)
        else:
            await self.async_send_raw(build_v1_set_mode(self.pin, MODE_GEAR))
            await self.async_send_raw(build_v1_set_param(self.pin, gear))

        self.status.run_mode = MODE_GEAR
        self.status.run_param = gear
        self.status.current_gear = gear
        await self.async_request_refresh()

    async def async_set_ventilation(self, fan_speed: int = 5) -> None:
        """Start ventilation / fan-only mode (blower running without diesel heating)."""
        speed = max(1, min(10, fan_speed))
        self._preferred_mode = MODE_VENTILATION
        _LOGGER.info("Starting ventilation mode with fan speed: %d", speed)
        await self.async_turn_on(mode=MODE_VENTILATION, param=speed)

    async def async_set_mode(self, mode: int, param: int | None = None) -> None:
        """Switch operating mode (1=Gear, 2=Thermostat, 3=Ventilation, 4=Boost)."""
        _LOGGER.info("Switching operating mode to %d", mode)
        self._preferred_mode = mode
        if mode == MODE_VENTILATION:
            p = param or (self.status.run_param if self.status.run_mode == MODE_VENTILATION else 5)
            await self.async_set_ventilation(p)
        elif mode == MODE_TEMPERATURE:
            p = param or (int(self.status.run_param) if self.status.run_mode == MODE_TEMPERATURE else 20)
            await self.async_set_temperature(p)
        elif mode == MODE_HIGH_HEAT:
            p = 11
            self.status.run_mode = MODE_HIGH_HEAT
            self.status.run_param = p
            if self.active_protocol == PROTOCOL_V21:
                pkt = build_v21_start(
                    self.mac,
                    run_mode=MODE_HIGH_HEAT,
                    run_param=p,
                    remain_minutes=self.status.remaining_minutes or 0,
                )
                await self.async_send_raw(pkt)
            await self.async_request_refresh()
        else:
            p = param or (self.status.run_param if self.status.run_mode == MODE_GEAR else 5)
            await self.async_set_gear(p)

    async def async_set_tank_volume(self, volume_idx: int) -> None:
        """Configure fuel tank capacity index (0=--, 1=5L, 2=10L, ... 10=50L)."""
        _LOGGER.info("Setting tank volume index to %d", volume_idx)
        if self.active_protocol == PROTOCOL_V21:
            pkt = build_v21_set_tank(
                self.mac,
                oil_volume=volume_idx,
                pump_model=self.status.pump_model or 1,
                i_stop=1 if self.status.auto_start_stop else 0,
                startup_diff=self.status.startup_temp_diff or 2,
                shutdown_diff=self.status.shutdown_temp_diff or 2,
            )
            await self.async_send_raw(pkt)
        self.status.oil_volume = volume_idx
        await self.async_request_refresh()

    async def async_set_tank_volume_liters(self, liters: float) -> None:
        """Set tank capacity from liters slider (0 to 50 L), mapping to nearest 5L firmware step."""
        if liters <= 2.5:
            idx = 0  # Disabled / --
        else:
            # Map 5..50 to steps 1..10
            idx = max(1, min(10, int(round(liters / 5.0))))
        _LOGGER.info("Setting tank volume: %.1f L -> step index %d", liters, idx)
        await self.async_set_tank_volume(idx)


    async def async_set_remaining_runtime(self, minutes: int) -> None:
        """Set remaining timer duration in minutes (0 resets/cancels timer to unlimited)."""
        _LOGGER.info("Setting remaining runtime timer to %d minutes", minutes)
        target_minutes = 65535 if minutes <= 0 else int(minutes)
        if self.active_protocol == PROTOCOL_V21:
            mode = self.status.run_mode or self._preferred_mode or MODE_GEAR
            param = self.status.run_param or 5
            pkt = build_v21_start(self.mac, mode, param, target_minutes)
            await self.async_send_raw(pkt)
        self.status.remaining_minutes = None if target_minutes == 65535 else target_minutes
        await self.async_request_refresh()

    async def async_sync_time(self) -> None:
        """Synchronize the heater's clock with local time."""
        _LOGGER.info("Synchronizing heater clock with local time")
        if self.active_protocol == PROTOCOL_V21:
            pkt = build_v21_sync_time(self.mac)
            await self.async_send_raw(pkt)
        else:
            await self.async_send_raw(build_v1_sync_time(self.pin))


    async def async_set_auto_start_stop(self, enabled: bool) -> None:
        """Enable or disable Auto Start/Stop in temperature mode."""
        _LOGGER.info("Setting Auto Start/Stop to %s", enabled)
        startup_diff = self.status.startup_temp_diff or 2
        shutdown_diff = self.status.shutdown_temp_diff or 2
        if self.active_protocol == PROTOCOL_V21:
            pkt = build_v21_set_auto_start_stop(
                self.mac, enabled, startup_diff=startup_diff, shutdown_diff=shutdown_diff
            )
            await self.async_send_raw(pkt)
        else:
            await self.async_send_raw(build_v1_set_auto_start_stop(self.pin, enabled))

        self.status.auto_start_stop = enabled
        await self.async_request_refresh()

    async def async_set_startup_temp_diff(self, diff: int) -> None:
        """Set startup temperature difference / hysteresis offset (delta T under target)."""
        diff = max(1, min(10, int(diff)))
        _LOGGER.info("Setting startup temp diff to %d °C", diff)
        shutdown_diff = self.status.shutdown_temp_diff or 2
        i_stop = 1 if self.status.auto_start_stop else 0
        if self.active_protocol == PROTOCOL_V21:
            pkt = build_v21_set_attributes(
                self.mac,
                i_stop=i_stop,
                startup_diff=diff,
                shutdown_diff=shutdown_diff,
            )
            await self.async_send_raw(pkt)
        self.status.startup_temp_diff = diff
        await self.async_request_refresh()

    async def async_set_shutdown_temp_diff(self, diff: int) -> None:
        """Set shutdown temperature difference / hysteresis offset (delta T over target)."""
        diff = max(1, min(10, int(diff)))
        _LOGGER.info("Setting shutdown temp diff to %d °C", diff)
        startup_diff = self.status.startup_temp_diff or 2
        i_stop = 1 if self.status.auto_start_stop else 0
        if self.active_protocol == PROTOCOL_V21:
            pkt = build_v21_set_attributes(
                self.mac,
                i_stop=i_stop,
                startup_diff=startup_diff,
                shutdown_diff=diff,
            )
            await self.async_send_raw(pkt)
        self.status.shutdown_temp_diff = diff
        await self.async_request_refresh()

    async def async_disconnect(self) -> None:
        """Disconnect BLE client."""
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(BOOYOOD_CHAR_UUID)
            except Exception:
                pass
            await self._client.disconnect()
            self._client = None
