import contextlib
import io
from pathlib import Path

import pytest

from rt4d_codeplug import ChannelMode, CodeplugParser, CodeplugSerializer
from rt4d_codeplug.models import Codeplug, RadioSettings
from rt4d_codeplug.constants import TOTAL_SIZE


@pytest.fixture(scope="module")
def codeplug():
    fixture_path = Path(__file__).resolve().parent.parent / "tests.4rdmf"
    if not fixture_path.exists():
        fixture_path = Path(__file__).resolve().parent.parent / "codeplug.new.4rdmf"
    parser = CodeplugParser.from_file(str(fixture_path))
    with contextlib.redirect_stdout(io.StringIO()):
        return parser.parse()


def test_parser_recognises_digital_and_analog_channels(codeplug):
    digital = {ch.name: ch for ch in codeplug.channels if ch.is_digital()}
    analog = {ch.name: ch for ch in codeplug.channels if ch.is_analog()}

    hotspot_name = next(name for name in digital if name.startswith("HOTSPOT PT"))
    hotspot = digital[hotspot_name]
    assert hotspot.mode is ChannelMode.DIGITAL
    assert hotspot.dmr_color_code == 1
    # Contact is now referenced by UUID
    assert hotspot.contact_uuid  # has a contact assigned
    contact = codeplug.get_contact(hotspot.contact_uuid)
    assert contact is not None
    assert contact.name == "PT"

    # Find an analog channel for verification
    analog_names = list(analog.keys())
    assert len(analog_names) > 0  # Should have some analog channels
    analog_ch = analog[analog_names[0]]
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
