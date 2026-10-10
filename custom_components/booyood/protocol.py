"""Booyood BLE Protocol Engine for Parking Heaters.

Reverse engineered from Booyood app v2.2.020 (uni-app com.booyood.www.airHeaterByBLE).
Supports both Modern Protocol v2.1 (XOR encrypted) and Legacy Protocol v1.0.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging
from typing import Any

try:
    from .const import MODE_GEAR, MODE_TEMPERATURE, MODE_VENTILATION, MODE_HIGH_HEAT
except ImportError:
    from const import MODE_GEAR, MODE_TEMPERATURE, MODE_VENTILATION, MODE_HIGH_HEAT

_LOGGER = logging.getLogger(__name__)

# Default master key for v2.1 protocol discovered from app-service.js
KEY1_V21 = b"passwordA2409PW"


@dataclass
class HeaterStatus:
    """Parsed status of the Booyood heater."""

    is_on: bool = False
    run_mode: int = MODE_GEAR  # 1 = Gear, 2 = Temperature
    run_step: int = 0          # 0=off, 1=preheat, 2=ignite, 3=heating, etc.
    run_param: int = 1         # Gear level (1..10) or Target Temp (°C)
    current_gear: int = 1
    ambient_temp: float = 0.0  # Room/detect temperature (°C)
    heat_exchanger_temp: float = 0.0  # Body/skin temperature (°C)
    voltage: float = 0.0       # Supply voltage (V)
    co_ppm: float | None = None # Carbon monoxide (PPM), None if no hardware sensor
    altitude: int = 0          # Altitude (m)
    error_code: int = 0        # 0 = OK, 1..10 = Error code
    remaining_minutes: int | None = None # Remaining runtime (None if unlimited / 65535)
    auto_start_stop: bool = False  # i_stop: Auto Start/Stop in temperature mode
    startup_temp_diff: int = 2     # Hysteresis for auto start (°C)
    shutdown_temp_diff: int = 2    # Hysteresis for auto shutdown (°C)
    oil_volume: int = 0            # Tank capacity index (0=--, 1=5L, 2=10L, ... 10=50L)
    pump_model: int = 1            # Pump model index (0=16ul, 1=22ul, 2=28ul, 3=32ul)
    raw_payload: bytes = b""


def clean_mac(mac: str) -> bytes:
    """Normalize BLE MAC address to uppercase without colons (ASCII bytes).

    Matches app-service.js Vs(e): e.toUpperCase().replace(/:/g, '')
    used as deviceNum / Key2 in v2.1 XOR cipher.
    """
    clean = mac.replace(":", "").replace("-", "").strip().upper()
    return clean.encode("ascii")


def xor_crypt(data: bytearray, key1: bytes, key2: bytes) -> bytearray:
    """Double-pass symmetric XOR cipher used in Booyood 2.1 protocol."""
    out = bytearray(data)
    # Pass 1 with master key
    r = 0
    k1_len = len(key1)
    for i in range(len(out)):
        out[i] ^= key1[r]
        r = (r + 1) % k1_len

    # Pass 2 with device MAC (deviceNum)
    if key2:
        r = 0
        k2_len = len(key2)
        for i in range(len(out)):
            out[i] ^= key2[r]
            r = (r + 1) % k2_len

    return out


# =========================================================================
# PROTOCOL V2.1 (Booyood 2.2.020+ Standard)
# =========================================================================

def build_v21_handshake(mac: str, pin: str = "1234") -> bytes:
    """Build handshake authentication packet (cmd_1=6, cmd_2=0).

    PIN is sent in the payload (byte 8: pin % 100, byte 9: pin // 100).
    XOR cipher Key2 is the device MAC without colons.
    """
    pw_int = int(pin) if pin.isdigit() else 1234
    pkt = bytearray(11)
    pkt[0] = 0xFE  # head_1
    pkt[1] = 0xAA  # head_2
    pkt[2] = 0     # version_num
    pkt[3] = 0     # package_num
    pkt[4] = 11    # length_l
    pkt[5] = 0     # length_h
    pkt[6] = 6     # cmd_1 (Handshake)
    pkt[7] = 0     # cmd_2
    pkt[8] = pw_int % 100
    pkt[9] = pw_int // 100
    pkt[10] = sum(pkt[:10]) & 0xFF  # Checksum

    key2 = clean_mac(mac)
    return bytes(xor_crypt(pkt, KEY1_V21, key2))


def build_v21_read(mac: str) -> bytes:
    """Build status read request packet (cmd_1=0, cmd_2=0)."""
    pkt = bytearray(9)
    pkt[0] = 0xFE
    pkt[1] = 0xAA
    pkt[2] = 0
    pkt[3] = 0
    pkt[4] = 9
    pkt[5] = 0
    pkt[6] = 0     # cmd_1 (Read)
    pkt[7] = 0     # cmd_2
    pkt[8] = sum(pkt[:8]) & 0xFF

    key2 = clean_mac(mac)
    return bytes(xor_crypt(pkt, KEY1_V21, key2))


def build_v21_start(
    mac: str,
    run_mode: int = MODE_GEAR,
    run_param: int = 5,
    remain_minutes: int = 0
) -> bytes:
    """Build heater start / control packet (cmd_1=1, cmd_2=1)."""
    pkt = bytearray(13)
    pkt[0] = 0xFE
    pkt[1] = 0xAA
    pkt[2] = 0
    pkt[3] = 0
    pkt[4] = 13
    pkt[5] = 0
    pkt[6] = 1     # cmd_1 (Control)
    pkt[7] = 1     # cmd_2 (Start / Param update)
    pkt[8] = run_mode
    pkt[9] = run_param
    pkt[10] = remain_minutes & 0xFF
    pkt[11] = (remain_minutes >> 8) & 0xFF
    pkt[12] = sum(pkt[:12]) & 0xFF

    key2 = clean_mac(mac)
    return bytes(xor_crypt(pkt, KEY1_V21, key2))


def build_v21_stop(
    mac: str,
    run_mode: int | None = None,
    run_param: int | None = None,
    remain_minutes: int = 65535,
) -> bytes:
    """Build heater stop packet (cmd_1=1, cmd_2=0).

    Matches App sd(mac, startup_params):
    When mode and param are known, a 13-byte control frame is sent with cmd_2=0.
    """
    if run_mode is not None:
        pkt = bytearray(13)
        pkt[0] = 0xFE
        pkt[1] = 0xAA
        pkt[2] = 0
        pkt[3] = 0
        pkt[4] = 13
        pkt[5] = 0
        pkt[6] = 1     # cmd_1 (Control)
        pkt[7] = 0     # cmd_2 (Stop)
        pkt[8] = run_mode
        pkt[9] = run_param or 1
        pkt[10] = remain_minutes & 0xFF
        pkt[11] = (remain_minutes >> 8) & 0xFF
        pkt[12] = sum(pkt[:12]) & 0xFF
    else:
        pkt = bytearray(9)
        pkt[0] = 0xFE
        pkt[1] = 0xAA
        pkt[2] = 0
        pkt[3] = 0
        pkt[4] = 9
        pkt[5] = 0
        pkt[6] = 1     # cmd_1 (Control)
        pkt[7] = 0     # cmd_2 (Stop)
        pkt[8] = sum(pkt[:8]) & 0xFF

    key2 = clean_mac(mac)
    return bytes(xor_crypt(pkt, KEY1_V21, key2))


def build_v21_set_attributes(
    mac: str,
    i_stop: int = 0,
    is_time_sync: bool = False,
    dt: datetime.datetime | None = None,
    startup_diff: int = 2,
    shutdown_diff: int = 2,
    oil_volume: int = 0,
    pump_model: int = 1,
) -> bytes:
    """Build 22-byte attribute setting packet (cmd_1=3, cmd_2=1)."""
    if dt is None:
        dt = datetime.datetime.now()
    pkt = bytearray(22)
    pkt[0] = 0xFE
    pkt[1] = 0xAA
    pkt[2] = 0
    pkt[3] = 0
    pkt[4] = 22  # length_l
    pkt[5] = 0   # length_h
    pkt[6] = 3   # cmd_1 (Attributes)
    pkt[7] = 1   # cmd_2 (Set)
    pkt[8] = 0   # altitude_unit
    pkt[9] = 0   # temp_unit
    cur_time = (60 * dt.hour + dt.minute + 32768) if is_time_sync else 0
    pkt[10] = cur_time & 0xFF
    pkt[11] = (cur_time >> 8) & 0xFF
    pkt[12] = (dt.year % 100) if is_time_sync else 0
    pkt[13] = dt.month if is_time_sync else 0
    pkt[14] = dt.day if is_time_sync else 0
    pkt[15] = dt.isoweekday() if is_time_sync else 0
    pkt[16] = 0  # back_light
    pkt[17] = startup_diff & 0xFF
    pkt[18] = shutdown_diff & 0xFF
    pkt[19] = 0  # wifi
    pkt[20] = i_stop & 0xFF
    # When not time syncing, bytes 14 and 15 hold oil_volume and pump_model
    if not is_time_sync:
        pkt[14] = oil_volume & 0xFF
        pkt[15] = pump_model & 0xFF
    pkt[21] = sum(pkt[:21]) & 0xFF

    key2 = clean_mac(mac)
    return bytes(xor_crypt(pkt, KEY1_V21, key2))


def build_v21_set_tank(
    mac: str,
    oil_volume: int,
    pump_model: int = 1,
    i_stop: int = 0,
    startup_diff: int = 2,
    shutdown_diff: int = 2,
) -> bytes:
    """Build tank volume and pump model configuration packet for v2.1 protocol."""
    return build_v21_set_attributes(
        mac,
        i_stop=i_stop,
        startup_diff=startup_diff,
        shutdown_diff=shutdown_diff,
        oil_volume=oil_volume,
        pump_model=pump_model,
    )


def build_v21_sync_time(mac: str, dt: datetime.datetime | None = None) -> bytes:
    """Build time sync packet for v2.1 protocol."""
    return build_v21_set_attributes(mac, is_time_sync=True, dt=dt)


def build_v21_set_auto_start_stop(
    mac: str,
    enabled: bool,
    startup_diff: int = 2,
    shutdown_diff: int = 2,
    oil_volume: int = 0,
    pump_model: int = 1,
) -> bytes:
    """Build auto start/stop setting packet for v2.1 protocol."""
    return build_v21_set_attributes(
        mac,
        i_stop=1 if enabled else 0,
        startup_diff=startup_diff,
        shutdown_diff=shutdown_diff,
        oil_volume=oil_volume,
        pump_model=pump_model,
    )


def build_v21_set_temp_diff(
    mac: str,
    startup_diff: int,
    shutdown_diff: int,
    i_stop: int = 1,
    oil_volume: int = 0,
    pump_model: int = 1,
) -> bytes:
    """Build temperature difference / offset packet for v2.1 protocol."""
    return build_v21_set_attributes(
        mac,
        i_stop=i_stop,
        startup_diff=startup_diff,
        shutdown_diff=shutdown_diff,
        oil_volume=oil_volume,
        pump_model=pump_model,
    )


def decrypt_v21_response(data: bytes, mac: str) -> bytes | None:
    """Decrypt a received response frame using v2.1 cipher (Key2 = MAC without colons)."""
    key2 = clean_mac(mac)
    dec = bytes(xor_crypt(bytearray(data), KEY1_V21, key2))
    if len(dec) >= 8 and dec[0] == 0xFE and dec[1] == 0xAA:
        return dec
    return None


def parse_v21_status(dec: bytes) -> HeaterStatus | None:
    """Parse decrypted v2.1 46-byte status response payload."""
    if len(dec) < 30:
        return None

    # Checksum validation
    chk = sum(dec[:-1]) & 0xFF
    if dec[-1] != chk:
        _LOGGER.debug("Checksum mismatch in v2.1 frame: expected %02x, got %02x", chk, dec[-1])

    status = HeaterStatus(raw_payload=dec)

    # Byte 10: run_state (2, 5, 6, 7 = ON / active, others = OFF)
    run_state = dec[10] if len(dec) > 10 else 0
    status.is_on = run_state in (2, 5, 6, 7) or (len(dec) > 14 and dec[14] in (1, 2, 3, 4, 6, 7))

    # Byte 11: run_mode (1 = Gear, 2 = Temp)
    status.run_mode = dec[11] if len(dec) > 11 else MODE_GEAR

    # Byte 12: run_param
    status.run_param = dec[12] if len(dec) > 12 else 1

    # Byte 13: now_gear
    status.current_gear = dec[13] if len(dec) > 13 else 1

    # Byte 14: run_step
    status.run_step = dec[14] if len(dec) > 14 else 0

    # Byte 15: fault_display, Byte 16: fault_code
    # App logic: if fault_code >= 128, error code is in fault_display (Byte 15)!
    # 128 = XMZ, 129 = TY (Nordkapp standard), 130 = JW.
    fault_disp = dec[15] if len(dec) > 15 else 0
    fault_cd = dec[16] if len(dec) > 16 else 0
    if fault_cd >= 128:
        status.error_code = fault_disp
    else:
        status.error_code = fault_cd

    # Bytes 18, 19: detect_temp (signed 16-bit LE ambient room temp)
    if len(dec) > 19:
        raw_t = dec[18] | (dec[19] << 8)
        if raw_t >= 32768:
            raw_t -= 65536
        status.ambient_temp = float(raw_t)

    # Bytes 21, 22: altitude (uint16 LE)
    if len(dec) > 22:
        status.altitude = dec[21] | (dec[22] << 8)

    # Bytes 23, 24: voltage ((uint16 LE) / 10.0 V)
    if len(dec) > 24:
        raw_v = dec[23] | (dec[24] << 8)
        status.voltage = round(raw_v / 10.0, 1)

    # Bytes 25, 26: skin_temp (signed 16-bit LE / 10.0 °C)
    if len(dec) > 26:
        raw_st = dec[25] | (dec[26] << 8)
        if raw_st >= 32768:
            raw_st -= 65536
        status.heat_exchanger_temp = round(raw_st / 10.0, 1)

    # Bytes 27, 28: co ((uint16 LE) / 10.0 PPM)
    # The official Booyood app filters out CO if raw >= 6553 (or 65535 when sensor not installed)
    if len(dec) > 28:
        raw_co = dec[27] | (dec[28] << 8)
        if raw_co < 65530 and round(raw_co / 10.0, 1) < 6553.0:
            status.co_ppm = round(raw_co / 10.0, 1)
        else:
            status.co_ppm = None
    else:
        status.co_ppm = None

    # Byte 36: oil_volume (Tank capacity: 0="--", 1="5L", 2="10L", ... 10="50L")
    if len(dec) > 36:
        status.oil_volume = dec[36]

    # Byte 37: pump_model (Pump pulse size: 0="16ul", 1="22ul", 2="28ul", 3="32ul")
    if len(dec) > 37:
        status.pump_model = dec[37]

    # Byte 39: startup_temp_difference
    if len(dec) > 39:
        status.startup_temp_diff = dec[39]

    # Byte 40: shutdown_temp_difference
    if len(dec) > 40:
        status.shutdown_temp_diff = dec[40]

    # Byte 42: i_stop (auto start/stop in temp mode)
    if len(dec) > 42:
        status.auto_start_stop = (dec[42] == 1)

    # Bytes 44, 45: remain_run_time (uint16 LE)
    # The heater reports the remaining countdown in minutes while running.
    # When off, standby, or in continuous/unlimited mode, raw value is 65535, 0, or an uninitialized garbage value (> 1440 min).
    # It must only report an active timer when the heater is ON and a real countdown is running (<= 1440 min).
    if len(dec) > 45 and status.is_on:
        raw_remain = dec[44] | (dec[45] << 8)
        if 0 < raw_remain <= 1440:
            status.remaining_minutes = raw_remain
        else:
            status.remaining_minutes = None
    else:
        status.remaining_minutes = None

    return status


# =========================================================================
# PROTOCOL V1.0 (Legacy Unencrypted 8-Byte Format)
# =========================================================================

def build_v1_cmd(password: str, cmd: int, data: int = 0) -> bytes:
    """Build legacy 8-byte command packet (0xAA 0x55)."""
    pw_int = int(password) if password.isdigit() else 1234
    pkt = bytearray(8)
    pkt[0] = 0xAA
    pkt[1] = 0x55
    pkt[2] = pw_int // 100
    pkt[3] = pw_int % 100
    pkt[4] = cmd
    pkt[5] = data & 0xFF
    pkt[6] = (data >> 8) & 0xFF
    pkt[7] = sum(pkt[2:7]) & 0xFF
    return bytes(pkt)


def build_v1_start(password: str) -> bytes:
    """V1 turn on."""
    return build_v1_cmd(password, cmd=3, data=1)


def build_v1_stop(password: str) -> bytes:
    """V1 turn off."""
    return build_v1_cmd(password, cmd=3, data=0)


def build_v1_set_mode(password: str, mode: int) -> bytes:
    """V1 set mode: 1 = Gear, 2 = Temperature."""
    return build_v1_cmd(password, cmd=2, data=mode)


def build_v1_set_param(password: str, param: int) -> bytes:
    """V1 set gear (1..10) or target temperature."""
    return build_v1_cmd(password, cmd=4, data=param)


def build_v1_read(password: str) -> bytes:
    """V1 query status."""
    return build_v1_cmd(password, cmd=1, data=0)


def build_v1_sync_time(password: str, dt: datetime.datetime | None = None) -> bytes:
    """V1 synchronize time (cmd=10)."""
    if dt is None:
        dt = datetime.datetime.now()
    return build_v1_cmd(password, cmd=10, data=60 * dt.hour + dt.minute)


def build_v1_set_auto_start_stop(password: str, enabled: bool) -> bytes:
    """V1 set auto start/stop (cmd=18)."""
    return build_v1_cmd(password, cmd=18, data=1 if enabled else 0)


def parse_v1_status(data: bytes) -> HeaterStatus | None:
    """Parse legacy V1 status packet starting with 0xAA 0x55 or 0xAA 0x66."""
    if len(data) < 18 or data[0] != 0xAA:
        return None

    status = HeaterStatus(raw_payload=data)

    # Byte 3: onOff (1 or 2 or 3 = ON, 0 = OFF)
    status.is_on = data[3] in (1, 2, 3)

    # Byte 4 or 17: error code
    status.error_code = data[17] if data[1] == 0x66 else data[4]

    # Byte 5: runStep
    status.run_step = data[5]

    # Byte 8: runMode
    status.run_mode = data[8] if data[8] in (1, 2) else MODE_GEAR

    # Byte 9: runTemp or runGear
    if status.run_mode == MODE_TEMPERATURE:
        status.run_param = data[9]
    else:
        status.run_param = data[9]
        status.current_gear = data[9]

    # Bytes 11, 12: Voltage
    raw_v = data[11] | (data[12] << 8)
    status.voltage = round(raw_v / 10.0, 1)

    # Bytes 13, 14: Heat exchanger temp (ShT)
    raw_st = data[13] | (data[14] << 8)
    if raw_st >= 32768:
        raw_st -= 65536
    status.heat_exchanger_temp = float(raw_st)

    # Bytes 15, 16: Ambient room temp (roT)
    raw_rt = data[15] | (data[16] << 8)
    if raw_rt >= 32768:
        raw_rt -= 65536
    status.ambient_temp = float(raw_rt)

    # Bytes 6, 7: Altitude
    status.altitude = data[6] | (data[7] << 8)

    # Byte 31: Auto start/stop
    if len(data) > 31:
        status.auto_start_stop = (data[31] == 1)

    return status
