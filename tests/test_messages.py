"""Tests for message parser and serializer"""

import pytest
from datetime import datetime

from rt4d_codeplug.models import Message, MessageType, CallType
from rt4d_codeplug.messages import MessageParser, MessageSerializer
from rt4d_codeplug.constants import MESSAGE_ENTRY_SIZE, MESSAGE_TEXT_OFFSET


class TestMessageParser:
    """Tests for MessageParser"""

    def test_parse_empty_entry(self):
        """Test parsing an empty entry (all 0xFF)"""
        data = bytes([0xFF] * MESSAGE_ENTRY_SIZE)
        result = MessageParser.parse_message(data, MessageType.PRESET)
        assert result is None

    def test_parse_preset_message(self):
        """Test parsing a preset message with text only"""
        data = bytearray([0xFF] * MESSAGE_ENTRY_SIZE)
        data[0] = MessageType.PRESET.value
        data[1] = CallType.PRIVATE.value

        # Add text at offset 56
        text = "Hello World"
        text_bytes = text.encode('gbk')
        data[MESSAGE_TEXT_OFFSET:MESSAGE_TEXT_OFFSET + len(text_bytes)] = text_bytes

        result = MessageParser.parse_message(bytes(data), MessageType.PRESET, index=5)

        assert result is not None
        assert result.message_type == MessageType.PRESET
        assert result.text == "Hello World"
        assert result.index == 5

    def test_parse_inbox_message_with_timestamp(self):
        """Test parsing an inbox message with timestamp and contact"""
        data = bytearray([0xFF] * MESSAGE_ENTRY_SIZE)
        data[0] = MessageType.INBOX.value
        data[1] = CallType.GROUP.value

        # Contact ID: 12345678 (little-endian)
        contact_id = 12345678
        data[2:6] = contact_id.to_bytes(4, 'little')

        # Timestamp: 2024-06-15 14:30:45
        data[6] = 24   # Year - 2000
        data[7] = 6    # Month
        data[8] = 15   # Day
        data[9] = 14   # Hour
        data[10] = 30  # Minute
        data[11] = 45  # Second

        # Add text
        text = "Test message"
        text_bytes = text.encode('gbk')
        data[MESSAGE_TEXT_OFFSET:MESSAGE_TEXT_OFFSET + len(text_bytes)] = text_bytes

        result = MessageParser.parse_message(bytes(data), MessageType.INBOX)

        assert result is not None
        assert result.message_type == MessageType.INBOX
        assert result.call_type == CallType.GROUP
        assert result.contact_id == 12345678
        assert result.timestamp == datetime(2024, 6, 15, 14, 30, 45)
        assert result.text == "Test message"

    def test_parse_region(self):
        """Test parsing a region with multiple messages"""
        # Create region data with 3 messages
        region_data = bytearray([0xFF] * MESSAGE_ENTRY_SIZE * 5)

        # Message at index 0
        region_data[0] = MessageType.PRESET.value
        text0 = "First"
        region_data[MESSAGE_TEXT_OFFSET:MESSAGE_TEXT_OFFSET + len(text0)] = text0.encode('gbk')

        # Message at index 2 (leave index 1 empty)
        offset2 = 2 * MESSAGE_ENTRY_SIZE
        region_data[offset2] = MessageType.PRESET.value
        text2 = "Third"
        region_data[offset2 + MESSAGE_TEXT_OFFSET:offset2 + MESSAGE_TEXT_OFFSET + len(text2)] = text2.encode('gbk')

        messages = MessageParser.parse_region(bytes(region_data), MessageType.PRESET, 5)

        assert len(messages) == 2
        assert messages[0].index == 0
        assert messages[0].text == "First"
        assert messages[1].index == 2
        assert messages[1].text == "Third"


