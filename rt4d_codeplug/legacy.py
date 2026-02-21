"""Legacy (pre-beta41) codeplug format support.

Handles reading old-format codeplug files so they can be converted to the
current beta41+ format.  The main CodeplugParser delegates here when the
DTCN magic is absent.
"""

import struct
from typing import Optional

from .models import (
    Channel, ChannelMode, PowerLevel, ScanMode, AnalogModulation,
)
from .constants import (
    OFFSET_CHANNELS, CHANNEL_SIZE, CHANNEL_MODE_DIGITAL,
    POWER_HIGH, SCAN_ADD, EMPTY_BYTE,
    GROUP_LIST_SIZE_LEGACY, MAX_GROUP_LISTS_LEGACY, MAX_GROUP_LIST_IDS_LEGACY,
)
from .tones import decode_subaudio_bytes


def parse_channel_legacy(data: bytes, index: int) -> Optional[Channel]:
    """Parse a single channel using the legacy (pre-beta41) layout.

    Parameters
    ----------
    data : bytes
        Full codeplug binary data.
    index : int
        0-based channel slot index.
    """
    from .parser import CodeplugParser  # for _parse_bcd

    offset = OFFSET_CHANNELS + (index * CHANNEL_SIZE)
    ch_data = data[offset:offset + CHANNEL_SIZE]

    # Check if channel is empty
    if ch_data[2] >= 2:
        return None

    try:
        # Basic fields
        mode_byte = ch_data[0x02]
        mode = ChannelMode.DIGITAL if mode_byte == CHANNEL_MODE_DIGITAL else ChannelMode.ANALOG

        # Frequencies (32-bit little-endian, stored as 10 Hz units)
        rx_freq_int = struct.unpack('<I', ch_data[0x06:0x0A])[0]
        tx_freq_int = struct.unpack('<I', ch_data[0x0A:0x0E])[0]
        rx_freq = 0 if rx_freq_int == 0xFFFFFFFF else rx_freq_int
        tx_freq = 0 if tx_freq_int == 0xFFFFFFFF else tx_freq_int

        # Power and scan
        power = PowerLevel.HIGH if ch_data[0x10] == POWER_HIGH else PowerLevel.LOW
        scan = ScanMode.ADD if ch_data[0x13] == SCAN_ADD else ScanMode.REMOVE

        # Channel name (16 bytes, GBK encoding)
        name_bytes = ch_data[0x20:0x30]
        name_bytes = bytes([b for b in name_bytes if b != EMPTY_BYTE])
        try:
            name = name_bytes.decode('gbk', errors='ignore').strip()
        except Exception:
            name = name_bytes.decode('latin-1', errors='ignore').strip()

        channel = Channel(
            position=index + 1,
            name=name,
            rx_freq=rx_freq,
            tx_freq=tx_freq,
            mode=mode,
            power=power,
            scan=scan,
        )

        if mode == ChannelMode.DIGITAL:
            id_select_byte = ch_data[0x00]
            channel.use_radio_id = (id_select_byte == 0x00)
            channel.dmr_time_slot = ch_data[0x03]
            channel.dmr_color_code = ch_data[0x04]
            channel.dmr_mode = ch_data[0x05]
            channel.dmr_monitor = ch_data[0x0E]
            channel.dmr_busy_lock = ch_data[0x11]
            channel.tot = ch_data[0x14]
            channel.alarm = ch_data[0x15]
            channel._parsed_group_list_index = struct.unpack('<H', ch_data[0x16:0x18])[0]
            contact_slot = struct.unpack('<H', ch_data[0x18:0x1A])[0]
            if contact_slot == 0xFFFF:
                channel._parsed_contact_index = 0
            else:
                channel._parsed_contact_index = contact_slot + 1
            channel._parsed_encrypt_index = struct.unpack('<H', ch_data[0x1A:0x1C])[0]
            dmr_id_bytes = ch_data[0x1C:0x20]
            channel.dmr_id = CodeplugParser._parse_bcd(dmr_id_bytes)
        else:
            byte_0x04 = ch_data[0x04]
            modulation_bits = (byte_0x04 >> 4) & 0x03
            if modulation_bits == 0x00:
                channel.analog_modulation = AnalogModulation.FM
            elif modulation_bits == 0x01:
                channel.analog_modulation = AnalogModulation.AM
            elif modulation_bits == 0x02:
                channel.analog_modulation = AnalogModulation.SSB
            else:
                channel.analog_modulation = AnalogModulation.FM
            channel.bandwidth = (byte_0x04 >> 6) & 0x01
            channel.ctdcs_select = (byte_0x04 >> 1) & 0x07
            channel.rx_ctcss = decode_subaudio_bytes(ch_data[0x05:0x07])
            channel.tx_ctcss = decode_subaudio_bytes(ch_data[0x0F:0x11])
            channel.ana_busy_lock = ch_data[0x11]
            byte_0x12 = ch_data[0x12]
            channel.tot_analog = byte_0x12 & 0x1F
            byte_0x13 = ch_data[0x13]
            channel.tail_tone = (byte_0x13 >> 4) & 0x0F
            channel.scramble = byte_0x13 & 0x0F
            channel.mute_code = struct.unpack('<I', ch_data[0x14:0x18])[0]

        return channel

    except Exception as e:
        print(f"Warning: Error parsing legacy channel {index}: {e}")
        return None


# Legacy group list format parameters (exposed for the parser)
LEGACY_GROUP_LIST_SIZE = GROUP_LIST_SIZE_LEGACY
LEGACY_MAX_GROUP_LISTS = MAX_GROUP_LISTS_LEGACY
LEGACY_MAX_GROUP_LIST_IDS = MAX_GROUP_LIST_IDS_LEGACY
