"""Tests for legacy (pre-beta41) codeplug channel parser"""

import struct

import pytest

from rt4d_codeplug.legacy import parse_channel_legacy
from rt4d_codeplug.constants import (
    OFFSET_CHANNELS, CHANNEL_SIZE, CHANNEL_MODE_DIGITAL, CHANNEL_MODE_ANALOG,
    POWER_HIGH, POWER_LOW, SCAN_ADD, SCAN_REMOVE, TOTAL_SIZE_LEGACY, EMPTY_BYTE,
)
from rt4d_codeplug.models import ChannelMode, PowerLevel, ScanMode, AnalogModulation
from rt4d_codeplug.serializer import CodeplugSerializer


def _make_codeplug_data(channel_index: int, ch_data: bytes) -> bytes:
    """Build a minimal legacy-size codeplug buffer with one channel populated."""
    data = bytearray(b'\xff' * TOTAL_SIZE_LEGACY)
    offset = OFFSET_CHANNELS + (channel_index * CHANNEL_SIZE)
    data[offset:offset + CHANNEL_SIZE] = ch_data
    return bytes(data)


def _make_digital_channel(
    *,
    name: str = "TEST",
    rx_freq: int = 43912500,
    tx_freq: int = 43412500,
    power_high: bool = True,
    scan_add: bool = True,
    time_slot: int = 1,
    color_code: int = 3,
    dmr_mode: int = 0,
    dmr_monitor: int = 0,
    dmr_busy_lock: int = 0,
    tot: int = 0,
    alarm: int = 0,
    use_radio_id: bool = True,
    contact_slot: int = 0xFFFF,
    group_list_index: int = 0xFFFF,
    encrypt_index: int = 0,
    dmr_id: int = 0,
) -> bytes:
    """Build a 48-byte legacy digital channel."""
    ch = bytearray(b'\xff' * CHANNEL_SIZE)

    # 0x00: ID select (0=radio ID, 1=channel ID)
    ch[0x00] = 0x00 if use_radio_id else 0x01
    # 0x02: mode (0=digital)
    ch[0x02] = CHANNEL_MODE_DIGITAL
    # 0x03: time slot
    ch[0x03] = time_slot
    # 0x04: color code
    ch[0x04] = color_code
    # 0x05: DMR mode
    ch[0x05] = dmr_mode
    # 0x06-0x09: RX freq
    struct.pack_into('<I', ch, 0x06, rx_freq)
    # 0x0A-0x0D: TX freq
    struct.pack_into('<I', ch, 0x0A, tx_freq)
    # 0x0E: DMR monitor
    ch[0x0E] = dmr_monitor
    # 0x10: power
    ch[0x10] = POWER_HIGH if power_high else POWER_LOW
    # 0x11: DMR busy lock
    ch[0x11] = dmr_busy_lock
    # 0x13: scan
    ch[0x13] = SCAN_ADD if scan_add else SCAN_REMOVE
    # 0x14: TOT
    ch[0x14] = tot
    # 0x15: alarm
    ch[0x15] = alarm
    # 0x16-0x17: group list index
    struct.pack_into('<H', ch, 0x16, group_list_index)
    # 0x18-0x19: contact slot
    struct.pack_into('<H', ch, 0x18, contact_slot)
    # 0x1A-0x1B: encrypt index
    struct.pack_into('<H', ch, 0x1A, encrypt_index)
    # 0x1C-0x1F: DMR ID (BCD)
    ch[0x1C:0x20] = CodeplugSerializer._to_bcd(dmr_id)
    # 0x20-0x2F: name (GBK, padded with 0xFF)
    name_bytes = name.encode('gbk')[:16]
    ch[0x20:0x20 + len(name_bytes)] = name_bytes

    return bytes(ch)