class TestMessageSerializer:
    """Tests for MessageSerializer"""

    def test_serialize_empty_entry(self):
        """Test creating an empty entry"""
        data = MessageSerializer.serialize_empty_entry()
        assert len(data) == MESSAGE_ENTRY_SIZE
        assert all(b == 0xFF for b in data)

    def test_serialize_preset_message(self):
        """Test serializing a preset message"""
        msg = Message(
            index=3,
            message_type=MessageType.PRESET,
            text="Test preset"
        )

        data = MessageSerializer.serialize_message(msg)

        assert len(data) == MESSAGE_ENTRY_SIZE
        assert data[0] == MessageType.PRESET.value
        assert data[1] == CallType.PRIVATE.value

        # Check text
        text_bytes = "Test preset".encode('gbk')
        assert data[MESSAGE_TEXT_OFFSET:MESSAGE_TEXT_OFFSET + len(text_bytes)] == text_bytes

    def test_serialize_message_with_timestamp(self):
        """Test serializing a message with timestamp and contact"""
        msg = Message(
            index=0,
            message_type=MessageType.OUTBOX,
            call_type=CallType.GROUP,
            contact_id=9876543,
            timestamp=datetime(2025, 1, 20, 10, 15, 30),
            text="Outbox message"
        )

        data = MessageSerializer.serialize_message(msg)

        assert data[0] == MessageType.OUTBOX.value
        assert data[1] == CallType.GROUP.value

        # Check contact ID
        assert int.from_bytes(data[2:6], 'little') == 9876543

        # Check timestamp
        assert data[6] == 25   # Year - 2000
        assert data[7] == 1    # Month
        assert data[8] == 20   # Day
        assert data[9] == 10   # Hour
        assert data[10] == 15  # Minute
        assert data[11] == 30  # Second

    def test_serialize_region(self):
        """Test serializing a region"""
        messages = [
            Message(index=0, message_type=MessageType.PRESET, text="First"),
            Message(index=2, message_type=MessageType.PRESET, text="Third"),
        ]

        data = MessageSerializer.serialize_region(messages, 5)

        assert len(data) == 5 * MESSAGE_ENTRY_SIZE

        # Check first message
        assert data[0] == MessageType.PRESET.value
        text0 = "First".encode('gbk')
        assert data[MESSAGE_TEXT_OFFSET:MESSAGE_TEXT_OFFSET + len(text0)] == text0

        # Check second slot is empty
        offset1 = MESSAGE_ENTRY_SIZE
        assert all(b == 0xFF for b in data[offset1:offset1 + MESSAGE_TEXT_OFFSET])

        # Check third message
        offset2 = 2 * MESSAGE_ENTRY_SIZE
        assert data[offset2] == MessageType.PRESET.value
        text2 = "Third".encode('gbk')
        assert data[offset2 + MESSAGE_TEXT_OFFSET:offset2 + MESSAGE_TEXT_OFFSET + len(text2)] == text2


class TestMessageRoundtrip:
    """Tests for parse/serialize roundtrip"""

    def test_preset_roundtrip(self):
        """Test parsing and re-serializing a preset message"""
        original = Message(
            index=5,
            message_type=MessageType.PRESET,
            text="Roundtrip test message!"
        )

        # Serialize
        data = MessageSerializer.serialize_message(original)

        # Parse
        parsed = MessageParser.parse_message(data, MessageType.PRESET, index=5)

        assert parsed is not None
        assert parsed.message_type == original.message_type
        assert parsed.text == original.text
        assert parsed.index == original.index

    def test_full_message_roundtrip(self):
        """Test roundtrip with all fields"""
        original = Message(
            index=10,
            message_type=MessageType.INBOX,
            call_type=CallType.PRIVATE,
            contact_id=1234567,
            timestamp=datetime(2024, 12, 25, 9, 0, 0),
            text="Christmas greeting!"
        )

        data = MessageSerializer.serialize_message(original)
        parsed = MessageParser.parse_message(data, MessageType.INBOX, index=10)

        assert parsed is not None
        assert parsed.message_type == original.message_type
        assert parsed.call_type == original.call_type
        assert parsed.contact_id == original.contact_id
        assert parsed.timestamp == original.timestamp
        assert parsed.text == original.text

    def test_region_roundtrip(self):
        """Test region roundtrip"""
        original_messages = [
            Message(index=0, message_type=MessageType.DRAFT, text="Draft 1"),
            Message(index=3, message_type=MessageType.DRAFT, text="Draft 4"),
            Message(index=7, message_type=MessageType.DRAFT, text="Draft 8"),
        ]

        data = MessageSerializer.serialize_region(original_messages, 10)
        parsed = MessageParser.parse_region(data, MessageType.DRAFT, 10)

        assert len(parsed) == 3
        for orig, parse in zip(original_messages, parsed):
            assert parse.index == orig.index
            assert parse.text == orig.text

    def test_gbk_text_roundtrip(self):
        """Test roundtrip with GBK-encoded Chinese text"""
        original = Message(
            index=0,
            message_type=MessageType.PRESET,
            text="Hello World"  # ASCII text
        )

        data = MessageSerializer.serialize_message(original)
        parsed = MessageParser.parse_message(data, MessageType.PRESET)

        assert parsed is not None
        assert parsed.text == original.text


class TestMessageModel:
    """Tests for Message model"""

    def test_is_empty(self):
        """Test is_empty method"""
        empty_msg = Message()
        assert empty_msg.is_empty()

        empty_text_msg = Message(text="   ")
        assert empty_text_msg.is_empty()

        valid_msg = Message(text="Hello")
        assert not valid_msg.is_empty()

    def test_text_truncation(self):
        """Test that text is truncated to max length"""
        long_text = "A" * 300
        msg = Message(text=long_text)
        assert len(msg.text) == 200
