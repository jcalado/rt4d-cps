"""RT-4D Message Parser and Serializer

Handles parsing and serializing DMR SMS messages from/to SPI flash format.
Messages are stored in a 256-byte entry format in different SPI regions.
"""

from datetime import datetime
from typing import List, Optional

from .models import Message, MessageType, CallType
from .constants import (
    MESSAGE_ENTRY_SIZE, MESSAGE_TEXT_OFFSET, MESSAGE_TEXT_MAX_LENGTH,
    MAX_PRESET_MESSAGES, MAX_DRAFT_MESSAGES, MAX_INBOX_MESSAGES, MAX_OUTBOX_MESSAGES
)


class MessageParser:
    """Parser for DMR SMS messages from SPI flash"""

    @staticmethod
    def parse_message(data: bytes, msg_type: MessageType, index: int = 0) -> Optional[Message]:
        """Parse a single 256-byte message entry.

        Message Entry Structure (256 bytes):
        | Offset | Size | Field        | Notes                                    |
        |--------|------|--------------|------------------------------------------|
        | 0      | 1    | Message Type | 0=Preset, 1=Draft, 2=Inbox, 3=Outbox     |
        | 1      | 1    | Call Type    | 0=Private, 1=Group, 2=All (Inbox/Outbox) |
        | 2-5    | 4    | Contact ID   | 32-bit LE (Inbox/Outbox only)            |
        | 6-11   | 6    | Timestamp    | YY-MM-DD HH:MM:SS (Inbox/Outbox only)    |
        | 12-55  | 44   | Reserved     | 0xFF filled                              |
        | 56-255 | 200  | Message Text | GBK encoding                             |
        """
        if len(data) < MESSAGE_ENTRY_SIZE:
            return None

        # Check message type byte - must match expected type for the region
        # Original CPS checks: bufSMSData[num3] == 0 for presets, == 1 for drafts, etc.
        stored_type = data[0]
        if stored_type != msg_type.value:
            # Message type doesn't match expected - entry is empty or invalid
            return None

        # Parse call type
        call_type = CallType.PRIVATE
        call_type_byte = data[1]
        if call_type_byte < 3:
            try:
                call_type = CallType(call_type_byte)
            except ValueError:
                pass

        # Parse contact ID (32-bit little-endian)
        contact_id = int.from_bytes(data[2:6], 'little')
        if contact_id == 0xFFFFFFFF:
            contact_id = 0

        # Parse timestamp (6 bytes: YY, MM, DD, HH, MM, SS)
        timestamp = None
        ts_data = data[6:12]
        if not all(b == 0xFF for b in ts_data) and not all(b == 0x00 for b in ts_data):
            try:
                year = 2000 + ts_data[0]
                month = ts_data[1] if 1 <= ts_data[1] <= 12 else 1
                day = ts_data[2] if 1 <= ts_data[2] <= 31 else 1
                hour = ts_data[3] if ts_data[3] <= 23 else 0
                minute = ts_data[4] if ts_data[4] <= 59 else 0
                second = ts_data[5] if ts_data[5] <= 59 else 0
                timestamp = datetime(year, month, day, hour, minute, second)
            except (ValueError, OverflowError):
                timestamp = None

        # Parse message text (GBK encoding, like original CPS)
        text_data = data[MESSAGE_TEXT_OFFSET:MESSAGE_TEXT_OFFSET + MESSAGE_TEXT_MAX_LENGTH]

        # Decode GBK and strip null characters (like original CPS: text.Replace("\0", ""))
        text = ""
        try:
            text = text_data.decode('gbk')
            text = text.replace('\x00', '').replace('\xff', '').strip()
        except UnicodeDecodeError:
            # Fallback to latin-1
            try:
                text = text_data.decode('latin-1')
                text = text.replace('\x00', '').replace('\xff', '').strip()
            except UnicodeDecodeError:
                text = ""

        # Return message even if text is empty (entry exists with valid type)
        return Message(
            index=index,
            message_type=msg_type,
            call_type=call_type,
            contact_id=contact_id,
            timestamp=timestamp,
            text=text
        )

    @staticmethod
    def parse_region(data: bytes, msg_type: MessageType, count: int) -> List[Message]:
        """Parse a full message region.

        Args:
            data: Raw bytes from SPI flash region
            msg_type: Message type for this region
            count: Maximum number of messages in region

        Returns:
            List of parsed Message objects (non-empty only)
        """
        messages = []
        for i in range(count):
            offset = i * MESSAGE_ENTRY_SIZE
            if offset + MESSAGE_ENTRY_SIZE > len(data):
                break

            entry_data = data[offset:offset + MESSAGE_ENTRY_SIZE]
            message = MessageParser.parse_message(entry_data, msg_type, index=i)
            if message:
                messages.append(message)

        return messages


