# RT-4D CPS

A codeplug programming software for the Radtel RT-4D, with full support for [DualTachyon's REFW](https://github.com/DualTachyon) custom firmware.

> [!CAUTION]
> This software is **not compatible** with Radtel's stock firmware >= 3.18.

[![Support me on Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20this%20project-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/jcalado)

## Download

Prebuilt binaries for **Windows**, **macOS**, and **Linux** are available on the [Releases page](https://github.com/jcalado/rt4d-cps/releases).

The app checks for updates automatically — you'll be notified when a new version is available.

## Screenshots

![Dark Mode](screenshots/dark.png)

![Read from radio](screenshots/read.png)

## Features

### Radio Communication
- **Read** the full codeplug from your radio over USB
- **Write** changes back — select exactly which regions to flash (channels, contacts, zones, etc.)
- **Backup** the entire SPI flash as a binary dump
- Auto-detection of serial port and firmware version

### Channel Management
- Edit up to **1024 channels** — both analog (FM/AM) and digital (DMR)
- Set frequencies, power level, CTCSS/DCS tones, bandwidth, time slot, color code, and more
- Drag-and-drop reordering, copy/paste, and multi-select delete
- Search and filter channels by name
- Automatic repeater offset calculation (configurable VHF/UHF shifts)

### Contacts & Groups
- Manage DMR contacts (Private, Group, All Call)
- Create and assign RX group lists with drag-and-drop

### Zones
- Organize channels into zones (up to 250 channels per zone)

### Address Book
- Import large DMR user databases (100k+ contacts) from CSV
- Search by DMR ID, callsign, or name
- Write the address book directly to your radio

### Encryption & DTMF
- Manage up to 32 encryption keys (ARC4, AES-128, AES-256)
- Configure DTMF sequences and remote control codes

### Messages
- View and edit preset DMR SMS messages

### FM Radio Presets
- Configure FM broadcast presets (76–108 MHz)

### Radio Settings
- Radio ID and callsign
- Display, audio, power save, scan, and startup options
- REFW-specific settings: scan speed, spectrum threshold, callsign lookup, and more

### Import / Export
- **CSV** import and export for channels (with replace or append mode)
- **CSV** import and export for DMR address books
- Open and save `.4rdmf` codeplug files

### Interface
- Dark, light, and system themes
- Keyboard shortcuts throughout
- Status bar, tooltips, and unsaved-changes warnings

## Running from Source

Requires Python 3.9+.

```bash
pip install -r requirements.txt
python3 rt4d_gui.py
```

### Command-Line Interface

A CLI is also available for scripting and automation:

```bash
# List channels
python3 rt4d_editor.py --file your.4rdmf --list-channels

# Export channels to CSV
python3 rt4d_editor.py --file your.4rdmf --export-csv channels.csv

# Backup radio over serial
python3 rt4d_editor.py --port COM3 --backup backup.bin

# Flash specific regions
python3 rt4d_editor.py --port COM3 --flash your.4rdmf --flash-regions channels contacts
```
