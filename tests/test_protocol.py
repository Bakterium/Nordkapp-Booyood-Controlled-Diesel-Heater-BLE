"""Unit tests for Nordkapp & Booyood BLE Protocol Engine."""

import sys
import os

# Add custom_components/booyood directly to path to test protocol standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components", "booyood")))

from const import (
    MODE_GEAR,
    MODE_TEMPERATURE,
    MODE_VENTILATION,
)
from protocol import (
    KEY1_V21,
    build_v1_cmd,
    build_v1_read,
    build_v1_start,
    build_v1_stop,
    build_v21_handshake,
    build_v21_read,
    build_v21_set_temp_diff,
    build_v21_start,
    build_v21_stop,
    clean_mac,
    decrypt_v21_response,
    parse_v1_status,
    parse_v21_status,
    xor_crypt,
)

TEST_MAC = "AA:BB:CC:11:22:33"
TEST_MAC_CLEAN = b"AABBCC112233"


def test_clean_mac():
    """Verify that clean_mac normalizes colons and lowercase."""
    assert clean_mac("aa:bb:cc:11:22:33") == TEST_MAC_CLEAN
    assert clean_mac("AABBCC112233") == TEST_MAC_CLEAN
    assert clean_mac("aa-bb-cc-11-22-33") == TEST_MAC_CLEAN


def test_v21_encryption_decryption():
    """Verify that XOR double-pass encryption is symmetric and invertible."""
    plain = bytearray([0xFE, 0xAA, 0x00, 0x00, 0x09, 0x00, 0x00, 0x00, 0xAD])
    key2 = clean_mac(TEST_MAC)
    encrypted = xor_crypt(plain, KEY1_V21, key2)
    decrypted = xor_crypt(encrypted, KEY1_V21, key2)
    assert plain == decrypted, "Decrypted data must match plaintext exactly"


def test_v21_handshake_builder():
    """Verify v2.1 handshake packet formatting with MAC Key2 and PIN in payload."""
    enc = build_v21_handshake(TEST_MAC, pin="1234")
    assert len(enc) == 11
    dec = decrypt_v21_response(enc, TEST_MAC)
    assert dec is not None
    assert dec[0] == 0xFE
    assert dec[1] == 0xAA
    assert dec[6] == 6  # Handshake cmd_1
    assert dec[7] == 0  # cmd_2
    # PIN 1234 in little-endian format (22 0c = 34, 12)
    assert dec[8] == 0x22  # 34 == 1234 % 100
    assert dec[9] == 0x0C  # 12 == 1234 // 100


def test_v21_ventilation_mode_builder():
    """Verify that ventilation / fan mode (mode 3) builds correctly."""
    enc = build_v21_start(TEST_MAC, run_mode=MODE_VENTILATION, run_param=7)
    dec = decrypt_v21_response(enc, TEST_MAC)
    assert dec is not None
    assert dec[6] == 1  # Control cmd_1
    assert dec[7] == 1  # Start / Param cmd_2
    assert dec[8] == MODE_VENTILATION  # 3
    assert dec[9] == 7  # Fan speed 7


def test_v21_read_builder():
    """Verify v2.1 telemetry read packet."""
    enc = build_v21_read(TEST_MAC)
    assert len(enc) == 9
    dec = decrypt_v21_response(enc, TEST_MAC)
    assert dec is not None
    assert dec[0] == 0xFE
    assert dec[1] == 0xAA
    assert dec[6] == 0  # Read cmd_1
    assert dec[7] == 0  # Read cmd_2


