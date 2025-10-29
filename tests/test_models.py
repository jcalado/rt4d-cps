import pytest

from rt4d_codeplug.models import Channel, GroupList, Zone


def test_channel_validation_truncates_and_validates():
    ch = Channel(index=1, name="A" * 40, rx_freq=145.5, tx_freq=145.5, enabled=True)
    assert len(ch.name) == 16
    assert not ch.is_empty()

    with pytest.raises(ValueError):
        Channel(index=2, rx_freq=1200.0, tx_freq=1200.0, enabled=True)

    empty = Channel(index=3, rx_freq=0.0, tx_freq=0.0, enabled=True)
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

    for idx in range(5, 253):
        zone.add_channel(idx)

    assert len(zone.channels) == 250

    with pytest.raises(ValueError):
        zone.add_channel(253)

    empty_zone = Zone(index=2, name="")
    assert empty_zone.is_empty()
