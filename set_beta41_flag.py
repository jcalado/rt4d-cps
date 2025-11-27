#!/usr/bin/env python3
"""Utility script to force the beta41 layout flag on an RT-4D radio.

The beta41+ firmware layout is detected by the radio when the last 4 bytes of
the main settings block contain the ASCII magic word ``DTCN``. Some early
codeplugs do not carry this marker, which prevents the extended layout from
being enabled. This script connects to the radio, reads the main settings
region, and writes the ``DTCN`` marker if it is missing.
"""

from __future__ import annotations

import argparse
import sys

from rt4d_uart import RT4DUART
from rt4d_codeplug.constants import (
    SPI_REGIONS, SIZE_CFG, BETA41_MAGIC,
    SETTINGS_BANK0_ADDR, SETTINGS_BANK1_ADDR,
    BANK0_MAGIC_OFFSET, BANK1_MAGIC_OFFSET
)
from rt4d_codeplug.utils import detect_settings_bank

REGION_NAME = "main_settings"
BETA41_OFFSET = SIZE_CFG - len(BETA41_MAGIC)


def _format_flag(flag: bytes) -> str:
    """Return a printable representation of the flag bytes."""
    try:
        text = flag.decode("ascii")
    except UnicodeDecodeError:
        text = "?"
    hex_value = flag.hex().upper()
    return f"{text} (0x{hex_value})"


def detect_banks(port: str, baudrate: int) -> int:
    """Detect and display which bank(s) contain DTCN magic bytes."""
    uart = RT4DUART()
    success, _actual_baud, message = uart.open_with_fallback(port, baudrate)
    if not success:
        print(f"Serial connection failed: {message}")
        return 1

    print(message)

    try:
        if uart.is_bootloader_mode():
            print("Radio appears to be in bootloader mode. Power it on normally and try again.")
            return 1

        if not uart.command_notify():
            print("Radio did not acknowledge the notify command.")
            return 1

        # Check bank 0
        bank0_magic = uart.read_spi_region(BANK0_MAGIC_OFFSET, len(BETA41_MAGIC))
        bank0_has_dtcn = bank0_magic == BETA41_MAGIC

        # Check bank 1
        bank1_magic = uart.read_spi_region(BANK1_MAGIC_OFFSET, len(BETA41_MAGIC))
        bank1_has_dtcn = bank1_magic == BETA41_MAGIC

        # Detect active bank (follows firmware logic)
        active_bank_addr = detect_settings_bank(uart)

        print("\n=== Bank Detection Results ===")
        print(f"Bank 0 (0x{SETTINGS_BANK0_ADDR:06X}): {_format_flag(bank0_magic)} {'[DTCN FOUND]' if bank0_has_dtcn else ''}")
        print(f"Bank 1 (0x{SETTINGS_BANK1_ADDR:06X}): {_format_flag(bank1_magic)} {'[DTCN FOUND]' if bank1_has_dtcn else ''}")
        print(f"\nActive bank (firmware logic): 0x{active_bank_addr:06X}")

        if bank0_has_dtcn and bank1_has_dtcn:
            print("\nWarning: DTCN found in both banks! Firmware uses bank 0 (checked first).")
            print("Consider using --clear-bank1 to remove the unused flag.")
        elif not bank0_has_dtcn and not bank1_has_dtcn:
            print("\nNo DTCN found in either bank (legacy/non-beta41 firmware).")

        return 0

    finally:
        try:
            uart.command_close()
        except Exception:
            pass
        uart.close()


def clear_bank1(port: str, baudrate: int, dry_run: bool, assume_yes: bool) -> int:
    """Clear DTCN magic from bank 1 (0x3000) to migrate settings to bank 0.

    Note: This operation requires direct SPI write support which may not be
    available. For now, this provides detection and information only.
    """
    uart = RT4DUART()
    success, _actual_baud, message = uart.open_with_fallback(port, baudrate)
    if not success:
        print(f"Serial connection failed: {message}")
        return 1

    print(message)

    try:
        if uart.is_bootloader_mode():
            print("Radio appears to be in bootloader mode. Power it on normally and try again.")
            return 1

        if not uart.command_notify():
            print("Radio did not acknowledge the notify command.")
            return 1

        # Check both banks
        bank0_magic = uart.read_spi_region(BANK0_MAGIC_OFFSET, len(BETA41_MAGIC))
        bank1_magic = uart.read_spi_region(BANK1_MAGIC_OFFSET, len(BETA41_MAGIC))

        print(f"Bank 0 flag: {_format_flag(bank0_magic)}")
        print(f"Bank 1 flag: {_format_flag(bank1_magic)}")

        if bank1_magic != BETA41_MAGIC:
            print("\nBank 1 does not have DTCN magic. Nothing to clear.")
            return 0

        if bank0_magic != BETA41_MAGIC:
            print("\nWarning: Bank 0 does not have DTCN magic!")
            print("You should write DTCN to bank 0 first (using default mode) before clearing bank 1.")
            if not dry_run and not assume_yes:
                response = input("Do you want to continue anyway? [y/N]: ").strip().lower()
                if response not in ("y", "yes"):
                    print("Aborted by user.")
                    return 1

        if dry_run:
            print("\nDry-run: Would clear DTCN from bank 1.")
            print("Note: Actual clearing requires direct SPI write support.")
            return 0

        print("\nNote: Direct writing to bank 1 is not yet fully implemented.")
        print("To migrate from bank 1 to bank 0:")
        print("  1. Back up your current codeplug")
        print("  2. Write it back to the radio (will go to bank 0)")
        print("  3. Bank 0 will become active automatically")
        return 1

    finally:
        try:
            uart.command_close()
        except Exception:
            pass
        uart.close()