def _make_analog_channel(
    *,
    name: str = "ANALOG",
    rx_freq: int = 14625000,
    tx_freq: int = 14625000,
    power_high: bool = False,
    scan_add: bool = False,
    modulation: int = 0,  # 0=FM, 1=AM, 2=SSB
    bandwidth: int = 0,   # 0=wide, 1=narrow
    ctdcs_select: int = 0,
    rx_tone: int = 0,
    tx_tone: int = 0,
    ana_busy_lock: int = 0,
    tot_analog: int = 10,
    tail_tone: int = 2,
    scramble: int = 0,
    mute_code: int = 0,
) -> bytes:
    """Build a 48-byte legacy analog channel."""
    ch = bytearray(b'\xff' * CHANNEL_SIZE)

    # 0x02: mode (1=analog)
    ch[0x02] = CHANNEL_MODE_ANALOG
    # 0x04: modulation(bits 4-5) | bandwidth(bit 6) | ctdcs_select(bits 1-3)
    ch[0x04] = ((ctdcs_select & 0x07) << 1) | ((modulation & 0x03) << 4) | ((bandwidth & 0x01) << 6)
    # 0x05-0x06: RX tone (16-bit LE)
    struct.pack_into('<H', ch, 0x05, rx_tone)
    # 0x06-0x09: RX freq
    struct.pack_into('<I', ch, 0x06, rx_freq)
    # 0x0A-0x0D: TX freq
    struct.pack_into('<I', ch, 0x0A, tx_freq)
    # 0x0F-0x10: TX tone (16-bit LE)
    struct.pack_into('<H', ch, 0x0F, tx_tone)
    # 0x10: power
    ch[0x10] = POWER_HIGH if power_high else POWER_LOW
    # 0x11: analog busy lock
    ch[0x11] = ana_busy_lock
    # 0x12: TOT analog (lower 5 bits)
    ch[0x12] = tot_analog & 0x1F
    # 0x13: tail_tone(upper 4 bits) | scramble(lower 4 bits)
    ch[0x13] = ((tail_tone & 0x0F) << 4) | (scramble & 0x0F)
    # 0x14-0x17: mute code
    struct.pack_into('<I', ch, 0x14, mute_code)
    # 0x20-0x2F: name
    name_bytes = name.encode('gbk')[:16]
    ch[0x20:0x20 + len(name_bytes)] = name_bytes

    return bytes(ch)


# ── Empty / invalid slots ──────────────────────────────────────────

class TestLegacyEmpty:
    def test_empty_slot_returns_none(self):
        """All-0xFF slot is detected as empty"""
        data = _make_codeplug_data(0, b'\xff' * CHANNEL_SIZE)
        assert parse_channel_legacy(data, 0) is None

    def test_mode_byte_ge_2_returns_none(self):
        """Byte 0x02 >= 2 means invalid/empty"""
        ch = bytearray(b'\xff' * CHANNEL_SIZE)
        ch[0x02] = 0x02
        data = _make_codeplug_data(0, bytes(ch))
        assert parse_channel_legacy(data, 0) is None


# ── Digital channel parsing ────────────────────────────────────────

class TestLegacyDigital:
    def test_basic_digital_channel(self):
        ch_bytes = _make_digital_channel(
            name="REPEATER",
            rx_freq=43912500,
            tx_freq=43412500,
            time_slot=1,
            color_code=7,
        )
        data = _make_codeplug_data(5, ch_bytes)
        ch = parse_channel_legacy(data, 5)

        assert ch is not None
        assert ch.position == 6  # 0-based index 5 → 1-based position 6
        assert ch.name == "REPEATER"
        assert ch.mode is ChannelMode.DIGITAL
        assert ch.rx_freq == 43912500
        assert ch.tx_freq == 43412500
        assert ch.dmr_time_slot == 1
        assert ch.dmr_color_code == 7

    def test_power_and_scan(self):
        ch_bytes = _make_digital_channel(power_high=False, scan_add=False)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)

        assert ch.power is PowerLevel.LOW
        assert ch.scan is ScanMode.REMOVE

    def test_power_high_and_scan_add(self):
        ch_bytes = _make_digital_channel(power_high=True, scan_add=True)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)

        assert ch.power is PowerLevel.HIGH
        assert ch.scan is ScanMode.ADD

    def test_use_radio_id_true(self):
        ch_bytes = _make_digital_channel(use_radio_id=True)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.use_radio_id is True

    def test_use_channel_id(self):
        ch_bytes = _make_digital_channel(use_radio_id=False)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.use_radio_id is False

    def test_dmr_id_bcd(self):
        ch_bytes = _make_digital_channel(use_radio_id=False, dmr_id=2680001)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.dmr_id == 2680001

    def test_contact_slot_none(self):
        ch_bytes = _make_digital_channel(contact_slot=0xFFFF)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch._parsed_contact_index == 0

    def test_contact_slot_valid(self):
        ch_bytes = _make_digital_channel(contact_slot=42)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch._parsed_contact_index == 43  # slot + 1

    def test_group_list_and_encrypt_indices(self):
        ch_bytes = _make_digital_channel(group_list_index=5, encrypt_index=3)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch._parsed_group_list_index == 5
        assert ch._parsed_encrypt_index == 3

    def test_dmr_fields(self):
        ch_bytes = _make_digital_channel(
            dmr_mode=1, dmr_monitor=1, dmr_busy_lock=1, tot=30, alarm=1,
        )
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.dmr_mode == 1
        assert ch.dmr_monitor == 1
        assert ch.dmr_busy_lock == 1
        assert ch.tot == 30
        assert ch.alarm == 1


