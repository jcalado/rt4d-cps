"""RT-4D Codeplug Binary Parser"""

import struct
from typing import Optional
from .models import (Channel, Contact, GroupList, Zone, Codeplug, ChannelMode,
                      PowerLevel, ScanMode, ContactType, EncryptionKey, EncryptionType,
                      AnalogModulation, RadioSettings)
from .constants import *
from .tones import decode_subaudio_bytes


class CodeplugParser:
    """Parse RT-4D .4rdmf codeplug files"""

    def __init__(self, data: bytes):
        """Initialize parser with binary data"""
        if len(data) != TOTAL_SIZE:
            raise ValueError(f"Invalid file size: {len(data)} (expected {TOTAL_SIZE})")
        self.data = data
        self._beta41_layout = False

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
        if codeplug.settings:
            self._beta41_layout = bool(codeplug.settings.beta41)
            print(f"Detected beta41+ layout: {self._beta41_layout}")

        # Parse channels
        print("Parsing channels...")
        for i in range(MAX_CHANNELS):
            if self._beta41_layout:
                channel = self.parse_channel_new(i)
            else:
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
        if self._beta41_layout:
            max_lists = MAX_GROUP_LISTS_NEW
            group_list_size = GROUP_LIST_SIZE_NEW
            max_group_list_ids = MAX_GROUP_LIST_IDS_NEW
        else:
            max_lists = MAX_GROUP_LISTS
            group_list_size = GROUP_LIST_SIZE
            max_group_list_ids = MAX_GROUP_LIST_IDS
        for i in range(max_lists):
            group_list = self.parse_group_list(i, max_lists, group_list_size, max_group_list_ids)
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

        # Resolve index-based references to UUIDs
        print("Resolving UUID references...")
        self._resolve_uuid_references(codeplug)

        return codeplug

    def _resolve_uuid_references(self, codeplug: Codeplug):
        """Convert index-based references to UUIDs after parsing all entities"""
        # Build index→UUID maps
        contact_uuid_map = {c.index: c.uuid for c in codeplug.contacts}
        group_list_uuid_map = {gl.index: gl.uuid for gl in codeplug.group_lists}
        encrypt_uuid_map = {ek.index + 1: ek.uuid for ek in codeplug.encryption_keys}
        # Channels use position (1-based) for mapping
        channel_uuid_map = {ch.position: ch.uuid for ch in codeplug.channels}

        # Resolve channel references (contact, group_list, encrypt)
        for channel in codeplug.channels:
            # _parsed_contact_index, _parsed_group_list_index, _parsed_encrypt_index
            # were stored during parsing
            if hasattr(channel, '_parsed_contact_index') and channel._parsed_contact_index:
                channel.contact_uuid = contact_uuid_map.get(channel._parsed_contact_index, "")
            if hasattr(channel, '_parsed_group_list_index') and channel._parsed_group_list_index:
                channel.group_list_uuid = group_list_uuid_map.get(channel._parsed_group_list_index, "")
            if hasattr(channel, '_parsed_encrypt_index') and channel._parsed_encrypt_index:
                channel.encrypt_uuid = encrypt_uuid_map.get(channel._parsed_encrypt_index, "")
            # Clean up temporary attributes
            for attr in ['_parsed_contact_index', '_parsed_group_list_index', '_parsed_encrypt_index']:
                if hasattr(channel, attr):
                    delattr(channel, attr)

        # Resolve zone channel references
        # Binary stores 0-based slot indices, but channels use 1-based positions
        for zone in codeplug.zones:
            if hasattr(zone, '_parsed_channel_indices'):
                zone.channels = [channel_uuid_map.get(idx + 1, "") for idx in zone._parsed_channel_indices
                                if (idx + 1) in channel_uuid_map]
                delattr(zone, '_parsed_channel_indices')

        # Resolve group list contact references
        for gl in codeplug.group_lists:
            if hasattr(gl, '_parsed_contact_indices'):
                gl.contacts = [contact_uuid_map.get(idx, "") for idx in gl._parsed_contact_indices
                              if idx in contact_uuid_map]
                delattr(gl, '_parsed_contact_indices')

    def parse_channel(self, index: int) -> Optional[Channel]:
        """Parse a single channel"""
        offset = OFFSET_CHANNELS + (index * CHANNEL_SIZE)
        ch_data = self.data[offset:offset + CHANNEL_SIZE]

        # Check if channel is empty
        if ch_data[2] >= 2:
            return None

        try:
            # Basic fields
            mode_byte = ch_data[0x02]
            mode = ChannelMode.DIGITAL if mode_byte == CHANNEL_MODE_DIGITAL else ChannelMode.ANALOG

            # Frequencies (32-bit little-endian, stored as 10 Hz units)
            rx_freq_int = struct.unpack('<I', ch_data[0x06:0x0A])[0]
            tx_freq_int = struct.unpack('<I', ch_data[0x0A:0x0E])[0]
            rx_freq = 0 if rx_freq_int == 0xFFFFFFFF else rx_freq_int
            tx_freq = 0 if tx_freq_int == 0xFFFFFFFF else tx_freq_int

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
                position=index + 1,  # Convert 0-based slot to 1-based position
                name=name,
                rx_freq=rx_freq,
                tx_freq=tx_freq,
                mode=mode,
                power=power,
                scan=scan,
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
                channel.dmr_busy_lock = ch_data[0x11]
                channel.tot = ch_data[0x14]
                channel.alarm = ch_data[0x15]
                # Store parsed indices temporarily for UUID resolution later
                channel._parsed_group_list_index = struct.unpack('<H', ch_data[0x16:0x18])[0]
                # Contact index: file stores 0-based slot numbers, convert to 1-based contact.index
                contact_slot = struct.unpack('<H', ch_data[0x18:0x1A])[0]
                if contact_slot == 0xFFFF:
                    channel._parsed_contact_index = 0  # No contact selected
                else:
                    channel._parsed_contact_index = contact_slot + 1  # Convert slot to index
                channel._parsed_encrypt_index = struct.unpack('<H', ch_data[0x1A:0x1C])[0]
                # DMR ID is BCD encoded at offset 0x1C-0x1F
                dmr_id_bytes = ch_data[0x1C:0x20]
                channel.dmr_id = self._parse_bcd(dmr_id_bytes)

            # Analog specific fields
            else:
                # Byte 0x04 layout:
                # bit 0: reserved
                # bits 1-3: DcsEncrypt (ctdcs_select)
                # bits 4-5: Modulation (FM/AM/SSB)
                # bit 6: bIsNarrow (bandwidth)
                byte_0x04 = ch_data[0x04]

                # Analog modulation: FM/AM/SSB (offset 0x04, bits 4-5)
                modulation_bits = (byte_0x04 >> 4) & 0x03
                if modulation_bits == 0x00:
                    channel.analog_modulation = AnalogModulation.FM
                elif modulation_bits == 0x01:
                    channel.analog_modulation = AnalogModulation.AM
                elif modulation_bits == 0x02:
                    channel.analog_modulation = AnalogModulation.SSB
                else:
                    channel.analog_modulation = AnalogModulation.FM  # Default to FM

                # Bandwidth (offset 0x04, bit 6)
                channel.bandwidth = (byte_0x04 >> 6) & 0x01

                # CT/DCS Select (offset 0x04, bits 1-3)
                channel.ctdcs_select = (byte_0x04 >> 1) & 0x07

                # RX CTCSS/DCS (offset 0x05-0x06)
                rx_tone_bytes = ch_data[0x05:0x07]
                channel.rx_ctcss = decode_subaudio_bytes(rx_tone_bytes)

                # TX CTCSS/DCS (offset 0x0F-0x10)
                tx_tone_bytes = ch_data[0x0F:0x11]
                channel.tx_ctcss = decode_subaudio_bytes(tx_tone_bytes)

                # Analog busy lock (offset 0x11)
                channel.ana_busy_lock = ch_data[0x11]

                # TOT (offset 0x12)
                byte_0x12 = ch_data[0x12]
                channel.tot_analog = byte_0x12 & 0x1F  # Lower 5 bits

                # Tail tone and Scrambler (offset 0x13)
                byte_0x13 = ch_data[0x13]
                channel.tail_tone = (byte_0x13 >> 4) & 0x0F  # Upper 4 bits
                channel.scramble = byte_0x13 & 0x0F  # Lower 4 bits

                # Encrypted sub-audio codes (offsets 0x14-0x1F)
                # Read as 32-bit little-endian integers
                channel.mute_code = struct.unpack('<I', ch_data[0x14:0x18])[0]

            return channel

        except Exception as e:
            print(f"Warning: Error parsing channel {index}: {e}")
            return None


    def parse_channel_new(self, index: int) -> Optional[Channel]:
        """Parse a single channel using the beta41+ layout"""
        offset = OFFSET_CHANNELS + (index * CHANNEL_SIZE)
        ch_data = self.data[offset:offset + CHANNEL_SIZE]

        try:
            # Detect empty slot (all 0xFF or no freqs/name)
            if all(b == EMPTY_BYTE for b in ch_data):
                return None

            rx_freq_int = struct.unpack('<I', ch_data[0x05:0x09])[0]
            tx_freq_int = struct.unpack('<I', ch_data[0x09:0x0D])[0]
            name_bytes = bytes([b for b in ch_data[0x20:0x30] if b != EMPTY_BYTE])
            if not name_bytes and rx_freq_int in (0, 0xFFFFFFFF) and tx_freq_int in (0, 0xFFFFFFFF):
                return None

            rx_freq = 0 if rx_freq_int in (0, 0xFFFFFFFF) else rx_freq_int
            tx_freq = 0 if tx_freq_int in (0, 0xFFFFFFFF) else tx_freq_int

            try:
                name = name_bytes.decode('gbk', errors='ignore').strip()
            except Exception:
                name = name_bytes.decode('latin-1', errors='ignore').strip()

            mode = ChannelMode.ANALOG if (ch_data[0x00] & 0x40) else ChannelMode.DIGITAL
            power = PowerLevel.HIGH if (ch_data[0x02] & 0x40) else PowerLevel.LOW
            scan = ScanMode.REMOVE if (ch_data[0x03] & 0x80) else ScanMode.ADD

            channel = Channel(
                position=index + 1,  # Convert 0-based slot to 1-based position
                name=name,
                rx_freq=rx_freq,
                tx_freq=tx_freq,
                mode=mode,
                power=power,
                scan=scan,
            )

            channel.dmr_monitor = ch_data[0x00] & 0x01
            channel.dmr_time_slot = (ch_data[0x00] >> 1) & 0x01
            channel.dmr_mode = (ch_data[0x00] >> 2) & 0x01
            # Bit 3: 0=use radio ID, 1=use channel ID (inverted from old layout)
            channel.use_radio_id = not bool((ch_data[0x00] >> 3) & 0x01)
            channel.rx_tx = (ch_data[0x00] >> 4) & 0x03  # RX/TX permission (bits 4-5)
            channel.scramble = ch_data[0x01] & 0x0F
            channel.dmr_color_code = (ch_data[0x01] >> 4) & 0x0F
            channel.tot = ch_data[0x02] & 0x3F
            channel.tail_tone = ch_data[0x03] & 0x07
            channel.ana_busy_lock = (ch_data[0x03] >> 3) & 0x03
            channel.dmr_busy_lock = (ch_data[0x03] >> 5) & 0x03
            channel.ctdcs_select = (ch_data[0x04] >> 1) & 0x07

            modulation_bits = (ch_data[0x04] >> 4) & 0x03
            try:
                channel.analog_modulation = AnalogModulation(modulation_bits)
            except ValueError:
                channel.analog_modulation = AnalogModulation.FM

            channel.bandwidth = (ch_data[0x04] >> 6) & 0x01

            # Sub-audio
            channel.rx_ctcss = decode_subaudio_bytes(ch_data[0x0D:0x0F])
            channel.tx_ctcss = decode_subaudio_bytes(ch_data[0x0F:0x11])

            # Store parsed indices temporarily for UUID resolution later
            contact_slot = struct.unpack('<H', ch_data[0x11:0x13])[0]
            if contact_slot == 0xFFFF:
                channel._parsed_contact_index = 0
            else:
                channel._parsed_contact_index = contact_slot + 1

            channel._parsed_group_list_index = ch_data[0x13]
            channel._parsed_encrypt_index = struct.unpack('<H', ch_data[0x14:0x16])[0]
            channel.dmr_id = self._parse_bcd(ch_data[0x16:0x1A])
            channel.mute_code = struct.unpack('<I', ch_data[0x1A:0x1E])[0]

            return channel

        except Exception as e:
            print(f"Warning: Error parsing channel {index}: {e}")
            return None

    def parse_contact(self, index: int) -> Optional[Contact]:
        """Parse a single DMR contact"""
        offset = OFFSET_CONTACTS + (index * CONTACT_SIZE)
        contact_data = self.data[offset:offset + CONTACT_SIZE]

        # Check if contact is empty
        if contact_data[1] > 2:
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

            return Contact(
                index=index + 1,  # Contacts use 1-based indexing
                name=name,
                contact_type=contact_type,
                dmr_id=dmr_id
            )

        except Exception as e:
            print(f"Warning: Error parsing contact {index}: {e}")
            return None

    def parse_group_list(self, index: int, maxlist: int, datasize: int, listsize: int) -> Optional[GroupList]:
        """Parse a single group list"""
        offset = OFFSET_GROUPLISTS + (index * datasize)
        gl_data = self.data[offset:offset + datasize]

        # Check if group list is empty (byte 1 should be 0x01 for enabled)
        if gl_data[1] != 0x01:
            return None

        try:
            # Group list name (14 bytes at offset 0x02)
            name_bytes = gl_data[0x02:0x10]
            name_bytes = bytes([b for b in name_bytes if b != EMPTY_BYTE])
            try:
                name = name_bytes.decode('gbk', errors='ignore').strip()
            except Exception:
                name = name_bytes.decode('latin-1', errors='ignore').strip()

            if not name:
                return None

            # Parse contact indices (128 × 2 bytes starting at offset 0x10)
            # Store as temporary attribute for UUID resolution later
            parsed_contact_indices = []
            for i in range(listsize):
                contact_offset = 0x10 + (i * 2)
                contact_index = struct.unpack('<H', gl_data[contact_offset:contact_offset + 2])[0]
                # 0xFFFF means empty slot
                if contact_index != 0xFFFF and contact_index < MAX_CONTACTS:
                    parsed_contact_indices.append(contact_index + 1)

            gl = GroupList(
                index=index + 1,  # Convert 0-based slot to 1-based index
                name=name,
            )
            gl._parsed_contact_indices = parsed_contact_indices
            return gl

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
            parsed_channel_indices = []

            # Channel list starts at offset 0x14 (20)
            # Each channel is a 16-bit little-endian integer
            for i in range(min(channel_count, 200)):  # Max 200 channels per zone
                offset = 0x14 + (i * 2)
                if offset + 1 < len(zone_data):
                    channel_idx = zone_data[offset] | (zone_data[offset + 1] << 8)
                    if channel_idx != 0xFFFF and channel_idx < 1024:  # Valid channel index
                        parsed_channel_indices.append(channel_idx)

            zone = Zone(
                index=index,
                name=name,
            )
            zone._parsed_channel_indices = parsed_channel_indices
            return zone

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

        # Scan settings (0x0A2-0x0A5, 0x34A-0x353)
        settings.scan_direction = cfg_data[0x0A2]
        settings.scan_mode = cfg_data[0x0A3]  # Unused in REFW
        settings.scan_return = cfg_data[0x0A4]
        settings.scan_dwell = cfg_data[0x0A5]
        settings.ch_direction = cfg_data[0x34A]
        settings.sms_prompt = cfg_data[0x34B]
        settings.scan_lower = (cfg_data[0x34C] | (cfg_data[0x34D] << 8) |
                               (cfg_data[0x34E] << 16) | (cfg_data[0x34F] << 24))
        settings.scan_upper = (cfg_data[0x350] | (cfg_data[0x351] << 8) |
                               (cfg_data[0x352] << 16) | (cfg_data[0x353] << 24))

        # Function keys
        settings.key_fs1_short = cfg_data[170]
        settings.key_fs1_long = cfg_data[171]
        settings.key_fs2_short = cfg_data[172]
        settings.key_fs2_long = cfg_data[173]
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

        # Audio Settings (0x100-0x11A)
        settings.tone_frequency = cfg_data[0x100] | (cfg_data[0x101] << 8)
        settings.squelch_level = cfg_data[0x102]
        settings.tx_mic_gain = cfg_data[0x105]
        settings.rx_speaker_volume = cfg_data[0x106]
        settings.tx_start_beep = cfg_data[0x10B]
        settings.roger_beep = cfg_data[0x10C]
        settings.analog_vox = cfg_data[0x10D]
        settings.vox_threshold = cfg_data[0x10E]
        settings.vox_delay = cfg_data[0x10F]
        settings.short_tail = cfg_data[0x117]
        settings.tone_timer = cfg_data[0x118]
        settings.single_tone_timer = cfg_data[0x119] | (cfg_data[0x11A] << 8)

        # Display Settings (additional)
        settings.rssi_refresh = cfg_data[0x0A8] | (cfg_data[0x0A9] << 8)
        settings.slaver_ptt = cfg_data[0x0E8]
        settings.lcd_contrast = cfg_data[0x0E9]
        settings.display_lines = cfg_data[0x0EA]
        settings.dual_display_mode = cfg_data[0x0EB]

        # DMR Audio Settings (0x185-0x193)
        settings.tx_denoise = cfg_data[0x185]
        settings.rx_denoise = cfg_data[0x186]
        settings.call_mic_gain = cfg_data[0x187]
        settings.call_speaker_volume = cfg_data[0x188]
        settings.call_start_beep = cfg_data[0x18D]
        settings.call_end_beep = cfg_data[0x18E]
        settings.digital_squelch = cfg_data[0x193]

        # DMR Enhancements (0x184, 0x18F-0x194)
        settings.remote_control = cfg_data[0x184]
        settings.group_call_hang_time = cfg_data[0x18F] | (cfg_data[0x190] << 8)
        settings.private_call_hang_time = cfg_data[0x191] | (cfg_data[0x192] << 8)
        settings.call_group_display = cfg_data[0x194]

        # DMR SMS Fields (0x195-0x19A)
        settings.dmr_send_dtmf = cfg_data[0x195]
        settings.sms_format = cfg_data[0x196]
        settings.sms_font = cfg_data[0x197]
        settings.caller_keep = cfg_data[0x198]
        settings.call_log_wpos = cfg_data[0x199] | (cfg_data[0x19A] << 8)

        # Advanced Features
        settings.detection_range = cfg_data[0x110]
        settings.relay_delay = cfg_data[0x111] | (cfg_data[0x112] << 8)
        settings.noaa_channel = cfg_data[0x113] # Unused
        settings.glitch_filter = cfg_data[0x114]
        settings.spectrum_step = cfg_data[0x115] | (cfg_data[0x116] << 8)

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
        # Structure: String[14] + unused byte + Length byte
        settings.dtmf_codes = []
        for i in range(20):
            offset = 522 + (i * 16)
            length = cfg_data[offset + 15]  # Length field at byte 15
            if length == 0 or length == 0xFF:
                # Empty DTMF code
                code = ""
            else:
                # Read only 'length' bytes from String field (max 14)
                actual_len = min(length, 14)
                code_bytes = cfg_data[offset:offset + actual_len]
                code = bytes(b for b in code_bytes if b != 0xFF and b != 0x00).decode('ascii', errors='ignore')
            settings.dtmf_codes.append(code)

        # DT Custom Firmware Settings (offset 0x380 = 896)
        settings.scan_speed_analog = cfg_data[0x380]
        settings.tx_backlight = cfg_data[0x381]
        settings.green_key_long = cfg_data[0x382]
        settings.voltage_display = cfg_data[0x383]
        settings.live_sub_tone = cfg_data[0x384]
        settings.spectrum_threshold = cfg_data[0x385]
        settings.sub_tone_ptt = cfg_data[0x386]
        settings.tot_warning = cfg_data[0x387]
        settings.scan_end = cfg_data[0x388]
        settings.scan_continue = cfg_data[0x389]
        settings.dt_scan_return = cfg_data[0x392]
        # VFO offsets are 32-bit little-endian integers (stored unsigned, but can be negative)
        # Stored in units of 10 Hz, so multiply by 10 to get Hz
        # Convert from unsigned to signed using two's complement
        vfo_a_offset = (cfg_data[0x393] |
                        (cfg_data[0x394] << 8) |
                        (cfg_data[0x395] << 16) |
                        (cfg_data[0x396] << 24))
        if vfo_a_offset & 0x80000000:
            vfo_a_offset = -(0x100000000 - vfo_a_offset)
        settings.vfo_a_offset = vfo_a_offset * 10  # Convert to Hz

        vfo_b_offset = (cfg_data[0x397] |
                        (cfg_data[0x398] << 8) |
                        (cfg_data[0x399] << 16) |
                        (cfg_data[0x39A] << 24))
        if vfo_b_offset & 0x80000000:
            vfo_b_offset = -(0x100000000 - vfo_b_offset)
        settings.vfo_b_offset = vfo_b_offset * 10  # Convert to Hz
        settings.callsign_lookup = cfg_data[0x39B]
        settings.dmr_scan_speed = cfg_data[0x39C]
        settings.ptt_lock = cfg_data[0x39D]
        settings.zone_channel_display = cfg_data[0x39E]
        settings.dmr_gid_name = cfg_data[0x39F]
        settings.tx_alias = cfg_data[0x3A0]
        settings.beta41 = cfg_data[4092:4096] == BETA41_MAGIC

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