def test_v21_status_parser():
    """Verify that 46-byte status packet parses telemetry values accurately."""
    # Construct a synthetic decrypted 47-byte status packet (46 data + 1 checksum)
    raw = bytearray(47)
    raw[0] = 0xFE
    raw[1] = 0xAA
    raw[2] = 0  # protocol_version
    raw[8] = 0  # mainboard_type
    raw[10] = 2  # run_state (2 = ON)
    raw[11] = 3  # run_mode (3 = Ventilation)
    raw[12] = 6  # run_param (Fan speed 6)
    raw[13] = 6  # now_gear
    raw[14] = 6  # run_step (6 = Ventilation)
    raw[16] = 0  # fault_code (0 = OK)
    # Detect temp: 22 deg C (22, 0)
    raw[18] = 22
    raw[19] = 0
    # Altitude: 520 m
    raw[21] = 520 & 0xFF
    raw[22] = (520 >> 8) & 0xFF
    # Voltage: 12.6 V -> 126
    raw[23] = 126 & 0xFF
    raw[24] = (126 >> 8) & 0xFF
    # Skin temp: 45.0 C -> 450
    raw[25] = 450 & 0xFF
    raw[26] = (450 >> 8) & 0xFF
    # CO: 1.5 PPM -> 15
    raw[27] = 15
    raw[28] = 0
    # Startup temp diff: 3 deg, shutdown temp diff: 2 deg, auto_start_stop: 1
    raw[39] = 3
    raw[40] = 2
    raw[42] = 1
    # Remaining runtime: 120 min
    raw[44] = 120
    raw[45] = 0
    raw[-1] = sum(raw[:-1]) & 0xFF

    status = parse_v21_status(bytes(raw))
    assert status is not None
    assert status.is_on is True
    assert status.run_mode == MODE_VENTILATION
    assert status.run_step == 6
    assert status.current_gear == 6
    assert status.ambient_temp == 22.0
    assert status.altitude == 520
    assert status.voltage == 12.6
    assert status.heat_exchanger_temp == 45.0
    assert status.co_ppm == 1.5
    assert status.remaining_minutes == 120
    assert status.startup_temp_diff == 3
    assert status.shutdown_temp_diff == 2
    assert status.auto_start_stop is True


def test_v21_temp_offsets_packet():
    """Verify temperature offset packet attributes."""
    mac = "AA:BB:CC:DD:EE:FF"
    pkt = build_v21_set_temp_diff(mac, startup_diff=3, shutdown_diff=4, i_stop=1)
    dec = decrypt_v21_response(pkt, mac)
    assert dec is not None
    assert dec[4] == 22  # Length
    assert dec[6] == 3   # cmd_1
    assert dec[7] == 1   # cmd_2
    assert dec[17] == 3  # startup_diff
    assert dec[18] == 4  # shutdown_diff
    assert dec[20] == 1  # i_stop


def test_v1_legacy():
    """Verify legacy V1 command building and parsing."""
    cmd_on = build_v1_start("1234")
    assert len(cmd_on) == 8
    assert cmd_on[0] == 0xAA
    assert cmd_on[1] == 0x55
    assert cmd_on[4] == 3  # onOff
    assert cmd_on[5] == 1  # 1 = ON

    # Synthetic V1 status response
    resp = bytearray(24)
    resp[0] = 0xAA
    resp[1] = 0x55
    resp[3] = 1  # on
    resp[4] = 0  # errcode
    resp[5] = 3  # heating step
    resp[8] = 1  # gear mode
    resp[9] = 4  # gear 4
    # Voltage: 12.4V -> 124
    resp[11] = 124
    resp[12] = 0
    # Skin temp: 180 C
    resp[13] = 180
    resp[14] = 0
    # Room temp: 21 C
    resp[15] = 21
    resp[16] = 0

    st = parse_v1_status(bytes(resp))
    assert st is not None
    assert st.is_on is True
    assert st.voltage == 12.4
    assert st.heat_exchanger_temp == 180.0
    assert st.ambient_temp == 21.0


def test_v21_co_and_runtime_filtering():
    """Verify that absent CO sensor (raw 65535 or >=6553) and unlimited runtime (65535) become None."""
    raw = bytearray(47)
    raw[0] = 0xFE
    raw[1] = 0xAA
    raw[10] = 2  # ON
    raw[11] = 1  # Gear
    raw[13] = 4  # Gear 4
    raw[14] = 3  # Heating step
    # Absent CO sensor: 0xFFFF = 65535
    raw[27] = 0xFF
    raw[28] = 0xFF
    # Unlimited runtime: 0xFFFF = 65535
    raw[44] = 0xFF
    raw[45] = 0xFF
    # Tank: 10L (index 2), Pump: 22ul (index 1)
    raw[36] = 2
    raw[37] = 1
    raw[-1] = sum(raw[:-1]) & 0xFF

    status = parse_v21_status(bytes(raw))
    assert status is not None
    assert status.co_ppm is None
    assert status.remaining_minutes is None
    assert status.oil_volume == 2
    assert status.pump_model == 1


if __name__ == "__main__":
    test_clean_mac()
    test_v21_encryption_decryption()
    test_v21_handshake_builder()
    test_v21_ventilation_mode_builder()
    test_v21_read_builder()
    test_v21_status_parser()
    test_v21_temp_offsets_packet()
    test_v21_co_and_runtime_filtering()
    test_v1_legacy()
    print("All protocol tests passed successfully!")

