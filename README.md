# Nordkapp® Air Gen 2 & Booyood Diesel-Standheizung BLE

[![HACS Validation](https://github.com/custom-components/nordkapp-booyood-ble/actions/workflows/validate.yml/badge.svg)](https://github.com/custom-components/nordkapp-booyood-ble/actions)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Home Assistant Custom Integration zur lokalen Bluetooth Low Energy (BLE) Steuerung von **Nordkapp® Air Gen 2 Diesel-Luftheizungen** und baugleichen Geräten (Booyood, Hcalory, Vevor, LF Bros, Aufocus, Sunster etc.).

Vollständig lokal, ohne Cloud, ohne Internetverbindung und ohne zusätzliche Hardware-Bridges.

---

## ✨ Funktionsumfang

* 🔥 **Vollwertige Thermostat- & Heizungssteuerung (`climate`)**:
  * Regelung der Zieltemperatur (8 °C bis 36 °C).
  * Direkte Wahl der Leistungsstufe (`Gear 1` bis `Gear 10`) über die Gebläsestufen (`fan_mode`).
  * Genaue Zustandsanzeige (`heating`, `cooling`, `fan`, `idle`, `off`).
* 💨 **Lüftungs- & Ventilationsmodus (`fan_only`)**:
  * Reiner Gebläsebetrieb zur Frischluftzirkulation ohne Glühkerze und ohne Dieselverbrauch.
  * Einstellbare Drehzahl über die Stufen 1 bis 10.
  * Umschaltbar direkt über das Thermostat (`Fan only`) oder die Modus-Auswahl.
* 🔄 **Automatischer Start/Stopp Modus (`switch.nordkapp_heater_auto_start_stop`)**:
  * Schaltet die Heizung automatisch ab, wenn die Wunschtemperatur erreicht ist, und startet sie wieder, sobald der Raum abkühlt (`i_stop` / `autoOnOff`).
  * Sowohl für Protokoll v2.1 (Attribut-Paket `0x03 0x01`, Byte 20) als auch Protokoll v1.0 (Kommando `18`).
* 🎚️ **Start- & Stop-Temperaturversatz / Hysterese (`number`)**:
  * **Start-Temperaturversatz (`number.nordkapp_heater_startup_temperature_offset`)**: Einstellbar von 1 °C bis 10 °C (Standard: 2 °C) – Heizung startet wieder, wenn Raumtemperatur um diesen Wert *unter* Solltemperatur fällt ($T_\text{Start} = T_\text{Soll} - \Delta T_\text{Start}$).
  * **Stop-Temperaturversatz (`number.nordkapp_heater_shutdown_temperature_offset`)**: Einstellbar von 1 °C bis 10 °C (Standard: 2 °C) – Heizung stoppt, wenn Raumtemperatur um diesen Wert *über* Solltemperatur steigt ($T_\text{Stop} = T_\text{Soll} + \Delta T_\text{Stop}$).
* 🕒 **Uhrzeit-Synchronisation (`button.nordkapp_heater_sync_time`)**:
  * Ein-Klick-Button zum Abgleichen der internen Standheizungsuhr mit der lokalen Systemzeit von Home Assistant (`current_time`, Wochentag, Datum).
* ⛽ **Kraftstofftank & Verbrauchsberechnung**:
  * **Tankinhalt-Schieberegler (`number.nordkapp_heater_tank_capacity`)**: Stufenloser Schieberegler von 0 bis 50 Liter für individuelle Tankgrößen. Mappt automatisch auf die internen Firmware-Stufen (5 L bis 50 L oder deaktiviert bei 0 L).
  * **Aktueller Dieselverbrauch (`sensor.nordkapp_heater_fuel_consumption`)**: Präzise Berechnung in Litern pro Stunde ($\text{L/h}$) basierend auf Brennerstufe, Betriebsphase und Pumpenmodell (16 µl, 22 µl, 28 µl, 32 µl). Im Lüftungsmodus oder Standby automatisch $0{,}0\,\text{L/h}$.
* ⏱️ **Timer & Restlaufzeit-Verwaltung**:
  * **Timer-Dauer (`number.nordkapp_heater_timer_duration`)**: Einstellen der gewünschten Heizdauer in Minuten oder Deaktivieren/Resetten auf unbegrenzten Dauerbetrieb.
  * **Restlaufzeit-Sensor (`sensor.nordkapp_heater_remaining_runtime`)**: Zeigt die verbleibende Laufzeit in Minuten an. Im Dauerbetrieb (`65535` / kein Timer aktiv) wird der Sensor sauber als inaktiv dargestellt statt fälschlicherweise 65.535 Minuten anzuzeigen.
* 🌡️ **Unterstützung für externe Raumtemperatursensoren**:
  * In den Integrations-Optionen oder beim Einrichten kann ein beliebiger Home Assistant Sensor (z. B. Zigbee / Z-Wave Raumthermostat) ausgewählt werden.
  * Das `climate`-Thermostat nutzt dann automatisch diesen Sensor für die Raumtemperatur (mit automatischem Fallback auf den internen Sensor der Heizung).
* 🎛️ **Betriebsmodus-Auswahl (`select.operating_mode`)**:
  * *Gear / Level (1..10)*: Feste Brennerstufe
  * *Thermostat (°C)*: Automatische Zieltemperatur-Regelung
  * *Ventilation / Fan (Lüftung)*: Reiner Gebläsebetrieb
  * *Boost / High Heat*: Maximale Heizleistung
* 📊 **Vollständige Telemetrie & Diagnose (`sensor`)**:
  * **Bord- / Versorgungsspannung** (V)
  * **Wärmetauscher-Gehäusetemperatur** (°C)
  * **Umgebungstemperatur / Raumtemperatur** (°C)
  * **Aktuelle Brennerstufe** (1..10)
  * **Betriebsphase im Klartext** (*Vorglühen*, *Zündung*, *Heizbetrieb*, *Lüftung*, *Nachlauf/Abkühlung*, *Standby*)
  * **Aktueller Dieselverbrauch** (L/h)
  * **Kohlenmonoxid-Gehalt** (PPM) – intelligente Erkennung: wird automatisch ausgeblendet, falls hardwareseitig kein CO-Sensor verbaut ist (Hersteller-Dummy 6553.5 PPM).
  * **Höhenmesser** (m)
  * **Verbleibende Laufzeit** (Minuten)
  * **Fehlercode & Diagnose** (z. B. *E-01 Unterspannung*, *E-03 Glühkerze*, *E-08 Flammenabbruch*)
* 🚨 **Binärsensoren (`binary_sensor`)**:
  * *Brenner aktiv* (`running`)
  * *Fehlerzustand* (`problem`)
* 🔐 **Protokollunterstützung**:
  * **Protokoll v2.1 (Standard ab Booyood 2.2+)**: Symmetrische XOR-Verschlüsselung mit MAC-Key & Handshake.
  * **Protokoll v1.0 (Legacy)**: Klassisches unverschlüsseltes 8-Byte `0xAA 0x55`-Protokoll.
  * Automatische Erkennung des Protokolls bei Verbindung.

---

## 🔍 Protokoll & Kryptographie-Analyse (v2.1)

Aus dem Reverse Engineering der App **Booyood 2.2.020** (`com.booyood.www.airHeaterByBLE`) und Live-BLE-Paketanalysen:

### 1. BLE GATT Schnittstelle
* **GATT Service UUID**: `0000ffe0-0000-1000-8000-00805f9b34fb` (`0xFFE0` – Standard BLE UART).
* **GATT Characteristic UUID**: `0000ffe1-0000-1000-8000-00805f9b34fb` (`0xFFE1` – Write & Notify).
* **Advertised Local Names**: Beginnen in der Regel mit `NK*`, `Nordkapp*`, `BYD*` oder `BAC*`.

### 2. Symmetrische 2-Wege XOR-Verschlüsselung
Alle Datenpakete (Senden & Empfangen) im Protokoll v2.1 werden mit einer zweistufigen XOR-Verschlüsselung maskiert:

$$\text{CipherByte} = \text{PlainByte} \oplus \text{Key1}[i \pmod{15}] \oplus \text{Key2}[i \pmod{12}]$$

* **Key1 (Master-Key)**: `passwordA2409PW` (15 Bytes ASCII, fest in der App).
* **Key2 (Geräte-Key)**: Die **Bluetooth MAC-Adresse des Geräts ohne Doppelpunkte in Großbuchstaben** (12 Bytes ASCII, z. B. `A1B2C3D4E5F6`, ermittelt über die App-Funktion `Vs(address)`).
* Da XOR selbstinvers ist ($A \oplus K \oplus K = A$), ist die Entschlüsselung identisch zur Verschlüsselung.

### 3. Rolle der Geräte-PIN
> [!IMPORTANT]
> Die PIN (Standard: `1234`) dient **nicht** als kryptographischer Schlüssel `Key2`, sondern wird ausschließlich in der Nutzdaten-Payload des Handshake-Pakets (`cmd_1=6, cmd_2=0`) übertragen:
> * `Byte 8`: $\text{PIN} \pmod{100}$ (z. B. $1234 \pmod{100} = 34 = \mathtt{0x22}$)
> * `Byte 9`: $\lfloor \text{PIN} / 100 \rfloor$ (z. B. $\lfloor 1234 / 100 \rfloor = 12 = \mathtt{0x0C}$)
> Im Hex-Stream erscheint die PIN `1234` somit als `22 0c`.

### 4. Frame-Aufbau (v2.1)
* `Byte 0`: `0xFE`
* `Byte 1`: `0xAA`
* `Byte 2..3`: Version (`0`), Paketnummer (`0`)
* `Byte 4..5`: Paketgesamtlänge (Little-Endian, z. B. `09 00` für 9 Bytes, `0d 00` für 13 Bytes, `16 00` für 22 Bytes)
* `Byte 6`: `cmd_1` (Befehlskategorie)
* `Byte 7`: `cmd_2` (Aktion)
* `Byte 8 .. N-2`: Nutzdaten
* `Byte N-1`: Checksumme ($\sum_{j=0}^{N-2} \text{Byte}[j] \pmod{256}$)

### 5. Steuerungsbefehle & Attribute
* **Handshake**: `cmd_1 = 6, cmd_2 = 0` (Payload: PIN `[pin % 100, pin // 100]`)
* **Status abfragen**: `cmd_1 = 0, cmd_2 = 0`
* **Einschalten / Parameter ändern**: `cmd_1 = 1, cmd_2 = 1`
  * `run_mode = 1`: Gear Mode (Stufe 1..10)
  * `run_mode = 2`: Temperature Mode (Thermostat 8..36 °C)
  * `run_mode = 3`: **Ventilation Mode (Lüftung)** (Frischluftgebläse 1..10 ohne Brenner)
  * `run_mode = 4`: High Heat / Boost
* **Ausschalten**: `cmd_1 = 1, cmd_2 = 0`
* **Attribute / Zeit / Auto-Start-Stopp setzen**: `cmd_1 = 3, cmd_2 = 1` (22 Bytes)
  * Byte 8: `current_time % 256` mit $\text{current\_time} = 60 \cdot \text{hour} + \text{minute} + 32768$
  * Byte 9: `current_time // 256`
  * Byte 12: `year % 100`, Byte 13: `month`, Byte 14: `day`, Byte 15: `weekday`
  * Byte 20: `i_stop` (1 = Auto Start/Stopp aktiv, 0 = inaktiv)

---

## 📦 Installation in Home Assistant

### Option 1: Über HACS (Empfohlen)
1. Öffne **HACS** in Home Assistant.
2. Klicke oben rechts auf das Drei-Punkte-Menü -> **Benutzerdefinierte Repositories**.
3. Gib deine GitHub-Repository-URL ein und wähle die Kategorie **Integration**.
4. Klicke auf **Herunterladen** und starte Home Assistant neu.

### Option 2: Manuelle Installation
1. Lade den Ordner `custom_components/booyood` herunter.
2. Kopiere das Verzeichnis auf deinen Home Assistant Server nach:
   ```
   /config/custom_components/booyood/
   ```
3. Starte Home Assistant neu.

---

## ⚙️ Konfiguration

1. **Automatische Erkennung**:
   Befindet sich die Standheizung in Bluetooth-Reichweite von Home Assistant (Name beginnt mit `NK-`, `Nordkapp`, `BYD-` oder `BAC-`), erscheint automatisch ein Dialog zum Hinzufügen.
2. **Manuelles Hinzufügen**:
   Unter **Einstellungen -> Geräte & Dienste -> Integration hinzufügen** nach **Nordkapp & Booyood Diesel Heater BLE** suchen.
3. Wähle die MAC-Adresse aus, bestätige die PIN (Standard: `1234`) und wähle optional bereits einen externen Temperatursensor.
4. **Externen Sensor nachträglich ändern**:
   Unter **Einstellungen -> Geräte & Dienste -> Nordkapp Heater -> Konfigurieren** kann der externe Raumtemperatursensor jederzeit im Options-Dialog gewechselt oder deaktiviert werden.

---

## 💡 Lovelace Dashboard Karten

### 1. Mushroom Climate Card (mit Lüftungs-Button)
```yaml
type: custom:mushroom-climate-card
entity: climate.nordkapp_heater
show_complete_name: true
hvac_modes:
  - 'off'
  - heat
  - fan_only
fill_container: false
```

### 2. Standard Thermostat Card
```yaml
type: thermostat
entity: climate.nordkapp_heater
```

### 3. Übersicht aller Sensoren, Schalter & Betriebsmodi
```yaml
type: entities
title: Nordkapp Standheizung Steuerung
entities:
  - entity: climate.nordkapp_heater
  - entity: select.nordkapp_heater_operating_mode
  - entity: switch.nordkapp_heater_auto_start_stop
  - entity: number.nordkapp_heater_startup_temperature_offset
  - entity: number.nordkapp_heater_shutdown_temperature_offset
  - entity: button.nordkapp_heater_sync_time
  - entity: sensor.nordkapp_heater_operating_phase
  - entity: sensor.nordkapp_heater_current_gear
  - entity: sensor.nordkapp_heater_ambient_temperature
  - entity: sensor.nordkapp_heater_heat_exchanger_temperature
  - entity: sensor.nordkapp_heater_supply_voltage
  - entity: sensor.nordkapp_heater_carbon_monoxide
  - entity: sensor.nordkapp_heater_altitude
  - entity: sensor.nordkapp_heater_remaining_runtime
  - entity: sensor.nordkapp_heater_fault_status
  - entity: binary_sensor.nordkapp_heater_heating_running
  - entity: binary_sensor.nordkapp_heater_problem
```

---

## 🚀 GitHub Veröffentlichung

Um dieses Repository unter Ihrem eigenen GitHub-Account zu veröffentlichen:

1. Auf [github.com/new](https://github.com/new) ein neues öffentliches Repository anlegen (z. B. `nordkapp-diesel-heater-ble`).
2. Im lokalen Projektordner ausführen:
   ```bash
   git init -b main
   git add .
   git commit -m "feat: initial release of Nordkapp & Booyood BLE integration with fan, auto-stop and time-sync"
   git remote add origin https://github.com/<DEIN-BENUTZERNAME>/nordkapp-diesel-heater-ble.git
   git push -u origin main
   ```
3. Auf GitHub unter **Releases -> Create a new release** das Release `v1.1.0` taggen.

---

## 📄 Lizenz

Dieses Projekt steht unter der [MIT Lizenz](LICENSE).  
Alle Marken (*Nordkapp®*, *Booyood*) gehören ihren jeweiligen Inhabern und werden nur zur Kompatibilitätsbeschreibung verwendet.