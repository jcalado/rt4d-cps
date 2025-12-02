#!/usr/bin/env python3
"""
RT-4D Channel Editor & Flasher
Command-line tool for editing RT-4D radio codeplug files and flashing to radio
"""

import argparse
import sys
import csv
from pathlib import Path

from rt4d_codeplug import (
    Channel, Contact, Zone, Codeplug,
    CodeplugParser, CodeplugSerializer,
    ChannelMode, PowerLevel, ScanMode
)
from rt4d_uart import RT4DUART
from rt4d_codeplug.constants import SPI_REGIONS
from rt4d_codeplug.utils import detect_settings_bank


def list_channels(codeplug: Codeplug, verbose: bool = False):
    """List all channels in codeplug"""
    channels = codeplug.get_active_channels()
    print(f"\nFound {len(channels)} channels:")
    print("-" * 100)
    print(f"{'Pos':<5} {'Name':<17} {'RX Freq':<12} {'TX Freq':<12} {'Mode':<8} {'Power':<6} {'Scan':<6}")
    print("-" * 100)

    for ch in sorted(channels, key=lambda c: c.position):
        mode_str = "Digital" if ch.is_digital() else "Analog"
        power_str = "High" if ch.power == PowerLevel.HIGH else "Low"
        scan_str = "Yes" if ch.scan == ScanMode.ADD else "No"

        print(f"{ch.position:<5} {ch.name:<17} {ch.rx_freq:<12.5f} {ch.tx_freq:<12.5f} "
              f"{mode_str:<8} {power_str:<6} {scan_str:<6}")

        if verbose and ch.is_digital():
            print(f"      DMR: Slot={ch.dmr_time_slot + 1}, CC={ch.dmr_color_code}, "
                  f"Contact UUID={ch.contact_uuid[:8] if ch.contact_uuid else 'None'}...")


def list_contacts(codeplug: Codeplug):
    """List all contacts in codeplug"""
    contacts = codeplug.get_active_contacts()
    print(f"\nFound {len(contacts)} contacts:")
    print("-" * 80)
    print(f"{'#':<5} {'Name':<20} {'Type':<15} {'DMR ID':<10}")
    print("-" * 80)

    for contact in sorted(contacts, key=lambda c: c.index):
        print(f"{contact.index + 1:<5} {contact.name:<20} {contact.contact_type.name:<15} {contact.dmr_id:<10}")


def list_group_lists(codeplug: Codeplug, verbose: bool = False):
    """List all group lists in codeplug"""
    group_lists = codeplug.get_active_group_lists()
    print(f"\nFound {len(group_lists)} group lists:")
    print("-" * 80)
    print(f"{'#':<5} {'Name':<20} {'Contacts':<10}")
    print("-" * 80)

    for gl in sorted(group_lists, key=lambda g: g.index):
        print(f"{gl.index + 1:<5} {gl.name:<20} {len(gl.contacts):<10}")

        if verbose and len(gl.contacts) > 0:
            print(f"      Contacts in this group:")
            for contact_idx in gl.contacts:
                contact = codeplug.get_contact(contact_idx)
                if contact:
                    print(f"        - {contact.name} (ID: {contact.dmr_id}, Type: {contact.contact_type.name})")
                else:
                    print(f"        - Contact #{contact_idx + 1} (not found)")
            print()


def list_zones(codeplug: Codeplug):
    """List all zones in codeplug"""
    zones = codeplug.get_active_zones()
    print(f"\nFound {len(zones)} zones:")
    print("-" * 80)
    print(f"{'#':<5} {'Name':<20} {'Channels':<10}")
    print("-" * 80)

    for zone in sorted(zones, key=lambda z: z.index):
        print(f"{zone.index + 1:<5} {zone.name:<20} {len(zone.channels):<10}")


def show_settings(codeplug: Codeplug):
    """Display radio settings"""
    if not codeplug.settings:
        print("No radio settings found")
        return

    s = codeplug.settings
    print("\n" + "=" * 80)
    print("RADIO SETTINGS")
    print("=" * 80)

    print("\n--- Identity ---")
    print(f"Radio Name:         {s.radio_name}")
    print(f"Radio ID (DMR):     {s.radio_id}")
    print(f"Startup Message:    {s.startup_message}")
    if s.startup_password:
        print(f"Startup Password:   {'*' * len(s.startup_password)} (protected)")

    print("\n--- Audio & UI ---")
    print(f"Voice Prompt:       {'On' if s.voice_prompt else 'Off'}")
    print(f"Key Beep:           {'On' if s.key_beep else 'Off'}")
    print(f"Key Lock:           {['Manual', 'Auto'][s.key_lock] if s.key_lock < 2 else s.key_lock}")

    print("\n--- Display ---")
    print(f"LED Timer:          {s.led_timer}")
    print(f"Menu Timer:         {s.menu_timer}")

    print("\n--- Power ---")
    print(f"Power Save Mode:    {s.power_save_mode}")
    print(f"Auto Power Off:     {'On' if s.apo_enabled else 'Off'}")

    print("\n--- Operation ---")
    print(f"Dual Watch:         {'On' if s.dual_watch else 'Off'}")
    print(f"Band A Mode:        {['Channel', 'VFO'][s.work_mode_a] if s.work_mode_a < 2 else s.work_mode_a}")
    print(f"Band A Channel:     {s.channel_a + 1}")
    print(f"Band B Mode:        {['Channel', 'VFO'][s.work_mode_b] if s.work_mode_b < 2 else s.work_mode_b}")
    print(f"Band B Channel:     {s.channel_b + 1}")

    print("=" * 80 + "\n")


