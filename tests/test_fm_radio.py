"""Tests for FM Radio parser and serializer"""

try:
    import pytest
except ImportError:
    pytest = None

from rt4d_codeplug.fm_radio import FMParser, FMSerializer, FM_FREQ_MIN, FM_FREQ_MAX
from rt4d_codeplug.models import FMSettings, FMPreset


class TestFMParser:
    """Tests for FMParser"""

    def test_parse_empty_data(self):
        """Test parsing all-0xFF data (empty FM settings)"""
        data = bytes([0xFF] * 1024)
        settings = FMParser.parse(data)

        assert settings.mode == 0
        assert settings.standby == 0
        assert settings.selected_area == 0
        assert settings.selected_channel == 0
        assert settings.scan_mode == 0
        assert len(settings.presets) == 16

        # All presets should be empty
        for preset in settings.presets:
            assert preset.name == ""
            assert all(f == 0.0 for f in preset.frequencies)

    def test_parse_header_fields(self):
        """Test parsing header fields"""
        data = bytearray([0xFF] * 1024)
        data[0] = 1  # mode = Channel Mode
        data[1] = 2  # standby = 2
        data[2] = 5  # selected_area = 5
        data[3] = 10  # selected_channel = 10
        data[4] = 1  # scan_mode = Scan All

        settings = FMParser.parse(bytes(data))

        assert settings.mode == 1
        assert settings.standby == 2
        assert settings.selected_area == 5
        assert settings.selected_channel == 10
        assert settings.scan_mode == 1

    def test_parse_preset_name_ascii(self):
        """Test parsing ASCII preset name"""
        data = bytearray([0xFF] * 1024)
        # First preset starts at offset 5
        name = b"Test Zone"
        data[5:5 + len(name)] = name

        settings = FMParser.parse(bytes(data))

        assert settings.presets[0].name == "Test Zone"

    def test_parse_preset_name_gbk(self):
        """Test parsing GBK encoded preset name"""
        data = bytearray([0xFF] * 1024)
        # GBK encoded Chinese characters
        name = "测试".encode('gbk')
        data[5:5 + len(name)] = name

        settings = FMParser.parse(bytes(data))

        assert settings.presets[0].name == "测试"

    def test_parse_frequencies(self):
        """Test parsing frequency values"""
        data = bytearray([0xFF] * 1024)
        # First preset, first frequency at offset 5 + 16 = 21
        # 88.5 MHz = 885 = 0x0375 (little-endian: 0x75, 0x03)
        data[21] = 0x75
        data[22] = 0x03

        # Second frequency: 107.9 MHz = 1079 = 0x0437
        data[23] = 0x37
        data[24] = 0x04

        settings = FMParser.parse(bytes(data))

        assert settings.presets[0].frequencies[0] == 88.5
        assert settings.presets[0].frequencies[1] == 107.9

    def test_parse_empty_frequency(self):
        """Test that 0xFFFF is parsed as empty frequency"""
        data = bytearray([0xFF] * 1024)
        # First frequency is already 0xFFFF

        settings = FMParser.parse(bytes(data))

        assert settings.presets[0].frequencies[0] == 0.0

    def test_parse_invalid_frequency_out_of_range(self):
        """Test that out-of-range frequencies are treated as empty"""
        data = bytearray([0xFF] * 1024)
        # Set frequency to 50 MHz (500) - out of range
        data[21] = 0xF4
        data[22] = 0x01  # 500 = 0x01F4

        settings = FMParser.parse(bytes(data))

        assert settings.presets[0].frequencies[0] == 0.0


