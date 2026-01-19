import pytest

from rt4d_codeplug.models import Channel, GroupList, Zone


def test_channel_validation_truncates_and_validates():
    # 145.5 MHz = 14550000 in 10 Hz units
    ch = Channel(position=1, name="A" * 40, rx_freq=14550000, tx_freq=14550000)
    assert len(ch.name) == 16
    assert not ch.is_empty()

    # 1200 MHz = 120000000 in 10 Hz units, exceeds 1000 MHz limit
    with pytest.raises(ValueError):
        Channel(position=2, rx_freq=120000000, tx_freq=120000000)

    empty = Channel(position=3, rx_freq=0, tx_freq=0)
    assert empty.is_empty()


def test_group_list_contact_management():
    group = GroupList(index=1, name="Test")
    group.add_contact(7)
    group.add_contact(7)
    assert group.contacts == [7]

    group.contacts = list(range(128))
    group.add_contact(999)
    assert 999 not in group.contacts


def test_zone_channel_limits_and_uniqueness():
    zone = Zone(index=1, name="Zone 1")
    zone.add_channel(3)
    zone.add_channel(3)
    zone.add_channel(4)
    assert zone.channels == [3, 4]

    for idx in range(5, 203):
        zone.add_channel(idx)

    assert len(zone.channels) == 200

    with pytest.raises(ValueError):
        zone.add_channel(203)

    empty_zone = Zone(index=2, name="")
    assert empty_zone.is_empty()