def ensure_beta41_flag(port: str, baudrate: int, dry_run: bool, assume_yes: bool, force: bool) -> int:
    """Connect to the radio and make sure the beta41 flag is set.

    Always writes to bank 0 (0x2000) as per firmware specification.
    """
    uart = RT4DUART()
    success, _actual_baud, message = uart.open_with_fallback(port, baudrate)
    if not success:
        print(f"Serial connection failed: {message}")
        return 1

    print(message)

    try:
        if uart.is_bootloader_mode():
            print("Radio appears to be in bootloader mode. Power it on normally and try again.")
            return 1

        if not uart.command_notify():
            print("Radio did not acknowledge the notify command.")
            return 1

        # Always write to bank 0 (0x2000) as per firmware specification
        region_info = SPI_REGIONS[REGION_NAME]
        current_region = uart.read_spi_region(region_info["address"], region_info["size"])
        if current_region is None:
            print("Failed to read settings from bank 0.")
            return 1

        current_flag = current_region[BETA41_OFFSET:BETA41_OFFSET + len(BETA41_MAGIC)]
        print(f"Current beta41 flag in bank 0: {_format_flag(current_flag)}")

        if current_flag == BETA41_MAGIC and not force:
            print("Beta41 flag is already set in bank 0. Nothing to do.")
            return 0

        if dry_run:
            if current_flag == BETA41_MAGIC:
                print("Dry-run: would rewrite the existing DTCN magic bytes to bank 0.")
            else:
                print("Dry-run: would update the magic bytes to 'DTCN' in bank 0.")
            return 0

        updated_region = bytearray(current_region)
        updated_region[BETA41_OFFSET:BETA41_OFFSET + len(BETA41_MAGIC)] = BETA41_MAGIC

        if not assume_yes:
            response = input("Proceed with writing DTCN to bank 0? [y/N]: ").strip().lower()
            if response not in ("y", "yes"):
                print("Aborted by user.")
                return 1

        print("Writing DTCN magic to bank 0...")
        if not uart.write_spi_region(bytes(updated_region), REGION_NAME):
            print("Failed to write to bank 0.")
            return 1

        # Verify
        verify_region = uart.read_spi_region(region_info["address"], region_info["size"])
        if verify_region is None:
            print("Warning: unable to re-read settings to verify the change.")
            return 0

        verify_flag = verify_region[BETA41_OFFSET:BETA41_OFFSET + len(BETA41_MAGIC)]
        if verify_flag == BETA41_MAGIC:
            print("Beta41 flag successfully written to bank 0: 'DTCN'.")
            return 0

        print("Warning: verification read did not match expected magic bytes.")
        print(f"Observed bytes after write: {_format_flag(verify_flag)}")
        return 1

    finally:
        try:
            uart.command_close()
        except Exception:
            pass
        uart.close()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage beta41 layout magic bytes (DTCN) on an RT-4D radio",
    )
    parser.add_argument("--port", "-p", required=True, help="Serial port for the radio (e.g., /dev/ttyUSB0, COM3)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Requested baud rate (default: 115200)")

    # Operation modes (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--detect",
        action="store_true",
        help="Detect and display which bank(s) contain DTCN magic bytes",
    )
    mode_group.add_argument(
        "--clear-bank1",
        action="store_true",
        help="Show information about clearing DTCN from bank 1 (migration guidance)",
    )

    # Options for write mode (default)
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing to the radio")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip the confirmation prompt")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Write the magic bytes even if they are already set to DTCN",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # Handle different operation modes
    if args.detect:
        return detect_banks(port=args.port, baudrate=args.baud)

    if args.clear_bank1:
        return clear_bank1(
            port=args.port,
            baudrate=args.baud,
            dry_run=args.dry_run,
            assume_yes=args.yes,
        )

    # Default: write DTCN flag to bank 0 (0x2000)
    return ensure_beta41_flag(
        port=args.port,
        baudrate=args.baud,
        dry_run=args.dry_run,
        assume_yes=args.yes,
        force=args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
