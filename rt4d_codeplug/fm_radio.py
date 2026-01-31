"""RT-4D FM Radio Parser and Serializer

Handles parsing and serializing FM radio preset data from/to codeplug format.

FM Data Structure (1024 bytes total):
| Offset | Size | Field        | Description                           |
|--------|------|--------------|---------------------------------------|
| 0      | 1    | FM Mode      | 0=Frequency Mode, 1=Channel Mode      |
| 1      | 1    | FM Standby   | Standby setting                       |
| 2      | 1    | FM Area      | Selected area index (0-15)            |
| 3      | 1    | FM Channel   | Selected channel index (0-15)         |
| 4      | 1    | FM Scan Mode | 0=Carrier Stop, 1=Scan All            |
| 5-772  | 768  | Preset Data  | 16 presets x 48 bytes each            |

Individual Preset Structure (48 bytes):
| Offset | Size | Field       | Description                          |
|--------|------|-------------|--------------------------------------|
| 0-15   | 16   | Zone Name   | GBK encoded, 0xFF padded             |
| 16-47  | 32   | Frequencies | 16 frequencies x 2 bytes each (u16LE)|

Frequency Encoding:
- 2 bytes per frequency, little-endian uint16
- Value = Frequency (MHz) x 10
- Example: 107.5 MHz stored as 1075 (0x433)
- Empty frequency: 0xFFFF
"""

from typing import List

from .models import FMPreset, FMSettings


# Constants
FM_DATA_SIZE = 1024
FM_HEADER_SIZE = 5
FM_PRESET_SIZE = 48
FM_PRESET_COUNT = 16
FM_NAME_SIZE = 16
FM_FREQ_COUNT = 16
FM_FREQ_SIZE = 2

# Valid FM frequency range (MHz)
FM_FREQ_MIN = 76.0
FM_FREQ_MAX = 108.0


class FMParser:
    """Parser for FM radio settings from codeplug data"""

    @staticmethod
    def parse(data: bytes) -> FMSettings:
        """Parse FM data bytes into FMSettings object.

        Args:
            data: Raw bytes from codeplug (1024 bytes)

        Returns:
            FMSettings object with parsed data
        """
        if len(data) < FM_DATA_SIZE:
            # Pad with 0xFF if too short
            data = data + bytes([0xFF] * (FM_DATA_SIZE - len(data)))

        settings = FMSettings()

        # Parse header (bytes 0-4)
        settings.mode = data[0] if data[0] != 0xFF else 0
        settings.standby = data[1] if data[1] != 0xFF else 0
        settings.selected_area = data[2] if data[2] != 0xFF else 0
        settings.selected_channel = data[3] if data[3] != 0xFF else 0
        settings.scan_mode = data[4] if data[4] != 0xFF else 0

        # Clamp to valid ranges
        settings.selected_area = min(max(settings.selected_area, 0), 15)
        settings.selected_channel = min(max(settings.selected_channel, 0), 15)

        # Parse presets (bytes 5-772, 16 presets x 48 bytes)
        settings.presets = []
        for i in range(FM_PRESET_COUNT):
            offset = FM_HEADER_SIZE + (i * FM_PRESET_SIZE)
            preset_data = data[offset:offset + FM_PRESET_SIZE]
            preset = FMParser._parse_preset(preset_data, i)
            settings.presets.append(preset)

        return settings

    @staticmethod
    def _parse_preset(data: bytes, index: int) -> FMPreset:
        """Parse a single 48-byte preset entry.

        Args:
            data: 48 bytes of preset data
            index: Preset index (0-15)

        Returns:
            FMPreset object
        """
        preset = FMPreset(index=index)

        if len(data) < FM_PRESET_SIZE:
            return preset

        # Parse name (bytes 0-15, GBK encoded)
        name_data = data[0:FM_NAME_SIZE]
        preset.name = FMParser._decode_name(name_data)

        # Parse frequencies (bytes 16-47, 16 x 2-byte uint16 LE)
        preset.frequencies = []
        for i in range(FM_FREQ_COUNT):
            freq_offset = FM_NAME_SIZE + (i * FM_FREQ_SIZE)
            freq_bytes = data[freq_offset:freq_offset + FM_FREQ_SIZE]
            freq = FMParser._decode_frequency(freq_bytes)
            preset.frequencies.append(freq)

        return preset

    @staticmethod
    def _decode_name(data: bytes) -> str:
        """Decode GBK name string with 0xFF padding.

        Args:
            data: Raw name bytes (16 bytes)

        Returns:
            Decoded string
        """
        # Strip 0xFF padding
        clean_data = bytearray()
        for b in data:
            if b == 0xFF:
                break
            clean_data.append(b)

        if not clean_data:
            return ""

        # Try GBK decoding first, fallback to latin-1
        try:
            return bytes(clean_data).decode('gbk').strip('\x00')
        except UnicodeDecodeError:
            try:
                return bytes(clean_data).decode('latin-1').strip('\x00')
            except UnicodeDecodeError:
                return ""

    @staticmethod
    def _decode_frequency(data: bytes) -> float:
        """Decode frequency from 2-byte uint16 LE.

        Args:
            data: 2 bytes (little-endian uint16)

        Returns:
            Frequency in MHz, or 0.0 if empty
        """
        if len(data) < 2:
            return 0.0

        value = int.from_bytes(data, 'little')

        # 0xFFFF means empty
        if value == 0xFFFF or value == 0:
            return 0.0

        # Convert to MHz (value is frequency x 10)
        freq = value / 10.0

        # Validate range
        if freq < FM_FREQ_MIN or freq > FM_FREQ_MAX:
            return 0.0

        return freq


