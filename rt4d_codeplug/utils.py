"""RT-4D Codeplug Utilities"""

from .constants import (
    BETA41_MAGIC,
    SETTINGS_BANK0_ADDR,
    SETTINGS_BANK1_ADDR,
    BANK0_MAGIC_OFFSET,
    BANK1_MAGIC_OFFSET,
)


def detect_settings_bank(uart_device):
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
        int: Settings bank address (0x2000 or 0x3000)
    """
    # Check bank 0 first (0x2FFC)
    bank0_magic = uart_device.read_spi_region(BANK0_MAGIC_OFFSET, 4)
    if bank0_magic == BETA41_MAGIC:
        return SETTINGS_BANK0_ADDR

    # Check bank 1 (0x3FFC)
    bank1_magic = uart_device.read_spi_region(BANK1_MAGIC_OFFSET, 4)
    if bank1_magic == BETA41_MAGIC:
        return SETTINGS_BANK1_ADDR

    # Default to bank 0 (legacy firmware without beta41)
    return SETTINGS_BANK0_ADDR