def export_csv(codeplug: Codeplug, output_file: str):
    """Export channels to CSV"""
    channels = codeplug.get_active_channels()

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Position', 'Name', 'RX Freq', 'TX Freq', 'Mode', 'Power',
                         'Scan', 'Color Code', 'Time Slot', 'Contact UUID', 'Group List UUID'])

        for ch in sorted(channels, key=lambda c: c.position):
            mode = 'Digital' if ch.is_digital() else 'Analog'
            power = 'High' if ch.power == PowerLevel.HIGH else 'Low'
            scan = 'Add' if ch.scan == ScanMode.ADD else 'Remove'

            writer.writerow([
                ch.position, ch.name, ch.rx_freq, ch.tx_freq, mode, power, scan,
                ch.dmr_color_code if ch.is_digital() else '',
                ch.dmr_time_slot + 1 if ch.is_digital() else '',
                ch.contact_uuid if ch.is_digital() else '',
                ch.group_list_uuid if ch.is_digital() else ''
            ])

    print(f"Exported {len(channels)} channels to {output_file}")


def backup_from_radio(port: str, output_file: str, regions: list = None):
    """Backup codeplug from radio via serial"""
    print(f"Connecting to radio on {port}...")
    uart = RT4DUART()

    try:
        uart.open(port)

        if uart.is_bootloader_mode():
            print("Error: Radio is in bootloader mode, not normal mode!")
            return False

        uart.command_notify()

        # Full backup (raw SPI dump)
        if regions is None:
            success = uart.read_spi_dump(output_file)
            uart.command_close()
            uart.close()
            if success:
                print(f"Full backup saved to {output_file}")
            return success

        # Selective backup (specific regions to .4rdmf format)
        print(f"Backing up regions: {', '.join(regions)}")

        # Create empty codeplug structure
        from rt4d_codeplug.constants import TOTAL_SIZE, OFFSET_CFG, OFFSET_CHANNELS, OFFSET_CONTACTS
        from rt4d_codeplug.constants import OFFSET_GROUPLISTS, OFFSET_ENCRYPT, OFFSET_ZONES, OFFSET_FM
        from rt4d_codeplug.constants import SIZE_CFG, SIZE_CHANNELS, SIZE_CONTACTS, SIZE_GROUPLISTS
        from rt4d_codeplug.constants import SIZE_ENCRYPT, SIZE_ZONES, SIZE_FM

        codeplug_data = bytearray(b'\xff' * TOTAL_SIZE)

        # Detect which bank contains active settings (beta41+ dual-bank support)
        settings_bank_addr = detect_settings_bank(uart)
        print(f"Detected settings at bank address: 0x{settings_bank_addr:06X}")

        # Map region names to offsets in .4rdmf file
        region_map = {
            'main_settings': (OFFSET_CFG, SIZE_CFG, settings_bank_addr),
            'channels': (OFFSET_CHANNELS, SIZE_CHANNELS, 0x004000),
            'contacts': (OFFSET_CONTACTS, SIZE_CONTACTS, 0x05C000),
            'groups': (OFFSET_GROUPLISTS, SIZE_GROUPLISTS, 0x07C000),
            'dmr_keys': (OFFSET_ENCRYPT, SIZE_ENCRYPT, 0x082000),
            'zones': (OFFSET_ZONES, SIZE_ZONES, 0x01C000),
            'fm_settings': (OFFSET_FM, SIZE_FM, 0x0D6000),
        }

        for region_name in regions:
            if region_name not in region_map:
                print(f"Warning: Unknown region '{region_name}', skipping")
                continue

            file_offset, size, spi_address = region_map[region_name]
            print(f"Reading {region_name} ({size} bytes)...")

            region_data = uart.read_spi_region(spi_address, size)
            if region_data is None:
                print(f"Failed to read {region_name}")
                uart.command_close()
                uart.close()
                return False

            codeplug_data[file_offset:file_offset + size] = region_data

        # Write to file
        with open(output_file, 'wb') as f:
            f.write(codeplug_data)

        uart.command_close()
        uart.close()
        print(f"Backup saved to {output_file}")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


