"""CTCSS/DCS Tone Encoding and Decoding for RT-4D Analog Channels

This module provides functions to encode and decode analog sub-audio tones
(CTCSS and DCS) for the RT-4D radio's binary codeplug format.

The encoding uses a 16-bit value stored in little-endian format:
- Bits 12-15 (upper 4 bits): Type indicator
  - 0x0: None/disabled
  - 0x1: CTCSS tone
  - 0x2: DCS Normal polarity
  - 0x3: DCS Inverted polarity
- Bits 0-11 (lower 12 bits): Value
  - CTCSS: Frequency × 10 (e.g., 67.0 Hz → 670)
  - DCS: Octal code as decimal (e.g., D023 → 0×64 + 2×8 + 3 = 19)
"""

from typing import Optional
import struct


# DCS code mapping (octal code as index)
# This maps decimal index to DCS octal code string
# Example: index 19 = "023" (because 023 octal = 2*8 + 3 = 19 decimal)
DCS_CODES = [
    "000", "001", "002", "003", "004", "005", "006", "007", "010", "011",
    "012", "013", "014", "015", "016", "017", "020", "021", "022", "023",
    "024", "025", "026", "027", "030", "031", "032", "033", "034", "035",
    "036", "037", "040", "041", "042", "043", "044", "045", "046", "047",
    "050", "051", "052", "053", "054", "055", "056", "057", "060", "061",
    "062", "063", "064", "065", "066", "067", "070", "071", "072", "073",
    "074", "075", "076", "077", "100", "101", "102", "103", "104", "105",
    "106", "107", "110", "111", "112", "113", "114", "115", "116", "117",
    "120", "121", "122", "123", "124", "125", "126", "127", "130", "131",
    "132", "133", "134", "135", "136", "137", "140", "141", "142", "143",
    "144", "145", "146", "147", "150", "151", "152", "153", "154", "155",
    "156", "157", "160", "161", "162", "163", "164", "165", "166", "167",
    "170", "171", "172", "173", "174", "175", "176", "177", "200", "201",
    "202", "203", "204", "205", "206", "207", "210", "211", "212", "213",
    "214", "215", "216", "217", "220", "221", "222", "223", "224", "225",
    "226", "227", "230", "231", "232", "233", "234", "235", "236", "237",
    "240", "241", "242", "243", "244", "245", "246", "247", "250", "251",
    "252", "253", "254", "255", "256", "257", "260", "261", "262", "263",
    "264", "265", "266", "267", "270", "271", "272", "273", "274", "275",
    "276", "277", "300", "301", "302", "303", "304", "305", "306", "307",
    "310", "311", "312", "313", "314", "315", "316", "317", "320", "321",
    "322", "323", "324", "325", "326", "327", "330", "331", "332", "333",
    "334", "335", "336", "337", "340", "341", "342", "343", "344", "345",
    "346", "347", "350", "351", "352", "353", "354", "355", "356", "357",
    "360", "361", "362", "363", "364", "365", "366", "367", "370", "371",
    "372", "373", "374", "375", "376", "377", "400", "401", "402", "403",
    "404", "405", "406", "407", "410", "411", "412", "413", "414", "415",
    "416", "417", "420", "421", "422", "423", "424", "425", "426", "427",
    "430", "431", "432", "433", "434", "435", "436", "437", "440", "441",
    "442", "443", "444", "445", "446", "447", "450", "451", "452", "453",
    "454", "455", "456", "457", "460", "461", "462", "463", "464", "465",
    "466", "467", "470", "471", "472", "473", "474", "475", "476", "477",
    "500", "501", "502", "503", "504", "505", "506", "507", "510", "511",
    "512", "513", "514", "515", "516", "517", "520", "521", "522", "523",
    "524", "525", "526", "527", "530", "531", "532", "533", "534", "535",
    "536", "537", "540", "541", "542", "543", "544", "545", "546", "547",
    "550", "551", "552", "553", "554", "555", "556", "557", "560", "561",
    "562", "563", "564", "565", "566", "567", "570", "571", "572", "573",
    "574", "575", "576", "577", "600", "601", "602", "603", "604", "605",
    "606", "607", "610", "611", "612", "613", "614", "615", "616", "617",
    "620", "621", "622", "623", "624", "625", "626", "627", "630", "631",
    "632", "633", "634", "635", "636", "637", "640", "641", "642", "643",
    "644", "645", "646", "647", "650", "651", "652", "653", "654", "655",
    "656", "657", "660", "661", "662", "663", "664", "665", "666", "667",
    "670", "671", "672", "673", "674", "675", "676", "677", "700", "701",
    "702", "703", "704", "705", "706", "707", "710", "711", "712", "713",
    "714", "715", "716", "717", "720", "721", "722", "723", "724", "725",
    "726", "727", "730", "731", "732", "733", "734", "735", "736", "737",
    "740", "741", "742", "743", "744", "745", "746", "747", "750", "751",
    "752", "753", "754", "755", "756", "757", "760", "761", "762", "763",
    "764", "765", "766", "767", "770", "771", "772", "773", "774", "775"
]

