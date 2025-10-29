"""RT-4D Codeplug Binary Parser"""

import struct
from typing import Optional
from .models import (Channel, Contact, GroupList, Zone, Codeplug, ChannelMode,
                      PowerLevel, ScanMode, ContactType, EncryptionKey, EncryptionType,
                      AnalogModulation)
from .constants import *
from .tones import decode_subaudio_bytes


class CodeplugParser:
    """Parse RT-4D .4rdmf codeplug files"""

    def __init__(self, data: bytes):
        """Initialize parser with binary data"""
        if len(data) != TOTAL_SIZE:
            raise ValueError(f"Invalid file size: {len(data)} (expected {TOTAL_SIZE})")
        self.data = data

    def parse(self) -> Codeplug:
        """Parse the complete codeplug"""
        codeplug = Codeplug()

        # Extract raw sections
        codeplug.cfg_data = self.data[OFFSET_CFG:OFFSET_CFG + SIZE_CFG]
        codeplug.grouplist_data = self.data[OFFSET_GROUPLISTS:OFFSET_GROUPLISTS + SIZE_GROUPLISTS]
        codeplug.encrypt_data = self.data[OFFSET_ENCRYPT:OFFSET_ENCRYPT + SIZE_ENCRYPT]
        codeplug.fm_data = self.data[OFFSET_FM:OFFSET_FM + SIZE_FM]

        # Parse radio settings
        print("Parsing radio settings...")
        codeplug.settings = self.parse_settings(codeplug.cfg_data)

        # Parse channels
        print("Parsing channels...")
        for i in range(MAX_CHANNELS):
            channel = self.parse_channel(i)
            if channel and not channel.is_empty():
                codeplug.add_channel(channel)

        # Parse contacts
        print(f"Parsed {len(codeplug.channels)} channels")
        print("Parsing contacts...")
        for i in range(MAX_CONTACTS):
            contact = self.parse_contact(i)
            if contact and not contact.is_empty():
                codeplug.add_contact(contact)

        # Parse group lists
        print(f"Parsed {len(codeplug.contacts)} contacts")
        print("Parsing group lists...")
        for i in range(32):  # Max 32 group lists
            group_list = self.parse_group_list(i)
            if group_list and not group_list.is_empty():
                codeplug.add_group_list(group_list)

        # Parse zones
        print(f"Parsed {len(codeplug.group_lists)} group lists")
        print("Parsing zones...")
        for i in range(MAX_ZONES):
            zone = self.parse_zone(i)
            if zone and not zone.is_empty():
                codeplug.add_zone(zone)

        # Parse encryption keys
        print(f"Parsed {len(codeplug.zones)} zones")
        print("Parsing encryption keys...")
        for i in range(256):  # Max 256 encryption keys
            key = self.parse_encryption_key(i)
            if key and not key.is_empty():
                codeplug.add_encryption_key(key)

        print(f"Parsed {len(codeplug.encryption_keys)} encryption keys")
        return codeplug

    def parse_channel(self, index: int) -> Optional[Channel]:
        """Parse a single channel"""
        offset = OFFSET_CHANNELS + (index * CHANNEL_SIZE)
        ch_data = self.data[offset:offset + CHANNEL_SIZE]

        # Check if channel is empty (both bytes 0 and 1 are 0xFF means empty)
        if ch_data[0] == EMPTY_BYTE and ch_data[1] == EMPTY_BYTE:
            return None

        try:
            # Basic fields
            # Byte 1 indicates if channel is enabled (0x01 = enabled)
            enabled = ch_data[1] == 0x01
            mode_byte = ch_data[0x02]
            mode = ChannelMode.DIGITAL if mode_byte == CHANNEL_MODE_DIGITAL else ChannelMode.ANALOG

            # Frequencies (32-bit little-endian, freq × 100000)
            rx_freq_int = struct.unpack('<I', ch_data[0x06:0x0A])[0]
            tx_freq_int = struct.unpack('<I', ch_data[0x0A:0x0E])[0]
            rx_freq = rx_freq_int / FREQ_MULTIPLIER if rx_freq_int != 0xFFFFFFFF else 0.0
            tx_freq = tx_freq_int / FREQ_MULTIPLIER if tx_freq_int != 0xFFFFFFFF else 0.0

            # Power and scan
            power = PowerLevel.HIGH if ch_data[0x10] == POWER_HIGH else PowerLevel.LOW
            scan = ScanMode.ADD if ch_data[0x13] == SCAN_ADD else ScanMode.REMOVE

            # Channel name (16 bytes, GBK encoding)
            name_bytes = ch_data[0x20:0x30]
            # Remove padding (0xFF bytes)
            name_bytes = bytes([b for b in name_bytes if b != EMPTY_BYTE])
            try:
                name = name_bytes.decode('gbk', errors='ignore').strip()
            except:
                name = name_bytes.decode('latin-1', errors='ignore').strip()

            # Create channel object
            channel = Channel(
                index=index,
                name=name,
                rx_freq=rx_freq,
                tx_freq=tx_freq,
                mode=mode,
                power=power,
                scan=scan,
                enabled=enabled
            )

            # Digital/DMR specific fields
            if mode == ChannelMode.DIGITAL:
                # ID Select field (offset 0x00): 0=Radio ID, 1=Channel ID
                id_select_byte = ch_data[0x00]
                channel.use_radio_id = (id_select_byte == 0x00)

                channel.dmr_time_slot = ch_data[0x03]
                channel.dmr_color_code = ch_data[0x04]
                channel.dmr_mode = ch_data[0x05]
                channel.dmr_monitor = ch_data[0x0E]  # Promiscuous mode
                channel.tx_priority = ch_data[0x11]
                channel.tot = ch_data[0x14]
                channel.alarm = ch_data[0x15]
                channel.group_list_index = struct.unpack('<H', ch_data[0x16:0x18])[0]
                # Contact index: file stores 0-based slot numbers, convert to 1-based contact.index
                contact_slot = struct.unpack('<H', ch_data[0x18:0x1A])[0]
                if contact_slot == 0xFFFF:
                    channel.contact_index = 0  # No contact selected
                else:
                    channel.contact_index = contact_slot + 1  # Convert slot to index
                channel.encrypt_index = struct.unpack('<H', ch_data[0x1A:0x1C])[0]
                # DMR ID is BCD encoded at offset 0x1C-0x1F
                dmr_id_bytes = ch_data[0x1C:0x20]
                channel.dmr_id = self._parse_bcd(dmr_id_bytes)

            # Analog specific fields
            else:
                # Analog modulation: FM/AM/SSB (offset 0x00)
                modulation_byte = ch_data[0x00]
                if modulation_byte == 0x00:
                    channel.analog_modulation = AnalogModulation.FM
                elif modulation_byte == 0x01:
                    channel.analog_modulation = AnalogModulation.AM
                elif modulation_byte == 0x02:
                    channel.analog_modulation = AnalogModulation.SSB
                else:
                    channel.analog_modulation = AnalogModulation.FM  # Default to FM

                # RX CTCSS/DCS (offset 0x04-0x05)
                rx_tone_bytes = ch_data[0x04:0x06]
                channel.rx_ctcss = decode_subaudio_bytes(rx_tone_bytes)

                # TX CTCSS/DCS (offset 0x0E-0x0F)
                tx_tone_bytes = ch_data[0x0E:0x10]
                channel.tx_ctcss = decode_subaudio_bytes(tx_tone_bytes)

                # Bandwidth (offset 0x03)
                channel.bandwidth = ch_data[0x03]

                # TX Priority analog (offset 0x11)
                channel.tx_priority_analog = ch_data[0x11]

                # TOT and CT/DCS Select (offset 0x12)
                byte_0x12 = ch_data[0x12]
                channel.tot_analog = byte_0x12 & 0x1F  # Lower 5 bits
                channel.ctdcs_select = (byte_0x12 >> 5) & 0x07  # Upper 3 bits

                # Tail tone and Scrambler (offset 0x13)
                byte_0x13 = ch_data[0x13]
                channel.tail_tone = (byte_0x13 >> 4) & 0x0F  # Upper 4 bits
                channel.scramble = byte_0x13 & 0x0F  # Lower 4 bits

                # Encrypted sub-audio codes (offsets 0x14-0x1F)
                # Read as 32-bit little-endian integers
                channel.encrypted_code_1 = struct.unpack('<I', ch_data[0x14:0x18])[0]
                channel.encrypted_code_2 = struct.unpack('<I', ch_data[0x18:0x1C])[0]
                channel.encrypted_code_3 = struct.unpack('<I', ch_data[0x1C:0x20])[0]

            return channel

        except Exception as e:
            print(f"Warning: Error parsing channel {index}: {e}")
            return None

    def parse_contact(self, index: int) -> Optional[Contact]:
        """Parse a single DMR contact"""
        offset = OFFSET_CONTACTS + (index * CONTACT_SIZE)
        contact_data = self.data[offset:offset + CONTACT_SIZE]

        # Check if contact is empty
        if contact_data[0] == 0 or contact_data[0] == EMPTY_BYTE:
            return None

        try:
            # Contact type
            type_byte = contact_data[0x01]
            if type_byte == CONTACT_TYPE_PRIVATE:
                contact_type = ContactType.PRIVATE
            elif type_byte == CONTACT_TYPE_GROUP:
                contact_type = ContactType.GROUP
            elif type_byte == CONTACT_TYPE_ALL_CALL:
                contact_type = ContactType.ALL_CALL
            else:
                contact_type = ContactType.GROUP

            # Contact name (16 bytes at offset 0x10)
            name_bytes = contact_data[0x10:0x20]
            name_bytes = bytes([b for b in name_bytes if b != EMPTY_BYTE])
            try:
                name = name_bytes.decode('gbk', errors='ignore').strip()
            except:
                name = name_bytes.decode('latin-1', errors='ignore').strip()

            # DMR ID (BCD encoded, 4 bytes at offset 0x02)
            dmr_id_bytes = contact_data[0x02:0x06]
            dmr_id = self._parse_bcd(dmr_id_bytes)

            # Contact index is stored in byte 0 (1-based)
            contact_index = contact_data[0x00]

            return Contact(
                index=contact_index,
                name=name,
                contact_type=contact_type,
                dmr_id=dmr_id
            )

        except Exception as e:
            print(f"Warning: Error parsing contact {index}: {e}")
            return None

    def parse_group_list(self, index: int) -> Optional[GroupList]:
        """Parse a single group list"""
        # Group list size is 272 bytes (0x110)
        GROUP_LIST_SIZE = 272
        offset = OFFSET_GROUPLISTS + (index * GROUP_LIST_SIZE)
        gl_data = self.data[offset:offset + GROUP_LIST_SIZE]

        # Check if group list is empty (byte 1 should be 0x01 for enabled)
        if gl_data[1] != 0x01:
            return None

        try:
            # Group list name (14 bytes at offset 0x02)
            name_bytes = gl_data[0x02:0x10]
            name_bytes = bytes([b for b in name_bytes if b != EMPTY_BYTE])
            try:
                name = name_bytes.decode('gbk', errors='ignore').strip()
            except:
                name = name_bytes.decode('latin-1', errors='ignore').strip()

            if not name:
                return None

            # Parse contact indices (128 × 2 bytes starting at offset 0x10)
            contacts = []
            for i in range(128):
                contact_offset = 0x10 + (i * 2)
                contact_index = struct.unpack('<H', gl_data[contact_offset:contact_offset + 2])[0]
                # 0xFFFF means empty slot
                if contact_index != 0xFFFF and contact_index < MAX_CONTACTS:
                    contacts.append(contact_index)

            return GroupList(
                index=index + 1,  # Convert 0-based slot to 1-based index
                name=name,
                contacts=contacts
            )

        except Exception as e:
            print(f"Warning: Error parsing group list {index}: {e}")
            return None

    def parse_zone(self, index: int) -> Optional[Zone]:
        """Parse a single zone"""
        offset = OFFSET_ZONES + (index * ZONE_SIZE)
        zone_data = self.data[offset:offset + ZONE_SIZE]

        # Check if zone is empty
        if zone_data[0] == EMPTY_BYTE:
            return None

        try:
            # Zone name (16 bytes at offset 0x04)
            name_bytes = zone_data[0x04:0x14]
            name_bytes = bytes([b for b in name_bytes if b != EMPTY_BYTE])
            try:
                name = name_bytes.decode('gbk', errors='ignore').strip()
            except:
                name = name_bytes.decode('latin-1', errors='ignore').strip()

            if not name:
                return None

            # Parse channel list
            # First 2 bytes contain channel count
            channel_count = zone_data[0] | (zone_data[1] << 8)
            channels = []

            # Channel list starts at offset 0x14 (20)
            # Each channel is a 16-bit little-endian integer
            for i in range(min(channel_count, 250)):  # Max 250 channels per zone
                offset = 0x14 + (i * 2)
                if offset + 1 < len(zone_data):
                    channel_idx = zone_data[offset] | (zone_data[offset + 1] << 8)
                    if channel_idx != 0xFFFF and channel_idx < 1024:  # Valid channel index
                        channels.append(channel_idx)

            return Zone(
                index=index,
                name=name,
                channels=channels
            )

        except Exception as e:
            print(f"Warning: Error parsing zone {index}: {e}")
            return None

    def parse_encryption_key(self, index: int) -> Optional[EncryptionKey]:
        """Parse a single encryption key"""
        offset = OFFSET_ENCRYPT + (index * 48)  # Each key is 48 bytes
        key_data = self.data[offset:offset + 48]

        # Check if key is empty (first byte is 0xFF or 0x00)
        if key_data[0] == EMPTY_BYTE or key_data[0] == 0x00:
            return None

        try:
            # Key type (offset 1)
            enc_type_val = key_data[1]
            if enc_type_val > 2:  # Only 0=ARC, 1=AES-128, 2=AES-256
                return None
            enc_type = EncryptionType(enc_type_val)

            # Key alias (offset 2-15, 14 bytes, GBK encoded, 0xFF padded)
            alias_bytes = key_data[2:16]
            alias_bytes = bytes([b for b in alias_bytes if b != EMPTY_BYTE])
            try:
                alias = alias_bytes.decode('gbk', errors='ignore').strip()
            except:
                alias = alias_bytes.decode('latin-1', errors='ignore').strip()

            if not alias:
                return None

            # Key value (offset 16-47, 32 bytes, nibble-packed)
            # Convert nibble-packed bytes back to hex string
            value_bytes = key_data[16:48]
            value = ""
            for byte_val in value_bytes:
                high_nibble = (byte_val >> 4) & 0x0F
                low_nibble = byte_val & 0x0F
                # Stop at 0xFF padding
                if high_nibble == 0xF and low_nibble == 0xF:
                    break
                value += f"{high_nibble:X}{low_nibble:X}"

            # Trim to expected length based on type
            if enc_type == EncryptionType.ARC:
                value = value[:10]
            elif enc_type == EncryptionType.AES_128:
                value = value[:32]
            elif enc_type == EncryptionType.AES_256:
                value = value[:64]

            return EncryptionKey(
                index=index,
                alias=alias,
                enc_type=enc_type,
                value=value
            )

        except Exception as e:
            print(f"Warning: Error parsing encryption key {index}: {e}")
            return None

    def parse_settings(self, cfg_data: bytes) -> 'RadioSettings':
        """Parse radio settings from CFG buffer"""
        from .models import RadioSettings

        def decode_gbk(data: bytes) -> str:
            data = bytes([b for b in data if b != 0xFF])
            try:
                return data.decode('gbk', errors='ignore').strip()
            except:
                return data.decode('latin-1', errors='ignore').strip()

        settings = RadioSettings()
        settings.startup_password = decode_gbk(cfg_data[28:44])
        settings.startup_message = decode_gbk(cfg_data[44:76])
        settings.radio_name = decode_gbk(cfg_data[76:92])
        settings.radio_id = self._parse_bcd(cfg_data[384:388])

        # Audio/UI
        settings.voice_prompt = cfg_data[92]
        settings.key_beep = cfg_data[93]
        settings.key_lock = cfg_data[94]
        settings.lock_timer = cfg_data[95]

        # Display
        settings.led_on_off = cfg_data[96]
        settings.backlight_brightness = cfg_data[97]
        settings.led_timer = cfg_data[98]
        settings.menu_timer = cfg_data[101]
        settings.display_mode_a = cfg_data[133]
        settings.display_mode_b = cfg_data[138]

        # Power
        settings.power_save_mode = cfg_data[99]
        settings.power_save_start = cfg_data[100]
        settings.apo_enabled = cfg_data[105] == 1

        # Operation
        settings.dual_watch = cfg_data[102]
        settings.talkaround = cfg_data[103]
        settings.alarm_type = cfg_data[104]
        settings.tx_priority_global = cfg_data[126]
        settings.main_ptt = cfg_data[127]
        settings.vfo_step = cfg_data[128]
        settings.main_band = cfg_data[131]
        settings.work_mode_a = cfg_data[132]
        settings.zone_a = cfg_data[134]
        settings.channel_a = cfg_data[135] | (cfg_data[136] << 8)
        settings.work_mode_b = cfg_data[137]
        settings.zone_b = cfg_data[139]
        settings.channel_b = cfg_data[140] | (cfg_data[141] << 8)

        # Clocks/Timers (3 bytes each: mode, hour, minute)
        settings.clock_1_mode = cfg_data[110]
        settings.clock_1_hour = cfg_data[111]
        settings.clock_1_minute = cfg_data[112]
        settings.clock_2_mode = cfg_data[113]
        settings.clock_2_hour = cfg_data[114]
        settings.clock_2_minute = cfg_data[115]
        settings.clock_3_mode = cfg_data[116]
        settings.clock_3_hour = cfg_data[117]
        settings.clock_3_minute = cfg_data[118]
        settings.clock_4_mode = cfg_data[119]
        settings.clock_4_hour = cfg_data[120]
        settings.clock_4_minute = cfg_data[121]

        # Startup/Boot settings
        settings.startup_picture_enable = cfg_data[16]
        settings.tx_protection = cfg_data[17]
        settings.startup_beep_enable = cfg_data[19]
        settings.startup_label_enable = cfg_data[20]
        settings.startup_display_line = cfg_data[23] | (cfg_data[24] << 8)
        settings.startup_display_column = cfg_data[25] | (cfg_data[26] << 8)
        settings.password_enable = cfg_data[27]

        # Radio clock/time (32-bit value: total seconds since midnight)
        settings.radio_time_seconds = (cfg_data[106] |
                                       (cfg_data[107] << 8) |
                                       (cfg_data[108] << 16) |
                                       (cfg_data[109] << 24))

        # Frequency lock ranges (4 ranges, 5 bytes each)
        settings.freq_lock_1_mode = cfg_data[142]
        settings.freq_lock_1_start = cfg_data[143] | (cfg_data[144] << 8)
        settings.freq_lock_1_end = cfg_data[145] | (cfg_data[146] << 8)
        settings.freq_lock_2_mode = cfg_data[147]
        settings.freq_lock_2_start = cfg_data[148] | (cfg_data[149] << 8)
        settings.freq_lock_2_end = cfg_data[150] | (cfg_data[151] << 8)
        settings.freq_lock_3_mode = cfg_data[152]
        settings.freq_lock_3_start = cfg_data[153] | (cfg_data[154] << 8)
        settings.freq_lock_3_end = cfg_data[155] | (cfg_data[156] << 8)
        settings.freq_lock_4_mode = cfg_data[157]
        settings.freq_lock_4_start = cfg_data[158] | (cfg_data[159] << 8)
        settings.freq_lock_4_end = cfg_data[160] | (cfg_data[161] << 8)

        # Scan settings
        settings.scan_direction = cfg_data[162]
        settings.scan_mode = cfg_data[163]
        settings.scan_return = cfg_data[164]
        settings.scan_dwell = cfg_data[165]

        # Function keys
        settings.key_fs1_short = cfg_data[170]
        settings.key_fs1_long = cfg_data[171]
        settings.key_fs2_short = cfg_data[172]
        settings.key_fs2_long = cfg_data[173]
        settings.key_alarm_short = cfg_data[174]
        settings.key_alarm_long = cfg_data[175]
        settings.key_0 = cfg_data[176]
        settings.key_1 = cfg_data[177]
        settings.key_2 = cfg_data[178]
        settings.key_3 = cfg_data[179]
        settings.key_4 = cfg_data[180]
        settings.key_5 = cfg_data[181]
        settings.key_6 = cfg_data[182]
        settings.key_7 = cfg_data[183]
        settings.key_8 = cfg_data[184]
        settings.key_9 = cfg_data[185]

        # Audio Settings
        settings.tone_frequency = cfg_data[256] | (cfg_data[257] << 8)
        settings.squelch_level = cfg_data[258]
        settings.tx_mic_gain = cfg_data[261]
        settings.rx_speaker_volume = cfg_data[262]
        settings.tx_start_beep = cfg_data[267]
        settings.roger_beep = cfg_data[268]
        settings.call_mic_gain = cfg_data[391]
        settings.call_speaker_volume = cfg_data[392]
        settings.call_start_beep = cfg_data[397]
        settings.call_end_beep = cfg_data[398]
        settings.digital_squelch = cfg_data[403]

        # Display Settings (additional)
        settings.lcd_contrast = cfg_data[233]
        settings.display_lines = cfg_data[234]
        settings.dual_display_mode = cfg_data[235]

        # DMR Enhancements
        settings.remote_control = cfg_data[388]
        settings.group_call_hang_time = cfg_data[389] | (cfg_data[390] << 8)
        settings.private_call_hang_time = cfg_data[395] | (cfg_data[396] << 8)
        settings.group_id_display = cfg_data[400]
        settings.call_timing_display = cfg_data[404]

        # Advanced Features
        settings.noaa_channel = cfg_data[272]
        settings.spectrum_scan_mode = cfg_data[273]
        settings.detection_range = cfg_data[274] | (cfg_data[275] << 8)
        settings.relay_delay = cfg_data[276]
        settings.glitch_filter = cfg_data[842]

        # DTMF System
        settings.dtmf_send_delay = cfg_data[512]
        settings.dtmf_send_duration = cfg_data[513]
        settings.dtmf_send_interval = cfg_data[514]
        settings.dtmf_send_mode = cfg_data[515]
        settings.dtmf_send_select = cfg_data[516]
        settings.dtmf_display_enable = cfg_data[517]
        settings.dtmf_gain = cfg_data[518]
        settings.dtmf_decode_threshold = cfg_data[519]
        settings.dtmf_remote_control = cfg_data[520]
        settings.dtmf_remote_cal_time = cfg_data[521]
        # Parse 20 DTMF codes (each 16 bytes starting at offset 522)
        settings.dtmf_codes = []
        for i in range(20):
            offset = 522 + (i * 16)
            code_bytes = cfg_data[offset:offset+16]
            code = decode_gbk(code_bytes)
            settings.dtmf_codes.append(code)

        return settings

    @staticmethod
    def _parse_bcd(bcd_bytes: bytes) -> int:
        """Convert BCD encoded bytes to integer"""
        # Check if all bytes are 0xFF (empty/invalid)
        if all(b == 0xFF for b in bcd_bytes):
            return 0

        result = 0
        for byte_val in reversed(bcd_bytes):
            high_nibble = (byte_val >> 4) & 0x0F
            low_nibble = byte_val & 0x0F

            # Invalid BCD if nibbles > 9 (unless 0xF which means empty)
            if high_nibble > 9 and high_nibble != 0xF:
                return 0
            if low_nibble > 9 and low_nibble != 0xF:
                return 0

            # Treat 0xF nibbles as 0
            if high_nibble == 0xF:
                high_nibble = 0
            if low_nibble == 0xF:
                low_nibble = 0

            result = result * 100 + high_nibble * 10 + low_nibble
        return result

    @classmethod
    def from_file(cls, filename: str) -> 'CodeplugParser':
        """Create parser from .4rdmf file"""
        with open(filename, 'rb') as f:
            data = f.read()
        return cls(data)
