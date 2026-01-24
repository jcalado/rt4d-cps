import contextlib
import io
from pathlib import Path

import pytest

from rt4d_codeplug import ChannelMode, CodeplugParser, CodeplugSerializer
from rt4d_codeplug.models import Codeplug, RadioSettings
from rt4d_codeplug.constants import TOTAL_SIZE


@pytest.fixture(scope="module")
def codeplug():
    fixture_path = Path(__file__).resolve().parent.parent / "codeplug.41-plus.4rdmf"
    parser = CodeplugParser.from_file(str(fixture_path))
    with contextlib.redirect_stdout(io.StringIO()):
        return parser.parse()


def test_parser_recognises_digital_and_analog_channels(codeplug):
    digital = {ch.name: ch for ch in codeplug.channels if ch.is_digital()}
    analog = {ch.name: ch for ch in codeplug.channels if ch.is_analog()}

    # Verify we have digital channels with proper mode
    assert len(digital) > 0, "Should have digital channels"
    # Use 'PT' channel which exists in codeplug.41-plus.4rdmf
    pt_channel = digital.get("PT")
    assert pt_channel is not None, "PT digital channel should exist"
    assert pt_channel.mode is ChannelMode.DIGITAL
    assert pt_channel.dmr_color_code >= 0
    # Contact is now referenced by UUID
    assert pt_channel.contact_uuid  # has a contact assigned
    contact = codeplug.get_contact(pt_channel.contact_uuid)
    assert contact is not None
    assert contact.name == "PT"

    # Find an analog channel for verification
    assert len(analog) > 0, "Should have some analog channels"
    # Use '70CM CALL' which exists in codeplug.41-plus.4rdmf
    analog_ch = analog.get("70CM CALL")
    assert analog_ch is not None, "70CM CALL analog channel should exist"
    assert analog_ch.mode is ChannelMode.ANALOG
    assert analog_ch.rx_freq > 0  # Should have a valid frequency


def test_parser_contact_references_resolve_correctly(codeplug):
    """Test that contact UUID references resolve to valid contacts"""
    digital = [ch for ch in codeplug.channels if ch.is_digital()]
    assert digital  # sanity check
    for ch in digital:
        if ch.contact_uuid:
            contact = codeplug.get_contact(ch.contact_uuid)
            assert contact is not None
            # The contact's UUID should match the channel's reference
            assert contact.uuid == ch.contact_uuid


def test_parser_bcd_guard_rails():
    assert CodeplugParser._parse_bcd(b"\xff" * 4) == 0
    assert CodeplugParser._parse_bcd(bytes.fromhex("01234567")) == 67452301


def snapshot_channels(codeplug):
    """Snapshot channel data for comparison.
    Uses resolved contact/group names instead of UUIDs since UUIDs are regenerated on parse.
    """
    snap = []
    for ch in sorted(codeplug.channels, key=lambda c: c.position):
        # Resolve contact name instead of using UUID
        contact_name = ""
        if ch.contact_uuid:
            contact = codeplug.get_contact(ch.contact_uuid)
            contact_name = contact.name if contact else ""
        # Resolve group list name instead of using UUID
        group_list_name = ""
        if ch.group_list_uuid:
            group_list = codeplug.get_group_list(ch.group_list_uuid)
            group_list_name = group_list.name if group_list else ""

        snap.append(
            (
                ch.name,  # Don't include index - it may change based on list position
                ch.mode,
                ch.rx_freq,
                ch.tx_freq,
                contact_name,
                group_list_name,
                ch.dmr_color_code,
                ch.dmr_time_slot,
                ch.tx_ctcss,
                ch.rx_ctcss,
            )
        )
    return snap


def snapshot_contacts(contacts):
    """Snapshot contact data - don't include index as it's calculated on save"""
    return sorted((c.name, c.contact_type, c.dmr_id) for c in contacts)


def snapshot_zones(codeplug):
    """Snapshot zone data - resolve channel UUIDs to names for comparison"""
    result = []
    for z in sorted(codeplug.zones, key=lambda z: z.index):
        channel_names = []
        for ch_uuid in z.channels:
            ch = codeplug.get_channel(ch_uuid)
            if ch:
                channel_names.append(ch.name)
        result.append((z.name, tuple(channel_names)))
    return sorted(result)


def test_serializer_round_trip_preserves_key_fields(codeplug):
    original_channels = snapshot_channels(codeplug)
    original_contacts = snapshot_contacts(codeplug.contacts)
    original_zones = snapshot_zones(codeplug)

    serialized = CodeplugSerializer.serialize(codeplug)
    parser = CodeplugParser(serialized)
    with contextlib.redirect_stdout(io.StringIO()):
        reparsed = parser.parse()

    assert snapshot_channels(reparsed) == original_channels
    assert snapshot_contacts(reparsed.contacts) == original_contacts
    assert snapshot_zones(reparsed) == original_zones