class TestFMSerializer:
    """Tests for FMSerializer"""

    def test_serialize_empty_settings(self):
        """Test serializing empty FM settings"""
        settings = FMSettings()
        data = FMSerializer.serialize(settings)

        assert len(data) == 1024
        # Header should be zeros
        assert data[0] == 0
        assert data[1] == 0
        assert data[2] == 0
        assert data[3] == 0
        assert data[4] == 0

    def test_serialize_header_fields(self):
        """Test serializing header fields"""
        settings = FMSettings()
        settings.mode = 1
        settings.standby = 2
        settings.selected_area = 5
        settings.selected_channel = 10
        settings.scan_mode = 1

        data = FMSerializer.serialize(settings)

        assert data[0] == 1
        assert data[1] == 2
        assert data[2] == 5
        assert data[3] == 10
        assert data[4] == 1

    def test_serialize_preset_name(self):
        """Test serializing preset name"""
        settings = FMSettings()
        settings.presets[0].name = "Test Zone"

        data = FMSerializer.serialize(settings)

        # First preset name starts at offset 5
        name_bytes = data[5:5 + 9]
        assert name_bytes == b"Test Zone"

    def test_serialize_frequency(self):
        """Test serializing frequency values"""
        settings = FMSettings()
        settings.presets[0].frequencies[0] = 88.5
        settings.presets[0].frequencies[1] = 107.9

        data = FMSerializer.serialize(settings)

        # First frequency at offset 5 + 16 = 21
        freq1 = int.from_bytes(data[21:23], 'little')
        freq2 = int.from_bytes(data[23:25], 'little')

        assert freq1 == 885  # 88.5 * 10
        assert freq2 == 1079  # 107.9 * 10

    def test_serialize_empty_frequency(self):
        """Test that empty frequency serializes as 0xFFFF"""
        settings = FMSettings()
        settings.presets[0].frequencies[0] = 0.0

        data = FMSerializer.serialize(settings)

        # First frequency at offset 5 + 16 = 21
        assert data[21] == 0xFF
        assert data[22] == 0xFF


class TestFMRoundtrip:
    """Tests for FM parser/serializer roundtrip"""

    def test_roundtrip_empty(self):
        """Test roundtrip with empty settings"""
        original = FMSettings()
        data = FMSerializer.serialize(original)
        parsed = FMParser.parse(data)

        assert parsed.mode == original.mode
        assert parsed.standby == original.standby
        assert parsed.selected_area == original.selected_area
        assert parsed.selected_channel == original.selected_channel
        assert parsed.scan_mode == original.scan_mode
        assert len(parsed.presets) == len(original.presets)

    def test_roundtrip_with_data(self):
        """Test roundtrip with actual data"""
        original = FMSettings()
        original.mode = 1
        original.scan_mode = 1
        original.selected_area = 3
        original.selected_channel = 7
        original.presets[0].name = "Rock FM"
        original.presets[0].frequencies[0] = 88.5
        original.presets[0].frequencies[1] = 92.3
        original.presets[0].frequencies[15] = 107.9
        original.presets[15].name = "News Radio"
        original.presets[15].frequencies[0] = 101.1

        data = FMSerializer.serialize(original)
        parsed = FMParser.parse(data)

        assert parsed.mode == 1
        assert parsed.scan_mode == 1
        assert parsed.selected_area == 3
        assert parsed.selected_channel == 7
        assert parsed.presets[0].name == "Rock FM"
        assert parsed.presets[0].frequencies[0] == 88.5
        assert parsed.presets[0].frequencies[1] == 92.3
        assert parsed.presets[0].frequencies[15] == 107.9
        assert parsed.presets[15].name == "News Radio"
        assert parsed.presets[15].frequencies[0] == 101.1

    def test_roundtrip_gbk_name(self):
        """Test roundtrip with GBK encoded name"""
        original = FMSettings()
        original.presets[0].name = "测试电台"

        data = FMSerializer.serialize(original)
        parsed = FMParser.parse(data)

        assert parsed.presets[0].name == "测试电台"

    def test_roundtrip_boundary_frequencies(self):
        """Test roundtrip with boundary frequency values"""
        original = FMSettings()
        original.presets[0].frequencies[0] = FM_FREQ_MIN  # 76.0
        original.presets[0].frequencies[1] = FM_FREQ_MAX  # 108.0

        data = FMSerializer.serialize(original)
        parsed = FMParser.parse(data)

        assert parsed.presets[0].frequencies[0] == FM_FREQ_MIN
        assert parsed.presets[0].frequencies[1] == FM_FREQ_MAX