class FMSerializer:
    """Serializer for FM radio settings to codeplug format"""

    @staticmethod
    def serialize(settings: FMSettings) -> bytes:
        """Serialize FMSettings to bytes.

        Args:
            settings: FMSettings object to serialize

        Returns:
            1024 bytes for codeplug
        """
        data = bytearray(FM_DATA_SIZE)

        # Fill with 0xFF
        for i in range(FM_DATA_SIZE):
            data[i] = 0xFF

        # Write header (bytes 0-4)
        data[0] = settings.mode & 0xFF
        data[1] = settings.standby & 0xFF
        data[2] = min(max(settings.selected_area, 0), 15) & 0xFF
        data[3] = min(max(settings.selected_channel, 0), 15) & 0xFF
        data[4] = settings.scan_mode & 0xFF

        # Write presets (bytes 5-772)
        for i, preset in enumerate(settings.presets[:FM_PRESET_COUNT]):
            offset = FM_HEADER_SIZE + (i * FM_PRESET_SIZE)
            preset_bytes = FMSerializer._serialize_preset(preset)
            data[offset:offset + FM_PRESET_SIZE] = preset_bytes

        return bytes(data)

    @staticmethod
    def _serialize_preset(preset: FMPreset) -> bytes:
        """Serialize a single preset to 48 bytes.

        Args:
            preset: FMPreset object

        Returns:
            48 bytes for preset
        """
        data = bytearray(FM_PRESET_SIZE)

        # Fill with 0xFF
        for i in range(FM_PRESET_SIZE):
            data[i] = 0xFF

        # Write name (bytes 0-15, GBK encoded)
        name_bytes = FMSerializer._encode_name(preset.name)
        data[0:len(name_bytes)] = name_bytes

        # Write frequencies (bytes 16-47)
        for i, freq in enumerate(preset.frequencies[:FM_FREQ_COUNT]):
            freq_offset = FM_NAME_SIZE + (i * FM_FREQ_SIZE)
            freq_bytes = FMSerializer._encode_frequency(freq)
            data[freq_offset:freq_offset + FM_FREQ_SIZE] = freq_bytes

        return bytes(data)

    @staticmethod
    def _encode_name(name: str) -> bytes:
        """Encode name to GBK bytes.

        Args:
            name: Name string (max 16 chars)

        Returns:
            Encoded bytes (up to 16 bytes)
        """
        if not name:
            return b''

        # Truncate to max length
        name = name[:FM_NAME_SIZE]

        # Try GBK encoding first, fallback to latin-1
        try:
            encoded = name.encode('gbk')
        except UnicodeEncodeError:
            try:
                encoded = name.encode('latin-1')
            except UnicodeEncodeError:
                encoded = b''

        # Truncate if GBK encoding exceeds 16 bytes
        return encoded[:FM_NAME_SIZE]

    @staticmethod
    def _encode_frequency(freq: float) -> bytes:
        """Encode frequency to 2-byte uint16 LE.

        Args:
            freq: Frequency in MHz

        Returns:
            2 bytes (little-endian uint16)
        """
        # Empty frequency
        if freq <= 0.0:
            return bytes([0xFF, 0xFF])

        # Validate and clamp to valid range
        if freq < FM_FREQ_MIN or freq > FM_FREQ_MAX:
            return bytes([0xFF, 0xFF])

        # Convert to uint16 (frequency x 10)
        value = int(round(freq * 10))

        return value.to_bytes(2, 'little')
