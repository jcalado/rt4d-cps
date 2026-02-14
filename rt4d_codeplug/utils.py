"""RT-4D Codeplug Utilities"""

from typing import Optional

from .constants import (
    BETA41_MAGIC,
    SETTINGS_BANK0_ADDR,
    SETTINGS_BANK1_ADDR,
    BANK0_MAGIC_OFFSET,
    BANK1_MAGIC_OFFSET,
    ZONE_PAGE_SIZE,
    ZONE_AB_BANK_OFFSET,
    ZONE_AB_MARKER_OFFSET,
    ZONE_AB_MARKER,
)


def detect_settings_bank(uart_device) -> tuple[int, bool]:
    """
    Detect which bank contains active settings by checking DTCN magic bytes.

    Implements firmware logic:
    - Check 0x2FFC for DTCN magic (bank 0)
    - If found, return 0x2000 (bank 0 address)
    - Otherwise, check 0x3FFC for DTCN magic (bank 1)
    - If found, return 0x3000 (bank 1 address)
    - Otherwise, return 0x2000 (legacy/non-beta41)

    Firmware recognizes first DTCN and stops checking the other bank.

    Args:
        uart_device: UART device with read_spi_region() method

    Returns:
        (address, is_beta41): Settings bank address and whether radio is beta41+
    """
    # Check bank 0 first (0x2FFC)
    bank0_magic = uart_device.read_spi_region(BANK0_MAGIC_OFFSET, 4)
    if bank0_magic == BETA41_MAGIC:
        return SETTINGS_BANK0_ADDR, True

    # Check bank 1 (0x3FFC)
    bank1_magic = uart_device.read_spi_region(BANK1_MAGIC_OFFSET, 4)
    if bank1_magic == BETA41_MAGIC:
        return SETTINGS_BANK1_ADDR, True

    # Default to bank 0 (legacy firmware without beta41)
    return SETTINGS_BANK0_ADDR, False


def read_zone_region_ab(uart_device, base_address: int, size: int) -> Optional[bytes]:
    """Read zone region with per-page A/B bank detection (beta41+).

    Each 4KB page may independently live in bank A or bank B.
    Checks an 8-byte marker at offset 0xFF8 within each page to decide.

    Args:
        uart_device: UART device with read_spi_region() method
        base_address: Start address of zone region in SPI flash
        size: Total size of zone region in bytes

    Returns:
        Zone data bytes, or None on read failure
    """
    pages = []
    for addr in range(base_address, base_address + size, ZONE_PAGE_SIZE):
        marker_a = uart_device.read_spi_region(addr + ZONE_AB_MARKER_OFFSET, 8)
        marker_b = uart_device.read_spi_region(addr + ZONE_AB_BANK_OFFSET + ZONE_AB_MARKER_OFFSET, 8)

        # Use bank B if it has DTCN, unless only A has the pristine marker
        read_addr = addr
        a_valid = marker_a == ZONE_AB_MARKER
        b_has_dtcn = marker_b is not None and marker_b[4:] == BETA41_MAGIC
        if b_has_dtcn and not (a_valid and marker_b != ZONE_AB_MARKER):
            read_addr = addr + ZONE_AB_BANK_OFFSET

        data = uart_device.read_spi_region(read_addr, ZONE_PAGE_SIZE)
        if data is None:
            return None
        pages.append(data)

    return b''.join(pages)