def flash_to_radio(port: str, input_file: str, regions: list = None):
    """Flash codeplug to radio via serial"""
    print(f"Reading codeplug from {input_file}...")

    # Parse codeplug file
    parser = CodeplugParser.from_file(input_file)
    codeplug = parser.parse()

    print(f"Connecting to radio on {port}...")
    uart = RT4DUART()

    try:
        uart.open(port)

        if uart.is_bootloader_mode():
            print("Error: Radio is in bootloader mode, not normal mode!")
            return False

        uart.command_notify()

        # Serialize codeplug for flashing
        data = CodeplugSerializer.serialize(codeplug)

        # Flash regions
        regions_to_flash = regions or ["main_settings", "channels", "contacts", "groups", "zones"]

        for region_name in regions_to_flash:
            if region_name not in SPI_REGIONS:
                print(f"Warning: Unknown region '{region_name}', skipping")
                continue

            region = SPI_REGIONS[region_name]

            # Extract appropriate data based on region
            if region_name == "channels":
                region_data = data[0x1000:0xD000]
            elif region_name == "contacts":
                region_data = data[0xD000:0x1D000]
            elif region_name == "groups":
                region_data = data[0x1D000:0x20000]
            elif region_name == "zones":
                region_data = data[0x23000:0x43000]
            elif region_name == "main_settings":
                region_data = data[0x0:0x1000]
            else:
                print(f"Warning: Don't know how to extract data for region '{region_name}'")
                continue

            print(f"Flashing {region_name}...")
            if not uart.write_spi_region(region_data, region_name):
                print(f"Failed to flash {region_name}")
                return False

        uart.command_close()
        uart.close()

        print("Flashing complete!")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='RT-4D Channel Editor & Flasher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List channels in a file
  %(prog)s --file rt4d.4rdmf --list-channels

  # Export channels to CSV
  %(prog)s --file rt4d.4rdmf --export-csv channels.csv

  # Backup entire radio (full 4MB SPI dump)
  %(prog)s --port COM3 --backup backup.bin

  # Backup only channels (creates .4rdmf file)
  %(prog)s --port COM3 --backup channels.4rdmf --backup-regions channels

  # Backup channels and contacts
  %(prog)s --port COM3 --backup partial.4rdmf --backup-regions channels contacts

  # Flash channels to radio
  %(prog)s --port COM3 --flash rt4d.4rdmf --flash-regions channels contacts
        """
    )

    # File operations
    parser.add_argument('--file', '-f', help='.4rdmf codeplug file')

    # Radio operations
    parser.add_argument('--port', '-p', help='Serial port (e.g., COM3, /dev/ttyUSB0)')
    parser.add_argument('--backup', '-b', help='Backup radio to file')
    parser.add_argument('--backup-regions', nargs='+',
                        help='Specific regions to backup (default: full backup). '
                        'Options: main_settings, channels, contacts, groups, dmr_keys, zones, fm_settings')
    parser.add_argument('--flash', help='Flash file to radio')
    parser.add_argument('--flash-regions', nargs='+', help='Regions to flash (default: all)')

    # List operations
    parser.add_argument('--list-channels', '-lc', action='store_true', help='List all channels')
    parser.add_argument('--list-contacts', '-lt', action='store_true', help='List all contacts')
    parser.add_argument('--list-groups', '-lg', action='store_true', help='List all group lists')
    parser.add_argument('--list-zones', '-lz', action='store_true', help='List all zones')
    parser.add_argument('--show-settings', '-s', action='store_true', help='Show radio settings')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    # Export
    parser.add_argument('--export-csv', '-e', help='Export channels to CSV file')

    args = parser.parse_args()

    # File-based operations
    if args.file:
        if not Path(args.file).exists():
            print(f"Error: File not found: {args.file}")
            return 1

        print(f"Loading codeplug from {args.file}...")
        parser_obj = CodeplugParser.from_file(args.file)
        codeplug = parser_obj.parse()

        if args.list_channels:
            list_channels(codeplug, args.verbose)

        if args.list_contacts:
            list_contacts(codeplug)

        if args.list_groups:
            list_group_lists(codeplug, args.verbose)

        if args.list_zones:
            list_zones(codeplug)

        if args.show_settings:
            show_settings(codeplug)

        if args.export_csv:
            export_csv(codeplug, args.export_csv)

    # Radio operations
    if args.port:
        if args.backup:
            if not backup_from_radio(args.port, args.backup, args.backup_regions):
                return 1

        if args.flash:
            if not flash_to_radio(args.port, args.flash, args.flash_regions):
                return 1

    if not any([args.file, args.port]):
        parser.print_help()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