class MessageSerializer:
    """Serializer for DMR SMS messages to SPI flash format"""

    @staticmethod
    def serialize_message(message: Message) -> bytes:
        """Serialize a message to 256-byte entry format.

        Args:
            message: Message object to serialize

        Returns:
            256-byte entry for SPI flash
        """
        data = bytearray(MESSAGE_ENTRY_SIZE)

        # Fill with 0xFF
        for i in range(MESSAGE_ENTRY_SIZE):
            data[i] = 0xFF

        # Message type
        data[0] = message.message_type.value

        # Call type
        data[1] = message.call_type.value

        # Contact ID (32-bit little-endian)
        if message.contact_id > 0:
            data[2:6] = message.contact_id.to_bytes(4, 'little')

        # Timestamp (6 bytes: YY, MM, DD, HH, MM, SS)
        if message.timestamp:
            data[6] = message.timestamp.year - 2000
            data[7] = message.timestamp.month
            data[8] = message.timestamp.day
            data[9] = message.timestamp.hour
            data[10] = message.timestamp.minute
            data[11] = message.timestamp.second

        # Reserved bytes 12-55 stay as 0xFF

        # Message text (GBK encoded, like original CPS)
        if message.text:
            try:
                text_bytes = message.text.encode('gbk')
            except UnicodeEncodeError:
                # Fallback to latin-1
                try:
                    text_bytes = message.text.encode('latin-1')
                except UnicodeEncodeError:
                    text_bytes = b''

            # Truncate to max length
            text_bytes = text_bytes[:MESSAGE_TEXT_MAX_LENGTH]

            # Copy to data
            data[MESSAGE_TEXT_OFFSET:MESSAGE_TEXT_OFFSET + len(text_bytes)] = text_bytes

        return bytes(data)

    @staticmethod
    def serialize_empty_entry() -> bytes:
        """Create an empty 256-byte entry (all 0xFF)."""
        return bytes([0xFF] * MESSAGE_ENTRY_SIZE)

    @staticmethod
    def serialize_region(messages: List[Message], count: int) -> bytes:
        """Serialize messages to full region format.

        Args:
            messages: List of Message objects to serialize
            count: Total slot count for the region

        Returns:
            Bytes for entire region (count * 256 bytes)
        """
        data = bytearray(count * MESSAGE_ENTRY_SIZE)

        # Fill with 0xFF
        for i in range(len(data)):
            data[i] = 0xFF

        # Serialize each message at its index position
        for message in messages:
            if 0 <= message.index < count:
                offset = message.index * MESSAGE_ENTRY_SIZE
                entry = MessageSerializer.serialize_message(message)
                data[offset:offset + MESSAGE_ENTRY_SIZE] = entry

        return bytes(data)

    @staticmethod
    def get_max_count(msg_type: MessageType) -> int:
        """Get maximum message count for a message type."""
        if msg_type == MessageType.PRESET:
            return MAX_PRESET_MESSAGES
        elif msg_type == MessageType.DRAFT:
            return MAX_DRAFT_MESSAGES
        elif msg_type == MessageType.INBOX:
            return MAX_INBOX_MESSAGES
        elif msg_type == MessageType.OUTBOX:
            return MAX_OUTBOX_MESSAGES
        return 16