# Create reverse mapping for encoding (DCS code string → decimal index)
DCS_TO_INDEX = {code: idx for idx, code in enumerate(DCS_CODES)}


def encode_subaudio(tone_str: Optional[str]) -> int:
    """Encode a CTCSS/DCS tone string to a 16-bit integer value.

    Args:
        tone_str: Tone string in one of these formats:
            - None or "None": No tone (returns 0x0000)
            - "67.0": CTCSS tone in Hz (returns 0x1000 | (freq * 10))
            - "D023N": DCS code normal polarity (returns 0x2000 | octal_to_decimal)
            - "D023I": DCS code inverted polarity (returns 0x3000 | octal_to_decimal)

    Returns:
        16-bit integer value to be stored in codeplug (little-endian)

    Examples:
        >>> encode_subaudio(None)
        0
        >>> encode_subaudio("None")
        0
        >>> encode_subaudio("67.0")
        4768  # 0x1000 | 670 = 0x12A0
        >>> encode_subaudio("D023N")
        8211  # 0x2000 | 19 = 0x2013
        >>> encode_subaudio("D023I")
        12307  # 0x3000 | 19 = 0x3013
    """
    if not tone_str or tone_str == "None":
        return 0x0000

    # CTCSS tone (format: "67.0")
    if not tone_str.startswith('D'):
        try:
            # Remove decimal point and convert to integer
            freq_int = int(tone_str.replace(".", ""))
            # Mask to 12 bits and add CTCSS indicator (0x1000)
            return (freq_int & 0x0FFF) | 0x1000
        except (ValueError, AttributeError):
            return 0x0000

    # DCS code (format: "D023N" or "D023I")
    if len(tone_str) < 5:
        return 0x0000

    try:
        # Extract octal code (positions 1-3, e.g., "023")
        dcs_code = tone_str[1:4]

        # Convert octal string to decimal index
        # Method: treat as octal digits and convert to decimal
        # E.g., "023" = 0*64 + 2*8 + 3 = 19
        digit1 = int(dcs_code[0])
        digit2 = int(dcs_code[1])
        digit3 = int(dcs_code[2])
        decimal_index = digit1 * 64 + digit2 * 8 + digit3

        # Mask to 12 bits
        decimal_index &= 0x0FFF

        # Check polarity (position 4)
        if tone_str[4] == 'I':
            # Inverted polarity (0x3000)
            return decimal_index | 0x3000
        else:
            # Normal polarity (0x2000)
            return decimal_index | 0x2000
    except (ValueError, IndexError):
        return 0x0000


def decode_subaudio(value: int) -> Optional[str]:
    """Decode a 16-bit integer value to a CTCSS/DCS tone string.

    Args:
        value: 16-bit integer from codeplug

    Returns:
        Tone string in one of these formats:
            - None: No tone (value = 0x0000)
            - "67.0": CTCSS tone in Hz
            - "D023N": DCS code normal polarity
            - "D023I": DCS code inverted polarity

    Examples:
        >>> decode_subaudio(0)
        None
        >>> decode_subaudio(0x12A0)
        "67.0"
        >>> decode_subaudio(0x2013)
        "D023N"
        >>> decode_subaudio(0x3013)
        "D023I"
    """
    # Extract type indicator (upper 4 bits)
    type_bits = (value >> 12) & 0x0F

    # Extract value (lower 12 bits)
    tone_value = value & 0x0FFF

    # No tone / disabled
    if type_bits == 0x0:
        return None

    # CTCSS tone (0x1xxx)
    if type_bits == 0x1:
        # Convert integer to frequency string with decimal point
        # E.g., 670 → "67.0"
        freq_str = f"{tone_value / 10:.1f}"
        return freq_str

    # DCS Normal polarity (0x2xxx)
    if type_bits == 0x2:
        if tone_value < len(DCS_CODES):
            return f"D{DCS_CODES[tone_value]}N"
        return None

    # DCS Inverted polarity (0x3xxx)
    if type_bits == 0x3:
        if tone_value < len(DCS_CODES):
            return f"D{DCS_CODES[tone_value]}I"
        return None

    # Unknown type
    return None


def encode_subaudio_bytes(tone_str: Optional[str]) -> bytes:
    """Encode a CTCSS/DCS tone string to 2 bytes (little-endian).

    Args:
        tone_str: Tone string (see encode_subaudio for format)

    Returns:
        2 bytes in little-endian format

    Examples:
        >>> encode_subaudio_bytes("67.0")
        b'\\xa0\\x12'  # 0x12A0 in little-endian
    """
    value = encode_subaudio(tone_str)
    return struct.pack('<H', value)


def decode_subaudio_bytes(data: bytes) -> Optional[str]:
    """Decode 2 bytes (little-endian) to a CTCSS/DCS tone string.

    Args:
        data: 2 bytes in little-endian format

    Returns:
        Tone string (see decode_subaudio for format)

    Examples:
        >>> decode_subaudio_bytes(b'\\xa0\\x12')
        "67.0"
    """
    if len(data) < 2:
        return None
    value = struct.unpack('<H', data[:2])[0]
    return decode_subaudio(value)