def test_beta41_settings_round_trip_preserves_magic_bytes():
    codeplug = Codeplug(settings=RadioSettings(beta41=True))

    serialized = CodeplugSerializer.serialize(codeplug)

    assert len(serialized) == TOTAL_SIZE

    parser = CodeplugParser(serialized)
    with contextlib.redirect_stdout(io.StringIO()):
        reparsed = parser.parse()

    assert reparsed.settings.beta41 is True


def test_parser_radio_settings_identity(codeplug):
    """Test that radio identity settings are parsed correctly"""
    settings = codeplug.settings

    # Beta41+ codeplug should have beta41 flag set
    assert settings.beta41 is True

    # Radio identity - these are from codeplug.41-plus.4rdmf
    assert settings.radio_name == "CS7BLE"
    assert settings.radio_id == 2680000


def test_parser_radio_settings_audio(codeplug):
    """Test that audio settings are parsed correctly"""
    settings = codeplug.settings

    # Audio settings should be within valid ranges
    assert 0 <= settings.squelch_level <= 9
    assert 0 <= settings.digital_squelch <= 9
    assert 1 <= settings.tx_mic_gain <= 15
    assert 1 <= settings.rx_speaker_volume <= 100
    assert 1 <= settings.call_mic_gain <= 15
    assert 1 <= settings.call_speaker_volume <= 15


def test_parser_radio_settings_display(codeplug):
    """Test that display settings are parsed correctly"""
    settings = codeplug.settings

    # Display settings should be within valid ranges
    assert 0 <= settings.backlight_brightness <= 4
    assert 0 <= settings.lcd_contrast <= 15
    assert settings.display_mode_a in (0, 1, 2)  # channel, freq, name
    assert settings.display_mode_b in (0, 1, 2)


def test_parser_radio_settings_vfo_offsets(codeplug):
    """Test that VFO frequency offsets are parsed correctly"""
    settings = codeplug.settings

    # VFO offsets are stored in Hz, typical values are -7.6MHz or -600kHz for repeaters
    # Verify they're reasonable (within +/- 100 MHz)
    assert -100_000_000 <= settings.vfo_a_offset <= 100_000_000
    assert -100_000_000 <= settings.vfo_b_offset <= 100_000_000


def snapshot_settings(settings):
    """Snapshot radio settings for comparison"""
    return {
        # Identity
        'radio_name': settings.radio_name,
        'radio_id': settings.radio_id,
        'beta41': settings.beta41,
        # Audio
        'squelch_level': settings.squelch_level,
        'digital_squelch': settings.digital_squelch,
        'tx_mic_gain': settings.tx_mic_gain,
        'rx_speaker_volume': settings.rx_speaker_volume,
        'call_mic_gain': settings.call_mic_gain,
        'call_speaker_volume': settings.call_speaker_volume,
        'tone_frequency': settings.tone_frequency,
        # Display
        'backlight_brightness': settings.backlight_brightness,
        'lcd_contrast': settings.lcd_contrast,
        'display_mode_a': settings.display_mode_a,
        'display_mode_b': settings.display_mode_b,
        'led_on_off': settings.led_on_off,
        'led_timer': settings.led_timer,
        # Operation
        'dual_watch': settings.dual_watch,
        'main_band': settings.main_band,
        'main_ptt': settings.main_ptt,
        'zone_a': settings.zone_a,
        'zone_b': settings.zone_b,
        'channel_a': settings.channel_a,
        'channel_b': settings.channel_b,
        # VFO
        'vfo_a_offset': settings.vfo_a_offset,
        'vfo_b_offset': settings.vfo_b_offset,
        'vfo_step': settings.vfo_step,
        # Scan
        'scan_lower': settings.scan_lower,
        'scan_upper': settings.scan_upper,
        'scan_mode': settings.scan_mode,
        'scan_dwell': settings.scan_dwell,
        # Function keys
        'key_fs1_short': settings.key_fs1_short,
        'key_fs1_long': settings.key_fs1_long,
        'key_fs2_short': settings.key_fs2_short,
        'key_fs2_long': settings.key_fs2_long,
        # DTMF
        'dtmf_codes': settings.dtmf_codes,
        'dtmf_send_delay': settings.dtmf_send_delay,
        'dtmf_send_duration': settings.dtmf_send_duration,
        # Beta41+ specific
        'tx_alias': settings.tx_alias,
        'dmr_gid_name': settings.dmr_gid_name,
        'callsign_lookup': settings.callsign_lookup,
    }


def test_serializer_round_trip_preserves_radio_settings(codeplug):
    """Test that radio settings survive serialization round-trip"""
    original_settings = snapshot_settings(codeplug.settings)

    serialized = CodeplugSerializer.serialize(codeplug)
    parser = CodeplugParser(serialized)
    with contextlib.redirect_stdout(io.StringIO()):
        reparsed = parser.parse()

    reparsed_settings = snapshot_settings(reparsed.settings)

    # Compare each setting individually for better error messages
    for key in original_settings:
        assert reparsed_settings[key] == original_settings[key], \
            f"Setting '{key}' mismatch: {reparsed_settings[key]} != {original_settings[key]}"
