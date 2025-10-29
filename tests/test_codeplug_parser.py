import contextlib
import io
from pathlib import Path

import pytest

from rt4d_codeplug import ChannelMode, CodeplugParser, CodeplugSerializer


@pytest.fixture(scope="module")
def codeplug():
    fixture_path = Path(__file__).resolve().parent.parent / "tests.4rdmf"
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
    assert hotspot.contact_index == 2
    assert codeplug.get_contact(hotspot.contact_index).name == "PT"

    assert "CQ0URVM" in analog
    analog_ch = analog["CQ0URVM"]
    assert analog_ch.mode is ChannelMode.ANALOG
    assert analog_ch.rx_freq == pytest.approx(439.325)
    assert analog_ch.tx_ctcss == "74.4"


def test_parser_contact_slots_are_one_based(codeplug):
    digital = [ch for ch in codeplug.channels if ch.is_digital()]
    assert digital  # sanity check
    for ch in digital:
        if ch.contact_index:
            contact = codeplug.get_contact(ch.contact_index)
            assert contact is not None
            assert contact.index == ch.contact_index


def test_parser_bcd_guard_rails():
    assert CodeplugParser._parse_bcd(b"\xff" * 4) == 0
    assert CodeplugParser._parse_bcd(bytes.fromhex("01234567")) == 67452301


def snapshot_channels(channels):
    snap = []
    for ch in sorted(channels, key=lambda c: c.index):
        snap.append(
            (
                ch.index,
                ch.name,
                ch.mode,
                ch.rx_freq,
                ch.tx_freq,
                ch.contact_index,
                ch.group_list_index,
                ch.dmr_color_code,
                ch.dmr_time_slot,
                ch.tx_ctcss,
                ch.rx_ctcss,
            )
        )
    return snap


def snapshot_contacts(contacts):
    return sorted((c.index, c.name, c.contact_type, c.dmr_id) for c in contacts)


def snapshot_zones(zones):
    return sorted((z.index, z.name, tuple(z.channels)) for z in zones)


def test_serializer_round_trip_preserves_key_fields(codeplug):
    original_channels = snapshot_channels(codeplug.channels)
    original_contacts = snapshot_contacts(codeplug.contacts)
    original_zones = snapshot_zones(codeplug.zones)

    serialized = CodeplugSerializer.serialize(codeplug)
    parser = CodeplugParser(serialized)
    with contextlib.redirect_stdout(io.StringIO()):
        reparsed = parser.parse()

    assert snapshot_channels(reparsed.channels) == original_channels
    assert snapshot_contacts(reparsed.contacts) == original_contacts
    assert snapshot_zones(reparsed.zones) == original_zones
