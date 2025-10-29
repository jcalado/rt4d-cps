"""RT-4D Codeplug Constants and Memory Maps"""

#  .4rdmf File Structure Offsets
OFFSET_CFG = 0x00000
OFFSET_CHANNELS = 0x01000
OFFSET_CONTACTS = 0x0D000
OFFSET_GROUPLISTS = 0x1D000
OFFSET_ENCRYPT = 0x20000
OFFSET_ZONES = 0x23000
OFFSET_FM = 0x43000

# Section Sizes
SIZE_CFG = 4096  # 0x1000
SIZE_CHANNELS = 49152  # 0xC000 (1024 × 48)
SIZE_CONTACTS = 65536  # 0x10000 (2048 × 32)
SIZE_GROUPLISTS = 12288  # 0x3000
SIZE_ENCRYPT = 12288  # 0x3000
SIZE_ZONES = 131072  # 0x20000 (256 × 512)
SIZE_FM = 1024  # 0x400

# Total file size
TOTAL_SIZE = 275456  # 0x43400

# Per-item sizes
CHANNEL_SIZE = 48
CONTACT_SIZE = 32
ZONE_SIZE = 512

# Max counts
MAX_CHANNELS = 1024
MAX_CONTACTS = 2048
MAX_ZONES = 256

# SPI Flash Memory Map (for direct radio flashing)
SPI_REGIONS = {
    "calibration": {"region_id": 0x40, "address": 0x000000, "size": 0x001000},
    "main_settings": {"region_id": 0x90, "address": 0x002000, "size": 0x001000},
    "channels": {"region_id": 0x91, "address": 0x004000, "size": 0x00C000},
    "zones": {"region_id": 0x92, "address": 0x01C000, "size": 0x020000},
    "contacts": {"region_id": 0x93, "address": 0x05C000, "size": 0x010000},
    "groups": {"region_id": 0x94, "address": 0x07C000, "size": 0x003000},
    "dmr_keys": {"region_id": 0x95, "address": 0x082000, "size": 0x003000},
    "call_log": {"region_id": 0x96, "address": 0x088000, "size": 0x00C000},
    "default_sms": {"region_id": 0x97, "address": 0x094000, "size": 0x001000},
    "schedules": {"region_id": 0x98, "address": 0x0C6000, "size": 0x008000},
    "fm_settings": {"region_id": 0x99, "address": 0x0D6000, "size": 0x001000},
}

# Channel modes
CHANNEL_MODE_DIGITAL = 0x00
CHANNEL_MODE_ANALOG = 0x01

# Power levels
POWER_LOW = 0x00
POWER_HIGH = 0x01

# Scan settings
SCAN_ADD = 0x00
SCAN_REMOVE = 0x80

# Contact types
CONTACT_TYPE_PRIVATE = 0x00
CONTACT_TYPE_GROUP = 0x01
CONTACT_TYPE_ALL_CALL = 0x02

# Empty marker
EMPTY_BYTE = 0xFF

# Frequency conversion
# Stored frequency = actual_freq_mhz × 100000
FREQ_MULTIPLIER = 100000