# ── Analog channel parsing ─────────────────────────────────────────

class TestLegacyAnalog:
    def test_basic_analog_channel(self):
        ch_bytes = _make_analog_channel(
            name="70CM CALL",
            rx_freq=14625000,
            tx_freq=14625000,
        )
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)

        assert ch is not None
        assert ch.name == "70CM CALL"
        assert ch.mode is ChannelMode.ANALOG
        assert ch.rx_freq == 14625000
        assert ch.tx_freq == 14625000

    def test_modulation_fm(self):
        ch_bytes = _make_analog_channel(modulation=0)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.analog_modulation is AnalogModulation.FM

    def test_modulation_am(self):
        ch_bytes = _make_analog_channel(modulation=1)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.analog_modulation is AnalogModulation.AM

    def test_modulation_ssb(self):
        ch_bytes = _make_analog_channel(modulation=2)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.analog_modulation is AnalogModulation.SSB

    def test_modulation_invalid_defaults_to_fm(self):
        ch_bytes = _make_analog_channel(modulation=3)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.analog_modulation is AnalogModulation.FM

    def test_bandwidth(self):
        ch_bytes = _make_analog_channel(bandwidth=1)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.bandwidth == 1

    def test_ctdcs_select(self):
        ch_bytes = _make_analog_channel(ctdcs_select=5)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.ctdcs_select == 5

    def test_tot_analog_and_tail_tone_and_scramble(self):
        ch_bytes = _make_analog_channel(tot_analog=15, tail_tone=7, scramble=3)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.tot_analog == 15
        assert ch.tail_tone == 7
        assert ch.scramble == 3

    def test_power_low_scan_remove(self):
        ch_bytes = _make_analog_channel(power_high=False, scan_add=False)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.power is PowerLevel.LOW
        assert ch.scan is ScanMode.REMOVE

    def test_mute_code(self):
        ch_bytes = _make_analog_channel(mute_code=0xDEADBEEF)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.mute_code == 0xDEADBEEF

    def test_analog_busy_lock(self):
        ch_bytes = _make_analog_channel(ana_busy_lock=1)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.ana_busy_lock == 1


# ── Edge cases ─────────────────────────────────────────────────────

class TestLegacyEdgeCases:
    def test_channel_at_last_index(self):
        """Channel at index 1023 (last slot)"""
        ch_bytes = _make_digital_channel(name="LAST")
        data = _make_codeplug_data(1023, ch_bytes)
        ch = parse_channel_legacy(data, 1023)
        assert ch is not None
        assert ch.position == 1024
        assert ch.name == "LAST"

    def test_frequency_0xffffffff_becomes_zero(self):
        ch_bytes = _make_digital_channel(rx_freq=0xFFFFFFFF, tx_freq=0xFFFFFFFF)
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.rx_freq == 0
        assert ch.tx_freq == 0

    def test_gbk_channel_name(self):
        """GBK-encoded name parses correctly"""
        ch_bytes = _make_digital_channel(name="CH-01")
        data = _make_codeplug_data(0, ch_bytes)
        ch = parse_channel_legacy(data, 0)
        assert ch.name == "CH-01"
