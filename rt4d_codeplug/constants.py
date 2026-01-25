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
GROUP_LIST_SIZE = 272
GROUP_LIST_SIZE_NEW = 80

# Max counts
MAX_CHANNELS = 1024
MAX_CONTACTS = 2048
MAX_ZONES = 256
MAX_GROUP_LISTS = 32
MAX_GROUP_LIST_IDS = 128
MAX_GROUP_LISTS_NEW = 150
MAX_GROUP_LIST_IDS_NEW = 32

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

# Beta firmware layout detection
BETA41_MAGIC = b'DTCN'

# Settings bank addresses (SPI flash)
SETTINGS_BANK0_ADDR = 0x002000  # Bank 0 settings location
SETTINGS_BANK1_ADDR = 0x003000  # Bank 1 settings location (beta41+)
BANK0_MAGIC_OFFSET = 0x002FFC   # DTCN magic location for bank 0 (0x2000 + 0xFFC)
BANK1_MAGIC_OFFSET = 0x003FFC   # DTCN magic location for bank 1 (0x3000 + 0xFFC)

# Message SPI Flash Memory Map
# All messages stored sequentially starting at 0x94000 (KB offset 592)
MESSAGE_REGIONS = {
    "presets": {"address": 0x094000, "size": 0x1000, "count": 16},      # 4KB, 16 entries
    "drafts": {"address": 0x095000, "size": 0x10000, "count": 256},     # 64KB, 256 entries
    "inbox": {"address": 0x0A5000, "size": 0x10000, "count": 256},      # 64KB, 256 entries
    "outbox": {"address": 0x0B5000, "size": 0x10000, "count": 256},     # 64KB, 256 entries
}

# Message structure constants
MESSAGE_ENTRY_SIZE = 256
MESSAGE_TEXT_OFFSET = 56
MESSAGE_TEXT_MAX_LENGTH = 200

# Message count limits
MAX_PRESET_MESSAGES = 16
MAX_DRAFT_MESSAGES = 256
MAX_INBOX_MESSAGES = 256
MAX_OUTBOX_MESSAGES = 256
