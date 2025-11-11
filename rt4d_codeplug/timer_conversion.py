"""Timer conversion utilities for RT4D firmware.

The RT4D firmware uses a non-linear conversion function to convert timer indices
to actual seconds. This module provides utilities to convert between firmware
indices and actual second values.

Firmware conversion function (from app/settings.c):
    uint32_t CONV_GetDuration(uint8_t Duration)
    {
        if (Duration == 0) {
            return 0;
        }
        if (Duration == 1 || Duration == 2 || Duration == 3) {
            return Duration * 5;
        }
        return (Duration - 2) * 15;
    }
"""

from typing import Dict, List, Tuple


def index_to_seconds(index: int) -> int:
    """Convert firmware timer index to actual seconds.

    Args:
        index: Firmware timer index (0-255)

    Returns:
        Actual seconds represented by the index

    Examples:
        >>> index_to_seconds(0)
        0
        >>> index_to_seconds(3)
        15
        >>> index_to_seconds(8)
        90
        >>> index_to_seconds(30)
        420
    """
    if index == 0:
        return 0

    if index in (1, 2, 3):
        return index * 5

    return (index - 2) * 15


def seconds_to_index(seconds: int) -> int:
    """Convert seconds to firmware timer index.

    Args:
        seconds: Number of seconds

    Returns:
        Firmware timer index that produces the given seconds

    Raises:
        ValueError: If seconds value doesn't map to a valid index

    Examples:
        >>> seconds_to_index(0)
        0
        >>> seconds_to_index(15)
        3
        >>> seconds_to_index(90)
        8
        >>> seconds_to_index(420)
        30
    """
    if seconds == 0:
        return 0

    # Handle special cases (1-3)
    if seconds == 5:
        return 1
    elif seconds == 10:
        return 2
    elif seconds == 15:
        return 3

    # Handle general case
    if seconds % 15 != 0:
        raise ValueError(f"Invalid seconds value: {seconds}. Must be 0, 5, 10, 15, or a multiple of 15 starting from 30.")

    index = (seconds // 15) + 2

    # Validate the conversion
    if index_to_seconds(index) != seconds:
        raise ValueError(f"Invalid seconds value: {seconds}")

    return index


def generate_timer_values(max_index: int = 40) -> Dict[int, str]:
    """Generate timer dropdown values for given index range.

    Args:
        max_index: Maximum index to generate (inclusive)

    Returns:
        Dictionary mapping index to formatted time string

    Example:
        {0: "Off", 1: "5s", 2: "10s", 3: "15s", 4: "30s", ...}
    """
    values = {}

    for index in range(max_index + 1):
        seconds = index_to_seconds(index)

        if seconds == 0:
            values[index] = "Off"
        elif seconds < 60:
            values[index] = f"{seconds}s"
        elif seconds % 60 == 0:
            minutes = seconds // 60
            values[index] = f"{minutes}m"
        else:
            minutes = seconds // 60
            secs = seconds % 60
            values[index] = f"{minutes}m{secs}s"

    return values


def get_all_valid_seconds(max_index: int = 40) -> List[int]:
    """Get list of all valid second values for given index range.

    Args:
        max_index: Maximum index to generate (inclusive)

    Returns:
        List of valid second values in ascending order
    """
    return [index_to_seconds(i) for i in range(max_index + 1)]


def get_index_seconds_pairs(max_index: int = 40) -> List[Tuple[int, int]]:
    """Get list of (index, seconds) pairs for given index range.

    Args:
        max_index: Maximum index to generate (inclusive)

    Returns:
        List of (index, seconds) tuples
    """
    return [(i, index_to_seconds(i)) for i in range(max_index + 1)]


# Pre-generated common timer values
TOT_MAX_INDEX = 40  # Maximum TOT index (40 = 570s = 9.5m)
LED_MENU_MAX_INDEX = 30  # Reasonable max for LED/Menu timers (30 = 420s = 7m)
LOCK_MAX_INDEX = 40  # Maximum lock timer index
POWER_SAVE_MAX_INDEX = 40  # Maximum power save timer index
