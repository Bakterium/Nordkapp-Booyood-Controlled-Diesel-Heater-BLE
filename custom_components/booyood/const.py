"""Constants for the Booyood / Nordkapp Parking Heater BLE integration."""

DOMAIN = "booyood"

# BLE GATT Service and Characteristic UUIDs (Standard UART Profile)
BOOYOOD_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
BOOYOOD_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

# Configuration keys
CONF_MAC = "mac"
CONF_NAME = "name"
CONF_PIN = "pin"
CONF_PROTOCOL_VERSION = "protocol_version"
CONF_EXTERNAL_TEMP_SENSOR = "external_temp_sensor"

# Default values
DEFAULT_PIN = "1234"
DEFAULT_NAME = "Nordkapp / Booyood Heater"

# Supported protocol versions
PROTOCOL_AUTO = "auto"
PROTOCOL_V21 = "v21"  # Booyood 2.2.020+ XOR encrypted protocol
PROTOCOL_V1 = "v1"    # Classic unencrypted 8-byte AA55 protocol

MODE_OFF = 0            # Standby / Aus
MODE_GEAR = 1           # Level / Leistungsstufen (1..10)
MODE_TEMPERATURE = 2    # Thermostat / Zieltemperatur (°C)
MODE_VENTILATION = 3    # Lüftung / Fan-only (Gebläse 1..10 ohne Brenner)
MODE_HIGH_HEAT = 4      # Boost / Maximale Heizleistung (11)
MODE_SINGLE = 5         # Einzelheizung
MODE_CONSTANT_TEMP = 6  # Dauer-Thermostat

MODE_NAMES = {
    MODE_OFF: "Off / Standby",
    MODE_GEAR: "Gear / Level",
    MODE_TEMPERATURE: "Thermostat",
    MODE_VENTILATION: "Ventilation / Fan",
    MODE_HIGH_HEAT: "Boost / High Heat",
}

# Tank Volumes (Byte 36 index in App: 0="--", 1="5L", 2="10L", ..., 10="50L")
TANK_VOLUME_OPTIONS = [
    "--",
    "5 L",
    "10 L",
    "15 L",
    "20 L",
    "25 L",
    "30 L",
    "35 L",
    "40 L",
    "45 L",
    "50 L",
]

TANK_VOLUME_MAP = {name: idx for idx, name in enumerate(TANK_VOLUME_OPTIONS)}
TANK_VOLUME_REV_MAP = {idx: name for idx, name in enumerate(TANK_VOLUME_OPTIONS)}

# Pump Models (Byte 37 index in App: 0="16ul", 1="22ul", 2="28ul", 3="32ul")
PUMP_MODEL_OPTIONS = [
    "16 µl",
    "22 µl (Standard)",
    "28 µl",
    "32 µl",
]
PUMP_MODEL_MAP = {name: idx for idx, name in enumerate(PUMP_MODEL_OPTIONS)}
PUMP_MODEL_REV_MAP = {idx: name for idx, name in enumerate(PUMP_MODEL_OPTIONS)}


# Operating Steps / Phases (runStep)
RUN_STEPS = {
    0: "Standby / Off",
    1: "Preheating / Vorglühen",
    2: "Ignition / Zündung",
    3: "Heating / Heizbetrieb",
    4: "Cooling Down / Nachlauf",
    5: "Shutdown / Abschaltung",
    6: "Ventilation / Lüftung",
    7: "Ventilation / Lüftung (v2.1)",
}

# Fault / Error Code Descriptions
FAULT_CODES = {
    0: "Normal",
    1: "E-01: Under-voltage (Unterspannung)",
    2: "E-02: Over-voltage (Überspannung)",
    3: "E-03: Glow plug fault (Glühkerze defekt)",
    4: "E-04: Fuel pump fault (Kraftstoffpumpe Fehler)",
    5: "E-05: Overheat error (Überhitzung)",
    6: "E-06: Fan motor fault (Lüftermotor Fehler)",
    7: "E-07: Communication error (Kommunikationsfehler)",
    8: "E-08: Flame extinction (Flammenabbruch)",
    9: "E-09: Temperature sensor error (Temperaturfühler Fehler)",
    10: "E-10: Ignition failure (Zündfehler)",
}
