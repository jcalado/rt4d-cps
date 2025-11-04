"""RT-4D Codeplug Data Models"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class ChannelMode(Enum):
    """Channel operating mode"""
    DIGITAL = 0x00  # DMR
    ANALOG = 0x01   # FM


class PowerLevel(Enum):
    """Transmit power level"""
    LOW = 0x00
    HIGH = 0x01


class ScanMode(Enum):
    """Scan list inclusion"""
    ADD = 0x00
    REMOVE = 0x80


class AnalogModulation(Enum):
    """Analog channel modulation type"""
    FM = 0x00
    AM = 0x01
    SSB = 0x02


class ContactType(Enum):
    """DMR contact type"""
    PRIVATE = 0x00
    GROUP = 0x01
    ALL_CALL = 0x02


class EncryptionType(Enum):
    """Encryption algorithm type"""
    ARC = 0x00
    AES_128 = 0x01
    AES_256 = 0x02


@dataclass
class Channel:
    """Radio channel configuration"""
    index: int
    name: str = ""
    rx_freq: float = 0.0  # MHz
    tx_freq: float = 0.0  # MHz
    mode: ChannelMode = ChannelMode.ANALOG
    power: PowerLevel = PowerLevel.HIGH
    scan: ScanMode = ScanMode.ADD
    enabled: bool = False

    # Digital/DMR specific
    dmr_time_slot: int = 0  # 0=Slot1, 1=Slot2
    dmr_color_code: int = 1  # 0-15
    dmr_mode: int = 0
    dmr_monitor: int = 0  # Promiscuous mode (0=Off, 1=On) (offset 0x0E)
    group_list_index: int = 0
    contact_index: int = 0
    encrypt_index: int = 0
    tx_priority: int = 0
    tot: int = 0  # Transmit timeout
    alarm: int = 0
    dmr_id: int = 0
    use_radio_id: bool = True  # True=use radio's DMR ID, False=use channel's custom DMR ID

    # Analog specific
    rx_ctcss: Optional[str] = None  # e.g., "67.0" or "D023N"
    tx_ctcss: Optional[str] = None
    scramble: int = 0
    analog_modulation: AnalogModulation = AnalogModulation.FM  # FM/AM/SSB (offset 0x00)
    bandwidth: int = 0  # Bandwidth: 0=Wide/25kHz, 1=Narrow/12.5kHz (offset 0x03)
    tx_priority_analog: int = 0  # TX priority for analog (offset 0x11)
    tot_analog: int = 0  # Transmit timeout for analog (offset 0x12, lower 5 bits)
    ctdcs_select: int = 0  # CT/DCS select mode (offset 0x12, bits 5-7): 0=Normal, 1=Encrypt1, 2=Encrypt2, 3=Encrypt3, 4=Decode
    tail_tone: int = 0  # Tail tone elimination (offset 0x13, upper 4 bits)
    encrypted_code_1: int = 0  # Encrypted sub-audio code 1 (offset 0x14-0x17, 32-bit hex)
    encrypted_code_2: int = 0  # Encrypted sub-audio code 2 (offset 0x18-0x1B, 32-bit hex)
    encrypted_code_3: int = 0  # Encrypted sub-audio code 3 (offset 0x1C-0x1F, 32-bit hex)

    def __post_init__(self):
        """Validate channel data"""
        if self.rx_freq < 0 or self.rx_freq > 1000:
            raise ValueError(f"Invalid RX frequency: {self.rx_freq}")
        if self.tx_freq < 0 or self.tx_freq > 1000:
            raise ValueError(f"Invalid TX frequency: {self.tx_freq}")
        if self.dmr_color_code < 0 or self.dmr_color_code > 15:
            raise ValueError(f"Invalid color code: {self.dmr_color_code}")
        if len(self.name) > 16:
            self.name = self.name[:16]

    def is_empty(self) -> bool:
        """Check if channel is empty/unused"""
        return not self.enabled or self.rx_freq == 0.0

    def is_digital(self) -> bool:
        """Check if channel is digital/DMR"""
        return self.mode == ChannelMode.DIGITAL

    def is_analog(self) -> bool:
        """Check if channel is analog/FM"""
        return self.mode == ChannelMode.ANALOG


@dataclass
class Contact:
    """DMR contact/talkgroup"""
    index: int
    name: str = ""
    contact_type: ContactType = ContactType.GROUP
    dmr_id: int = 0

    def __post_init__(self):
        """Validate contact data"""
        if len(self.name) > 16:
            self.name = self.name[:16]
        if self.dmr_id < 0 or self.dmr_id > 16777215:  # 24-bit max
            raise ValueError(f"Invalid DMR ID: {self.dmr_id}")
        # All Call contacts must have DMR ID 16777215 (0xFFFFFF)
        if self.contact_type == ContactType.ALL_CALL and self.dmr_id != 16777215:
            self.dmr_id = 16777215

    def is_empty(self) -> bool:
        """Check if contact is empty/unused"""
        if not self.name:
            return True
        # All Call contacts must have dmr_id=16777215, so check for that
        if self.contact_type == ContactType.ALL_CALL:
            return False
        if self.dmr_id == 0:
            return True
        return False


@dataclass
class EncryptionKey:
    """Encryption key configuration"""
    index: int
    alias: str = ""
    enc_type: EncryptionType = EncryptionType.ARC
    value: str = ""  # Hex string (10/32/64 chars depending on type)

    def __post_init__(self):
        """Validate encryption key data"""
        if len(self.alias) > 14:
            self.alias = self.alias[:14]
        # Validate hex string
        if self.value:
            try:
                int(self.value, 16)
            except ValueError:
                raise ValueError(f"Invalid hex value: {self.value}")
        # Validate length based on type
        expected_len = self.get_expected_length()
        if len(self.value) > expected_len:
            self.value = self.value[:expected_len]

    def get_expected_length(self) -> int:
        """Get expected hex string length for encryption type"""
        if self.enc_type == EncryptionType.ARC:
            return 10  # 5 bytes
        elif self.enc_type == EncryptionType.AES_128:
            return 32  # 16 bytes
        elif self.enc_type == EncryptionType.AES_256:
            return 64  # 32 bytes
        return 10

    def is_empty(self) -> bool:
        """Check if encryption key is empty/unused"""
        return not self.alias or not self.value


@dataclass
class GroupList:
    """DMR Group List (RX Group)"""
    index: int
    name: str = ""
    contacts: List[int] = field(default_factory=list)  # List of contact indices (max 128)

    def __post_init__(self):
        """Validate group list data"""
        if len(self.name) > 14:
            self.name = self.name[:14]
        if len(self.contacts) > 128:
            self.contacts = self.contacts[:128]

    def is_empty(self) -> bool:
        """Check if group list is empty/unused"""
        return not self.name

    def add_contact(self, contact_index: int):
        """Add a contact to this group list"""
        if len(self.contacts) < 128 and contact_index not in self.contacts:
            self.contacts.append(contact_index)

    def remove_contact(self, contact_index: int):
        """Remove a contact from this group list"""
        if contact_index in self.contacts:
            self.contacts.remove(contact_index)


@dataclass
class Zone:
    """Zone (channel group)"""
    index: int
    name: str = ""
    channels: List[int] = field(default_factory=list)  # List of channel indices

    def __post_init__(self):
        """Validate zone data"""
        if len(self.name) > 16:
            self.name = self.name[:16]

    def is_empty(self) -> bool:
        """Check if zone is empty/unused"""
        return not self.name

    def add_channel(self, channel_index: int):
        """Add a channel to this zone (max 200 channels)"""
        if len(self.channels) >= 200:
            raise ValueError("Zone can contain maximum 200 channels")
        if channel_index not in self.channels:
            self.channels.append(channel_index)

    def remove_channel(self, channel_index: int):
        """Remove a channel from this zone"""
        if channel_index in self.channels:
            self.channels.remove(channel_index)


@dataclass
class RadioSettings:
    """General radio configuration settings"""
    # Identity
    radio_name: str = ""
    radio_id: int = 0
    startup_message: str = ""
    startup_password: str = ""

    # Audio/UI
    voice_prompt: int = 0
    key_beep: int = 0
    key_lock: int = 0
    lock_timer: int = 0  # Lock timer in seconds (0=off, 5-600)

    # Audio Settings
    tone_frequency: int = 0  # Tone frequency in Hz (offset 256-257, 16-bit LE)
    squelch_level: int = 5  # Analog squelch level 0-9 (offset 258)
    tx_mic_gain: int = 5  # TX microphone gain 1-10 (offset 261)
    rx_speaker_volume: int = 5  # RX speaker volume 1-10 (offset 262)
    tx_start_beep: int = 0  # TX start beep on/off (offset 267)
    roger_beep: int = 0  # Roger beep on/off (offset 268)
    call_mic_gain: int = 5  # Call mic gain 1-10 (offset 391)
    call_speaker_volume: int = 5  # Called speaker volume 1-10 (offset 392)
    call_start_beep: int = 0  # Call start beep on/off (offset 397)
    call_end_beep: int = 0  # Call end beep on/off (offset 398)
    digital_squelch: int = 5  # Digital squelch level 0-9 (offset 403)

    # Display
    led_timer: int = 0
    led_on_off: int = 1  # LED on/off (0=off, 1=on)
    backlight_brightness: int = 2  # Backlight brightness (0-4)
    menu_timer: int = 0
    display_mode_a: int = 0  # Display mode for band A (0=channel, 1=freq, 2=name)
    display_mode_b: int = 0  # Display mode for band B (0=channel, 1=freq, 2=name)
    lcd_contrast: int = 7  # LCD contrast 0-15 (offset 233)
    display_lines: int = 0  # 6-line or 8-line display mode (offset 234)
    dual_display_mode: int = 0  # Dual display mode (offset 235)

    # DMR Enhancements
    remote_control: int = 0  # Remote control enable (offset 388)
    group_call_hang_time: int = 3000  # Group call hang time in ms (offset 389-390, 16-bit LE)
    private_call_hang_time: int = 3000  # Private call hang time in ms (offset 395-396, 16-bit LE)
    group_id_display: int = 0  # Show group ID during calls (offset 400)
    call_timing_display: int = 0  # Show call timing during calls (offset 404)

    # Power
    power_save_mode: int = 0
    power_save_start: int = 0  # Power save start timer in seconds (0-600)
    apo_enabled: bool = False

    # Operation
    dual_watch: int = 0
    work_mode_a: int = 0
    channel_a: int = 0
    zone_a: int = 0  # Zone for band A
    work_mode_b: int = 0
    channel_b: int = 0
    zone_b: int = 0  # Zone for band B
    talkaround: int = 0  # Talkaround mode (0=off, 1=direct, 2=reverse)
    main_band: int = 0  # Main band selection (0=A, 1=B)
    main_ptt: int = 0  # Main PTT behavior (0=Band A, 1=Main Band)
    vfo_step: int = 6  # VFO frequency step (0-13, default=12.5kHz)
    tx_priority_global: int = 0  # Global TX priority (0=edit, 1=busy)
    alarm_type: int = 0  # Alarm type (0=local, 1=remote, 2=local+remote)

    # Clocks/Timers (4 programmable timers)
    clock_1_mode: int = 0  # 0=off, 1=once, 2=daily
    clock_1_hour: int = 0
    clock_1_minute: int = 0
    clock_2_mode: int = 0
    clock_2_hour: int = 0
    clock_2_minute: int = 0
    clock_3_mode: int = 0
    clock_3_hour: int = 0
    clock_3_minute: int = 0
    clock_4_mode: int = 0
    clock_4_hour: int = 0
    clock_4_minute: int = 0

    # Startup/Boot settings
    startup_picture_enable: int = 0  # Show boot logo (0=off, 1=on)
    tx_protection: int = 0  # TX protection (0=off, 1=on)
    startup_beep_enable: int = 0  # Power-on beep (0=off, 1=on)
    startup_label_enable: int = 0  # Show startup text (0=off, 1=on)
    startup_display_line: int = 0  # Startup message line position
    startup_display_column: int = 0  # Startup message column position
    password_enable: int = 0  # Password enable flag (0=off, 1=on)

    # Radio clock/time
    radio_time_seconds: int = 0  # Current time as total seconds since midnight

    # Frequency lock ranges (4 ranges)
    freq_lock_1_mode: int = 0  # 0=unlock, 1=rx only, 2=lock
    freq_lock_1_start: int = 0  # Start frequency in MHz
    freq_lock_1_end: int = 0  # End frequency in MHz
    freq_lock_2_mode: int = 0
    freq_lock_2_start: int = 0
    freq_lock_2_end: int = 0
    freq_lock_3_mode: int = 0
    freq_lock_3_start: int = 0
    freq_lock_3_end: int = 0
    freq_lock_4_mode: int = 0
    freq_lock_4_start: int = 0
    freq_lock_4_end: int = 0

    # Scan settings
    scan_direction: int = 0  # 0=up, 1=down
    scan_mode: int = 0  # Scan mode
    scan_return: int = 0  # 0=original ch, 1=current ch
    scan_dwell: int = 0  # Scan dwell time

    # Function keys
    key_fs1_short: int = 0  # FS1 short press action
    key_fs1_long: int = 0  # FS1 long press action
    key_fs2_short: int = 0  # FS2 short press action
    key_fs2_long: int = 0  # FS2 long press action
    key_alarm_short: int = 0  # Alarm/Emergency button short press
    key_alarm_long: int = 0  # Alarm/Emergency button long press
    key_0: int = 0  # Numeric key 0 action
    key_1: int = 0  # Numeric key 1 action
    key_2: int = 0  # Numeric key 2 action
    key_3: int = 0  # Numeric key 3 action
    key_4: int = 0  # Numeric key 4 action
    key_5: int = 0  # Numeric key 5 action
    key_6: int = 0  # Numeric key 6 action
    key_7: int = 0  # Numeric key 7 action
    key_8: int = 0  # Numeric key 8 action
    key_9: int = 0  # Numeric key 9 action

    # Advanced Features
    noaa_channel: int = 0  # NOAA weather channel index (offset 272)
    spectrum_scan_mode: int = 0  # Spectrum scan mode (offset 273)
    detection_range: int = 0  # Detection range (offset 274-275, 16-bit LE)
    relay_delay: int = 0  # Relay delay (offset 276)
    glitch_filter: int = 0  # Glitch filter (offset 842)

    # DTMF System
    dtmf_send_delay: int = 0  # Send delay 0-20: 0=0ms, 1=100ms...20=2000ms (offset 512, byte)
    dtmf_send_duration: int = 0  # Send duration 0-17: 30ms-200ms in 10ms steps (offset 513, byte)
    dtmf_send_interval: int = 0  # Send interval 0-17: 30ms-200ms in 10ms steps (offset 514, byte)
    dtmf_send_mode: int = 0  # Send mode 0=Off, 1=TX Begin, 2=TX End, 3=Begin And End (offset 515, byte)
    dtmf_send_select: int = 0  # Preset code selection 0-15 (DTMF-01 to DTMF-16) (offset 516, byte)
    dtmf_display_enable: int = 0  # DTMF display/decode enable 0=Off, 1=On (offset 517, byte)
    dtmf_gain: int = 0  # DTMF gain 0-127 (offset 518, byte)
    dtmf_decode_threshold: int = 0  # Decode threshold 0-63 (offset 519, byte)
    dtmf_remote_control: int = 0  # Remote control enable 0=Off, 1=On (offset 520, byte)
    dtmf_remote_cal_time: int = 0  # Remote cal time enable 0=Off, 1=On (offset 521, byte)
    # 20 programmable DTMF codes (each 16 bytes, offsets 522-841)
    # Stored as list of strings, each up to 16 chars, valid characters: 0-9, A-D, *, #
    dtmf_codes: List[str] = field(default_factory=lambda: [""] * 20)

    # DT Custom Firmware Settings (offset 0x380 = 896)
    scan_speed_analog: int = 0  # Scan speed for analog channels (offset 896/0x380)
    tx_backlight: int = 0  # TX backlight behavior (offset 897/0x381)
    green_key_long: int = 0  # Long press code for green key (offset 898/0x382)
    voltage_display: int = 0  # Display voltage on screen (offset 899/0x383)
    live_sub_tone: int = 0  # Live sub-tone detection (offset 900/0x384)
    spectrum_threshold: int = 0  # Spectrum scan squelch threshold (offset 901/0x385)
    sub_tone_ptt: int = 0  # Enable PTT from DTMF list (offset 902/0x386)
    tot_warning: int = 0  # TOT warning beep before timeout (offset 903/0x387)
    scan_end: int = 0  # Scan end behavior (offset 904/0x388)
    scan_continue: int = 0  # Scan continue mode (offset 905/0x389)
    scan_return: int = 0  # Scan return behavior (offset 914/0x392)
    vfo_a_offset: int = 0  # VFO A frequency offset in Hz (offset 915/0x393, 32-bit LE, stored as units of 10 Hz)
    vfo_b_offset: int = 0  # VFO B frequency offset in Hz (offset 919/0x397, 32-bit LE, stored as units of 10 Hz)
    callsign_lookup: int = 0  # Look up callsign in Call Log (offset 923/0x39B)
    dmr_scan_speed: int = 0  # Scan speed for DMR channels (offset 924/0x39C)
    ptt_lock: int = 0  # PTT lock feature (offset 925/0x39D)
    zone_channel_display: int = 0  # Show Zone CH on display (offset 926/0x39E)
    dmr_gid_name: int = 0  # Show DMR group name if available (offset 927/0x39F)


@dataclass
class Codeplug:
    """Complete radio codeplug configuration"""
    channels: List[Channel] = field(default_factory=list)
    contacts: List[Contact] = field(default_factory=list)
    group_lists: List[GroupList] = field(default_factory=list)
    zones: List[Zone] = field(default_factory=list)
    encryption_keys: List[EncryptionKey] = field(default_factory=list)
    settings: Optional[RadioSettings] = None
    cfg_data: bytes = field(default_factory=lambda: b'\xff' * 4096)
    grouplist_data: bytes = field(default_factory=lambda: b'\xff' * 12288)
    encrypt_data: bytes = field(default_factory=lambda: b'\xff' * 12288)
    fm_data: bytes = field(default_factory=lambda: b'\xff' * 1024)

    def get_channel(self, index: int) -> Optional[Channel]:
        """Get channel by index"""
        for ch in self.channels:
            if ch.index == index:
                return ch
        return None

    def get_contact(self, index: int) -> Optional[Contact]:
        """Get contact by index"""
        for contact in self.contacts:
            if contact.index == index:
                return contact
        return None

    def get_group_list(self, index: int) -> Optional[GroupList]:
        """Get group list by index"""
        for gl in self.group_lists:
            if gl.index == index:
                return gl
        return None

    def get_zone(self, index: int) -> Optional[Zone]:
        """Get zone by index"""
        for zone in self.zones:
            if zone.index == index:
                return zone
        return None

    def get_encryption_key(self, index: int) -> Optional[EncryptionKey]:
        """Get encryption key by index"""
        for key in self.encryption_keys:
            if key.index == index:
                return key
        return None

    def add_channel(self, channel: Channel):
        """Add or update a channel"""
        existing = self.get_channel(channel.index)
        if existing:
            self.channels.remove(existing)
        self.channels.append(channel)

    def add_contact(self, contact: Contact):
        """Add or update a contact"""
        existing = self.get_contact(contact.index)
        if existing:
            self.contacts.remove(existing)
        self.contacts.append(contact)

    def add_group_list(self, group_list: GroupList):
        """Add or update a group list"""
        existing = self.get_group_list(group_list.index)
        if existing:
            self.group_lists.remove(existing)
        self.group_lists.append(group_list)

    def add_zone(self, zone: Zone):
        """Add or update a zone"""
        existing = self.get_zone(zone.index)
        if existing:
            self.zones.remove(existing)
        self.zones.append(zone)

    def add_encryption_key(self, key: EncryptionKey):
        """Add or update an encryption key"""
        existing = self.get_encryption_key(key.index)
        if existing:
            self.encryption_keys.remove(existing)
        self.encryption_keys.append(key)

    def get_active_channels(self) -> List[Channel]:
        """Get all non-empty channels"""
        return [ch for ch in self.channels if not ch.is_empty()]

    def get_active_contacts(self) -> List[Contact]:
        """Get all non-empty contacts"""
        return [c for c in self.contacts if not c.is_empty()]

    def get_active_group_lists(self) -> List[GroupList]:
        """Get all non-empty group lists"""
        return [gl for gl in self.group_lists if not gl.is_empty()]

    def get_active_zones(self) -> List[Zone]:
        """Get all non-empty zones"""
        return [z for z in self.zones if not z.is_empty()]

    def get_active_encryption_keys(self) -> List[EncryptionKey]:
        """Get all non-empty encryption keys"""
        return [k for k in self.encryption_keys if not k.is_empty()]
