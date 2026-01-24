"""RT-4D Codeplug Binary Serializer"""

import struct
from .models import (Codeplug, Channel, Contact, Zone, ChannelMode, PowerLevel,
                      ScanMode, ContactType, EncryptionKey, EncryptionType,
                      AnalogModulation)
from .constants import *
from .tones import encode_subaudio_bytes


class CodeplugSerializer:
    """Serialize Codeplug objects to binary .4rdmf format"""

    @staticmethod
    def serialize(codeplug: Codeplug) -> bytes:
        """Serialize complete codeplug to binary data"""
        # Initialize with empty data (all 0xFF)
        data = bytearray(b'\xff' * TOTAL_SIZE)

        # Validate channel positions
        errors = codeplug.validate_channel_positions()
        if errors:
            raise ValueError(f"Channel position errors: {'; '.join(errors)}")

        # Auto-assign positions for any channels with position=0
        used_positions = codeplug.get_used_positions()
        next_pos = 1
        for ch in codeplug.channels:
            if ch.position == 0 and not ch.is_empty():
                while next_pos in used_positions:
                    next_pos += 1
                if next_pos > 1024:
                    raise ValueError("No available channel positions")
                ch.position = next_pos
                used_positions.add(next_pos)
                next_pos += 1

        # Recalculate indices for contacts, group lists, zones, encryption keys
        for i, c in enumerate(codeplug.contacts):
            c.index = i + 1  # Contacts are 1-based
        for i, gl in enumerate(codeplug.group_lists):
            gl.index = i + 1  # Group lists are 1-based
        for i, z in enumerate(codeplug.zones):
            z.index = i
        for i, ek in enumerate(codeplug.encryption_keys):
            ek.index = i

        # Build UUID→index maps for cross-reference resolution
        contact_idx_map = {c.uuid: c.index for c in codeplug.contacts}
        group_list_idx_map = {gl.uuid: gl.index for gl in codeplug.group_lists}
        encrypt_idx_map = {ek.uuid: ek.index + 1 for ek in codeplug.encryption_keys}
        # Channels use position-1 (convert 1-based position to 0-based slot)
        channel_idx_map = {ch.uuid: ch.position - 1 for ch in codeplug.channels}

        # Serialize settings to cfg_data if settings exist
        if codeplug.settings:
            codeplug.cfg_data = CodeplugSerializer.serialize_settings(codeplug.settings, codeplug.cfg_data)

        # Write CFG section
        data[OFFSET_CFG:OFFSET_CFG + SIZE_CFG] = codeplug.cfg_data

        use_beta_layout = bool(codeplug.settings and codeplug.settings.beta41)

        # Write channels at their designated positions
        for channel in codeplug.channels:
            if use_beta_layout:
                ch_data = CodeplugSerializer.serialize_channel_new(channel, contact_idx_map, group_list_idx_map, encrypt_idx_map)
            else:
                ch_data = CodeplugSerializer.serialize_channel(channel, contact_idx_map, group_list_idx_map, encrypt_idx_map)
            # Position is 1-based, convert to 0-based slot for offset calculation
            slot = channel.position - 1
            offset = OFFSET_CHANNELS + (slot * CHANNEL_SIZE)
            data[offset:offset + CHANNEL_SIZE] = ch_data

        # Write contacts
        for contact in codeplug.contacts:
            contact_data = CodeplugSerializer.serialize_contact(contact)
            # Contact index is 1-based, convert to 0-based slot for file offset
            offset = OFFSET_CONTACTS + ((contact.index - 1) * CONTACT_SIZE)
            data[offset:offset + CONTACT_SIZE] = contact_data

        # Write zones
        for zone in codeplug.zones:
            zone_data = CodeplugSerializer.serialize_zone(zone, channel_idx_map)
            offset = OFFSET_ZONES + (zone.index * ZONE_SIZE)
            data[offset:offset + ZONE_SIZE] = zone_data

        # Write group lists
        group_list_size = GROUP_LIST_SIZE_NEW if use_beta_layout else GROUP_LIST_SIZE
        max_contacts = MAX_GROUP_LIST_IDS_NEW if use_beta_layout else MAX_GROUP_LIST_IDS
        for group_list in codeplug.group_lists:
            gl_data = CodeplugSerializer.serialize_group_list(group_list, contact_idx_map, group_list_size, max_contacts)
            # Group list index is 1-based, convert to 0-based slot for file offset
            offset = OFFSET_GROUPLISTS + ((group_list.index - 1) * group_list_size)
            data[offset:offset + group_list_size] = gl_data

        # Write encryption keys
        for key in codeplug.encryption_keys:
            key_data = CodeplugSerializer.serialize_encryption_key(key)
            offset = OFFSET_ENCRYPT + (key.index * 48)  # Each key is 48 bytes
            data[offset:offset + 48] = key_data

        # Write other sections
        data[OFFSET_FM:OFFSET_FM + SIZE_FM] = codeplug.fm_data

        return bytes(data)

    @staticmethod
    def serialize_channel(channel: Channel, contact_idx_map: dict, group_list_idx_map: dict, encrypt_idx_map: dict) -> bytes:
        """Serialize a single channel to 48 bytes"""
        data = bytearray(b'\xff' * CHANNEL_SIZE)

        if channel.is_empty():
            return bytes(data)

        # Basic fields
        data[0x01] = 0x01
        data[0x02] = channel.mode.value

        # Frequencies (32-bit little-endian, stored as 10 Hz units)
        struct.pack_into('<I', data, 0x06, channel.rx_freq)
        struct.pack_into('<I', data, 0x0A, channel.tx_freq)

        # Power and scan
        data[0x10] = channel.power.value
        data[0x13] = channel.scan.value

        # Channel name (GBK encoding, 16 bytes)
        try:
            name_bytes = channel.name.encode('gbk')[:16]
        except:
            name_bytes = channel.name.encode('latin-1', errors='ignore')[:16]

        for i, byte in enumerate(name_bytes):
            data[0x20 + i] = byte
        # Pad remaining with 0xFF
        for i in range(len(name_bytes), 16):
            data[0x20 + i] = EMPTY_BYTE

        # Digital/DMR specific fields
        if channel.mode == ChannelMode.DIGITAL:
            # ID Select field (offset 0x00): 0=Radio ID, 1=Channel ID
            data[0x00] = 0x00 if channel.use_radio_id else 0x01

            data[0x03] = channel.dmr_time_slot
            data[0x04] = channel.dmr_color_code
            data[0x05] = channel.dmr_mode
            data[0x0E] = channel.dmr_monitor  # Promiscuous mode
            data[0x11] = channel.tx_priority
            data[0x14] = channel.tot
            data[0x15] = channel.alarm
            # Convert UUID references to indices
            group_list_index = group_list_idx_map.get(channel.group_list_uuid, 0)
            struct.pack_into('<H', data, 0x16, group_list_index)
            # Contact: convert UUID to index, then to 0-based slot number for file
            contact_index = contact_idx_map.get(channel.contact_uuid, 0)
            if contact_index == 0:
                contact_slot = 0xFFFF  # No contact selected
            else:
                contact_slot = contact_index - 1  # Convert index to slot
            struct.pack_into('<H', data, 0x18, contact_slot)
            encrypt_index = encrypt_idx_map.get(channel.encrypt_uuid, 0)
            struct.pack_into('<H', data, 0x1A, encrypt_index)
            # DMR ID: write 0 if using radio ID, otherwise write channel DMR ID
            if channel.use_radio_id:
                bcd_bytes = CodeplugSerializer._to_bcd(0)
            else:
                bcd_bytes = CodeplugSerializer._to_bcd(channel.dmr_id)
            data[0x1C:0x20] = bcd_bytes

        # Analog specific
        else:
            # Analog modulation: FM/AM/SSB (offset 0x00)
            data[0x00] = channel.analog_modulation.value

            # Bandwidth (offset 0x03)
            data[0x03] = channel.bandwidth

            # RX CTCSS/DCS (offset 0x04-0x05)
            rx_tone_bytes = encode_subaudio_bytes(channel.rx_ctcss)
            data[0x04:0x06] = rx_tone_bytes

            # TX CTCSS/DCS (offset 0x0E-0x0F)
            tx_tone_bytes = encode_subaudio_bytes(channel.tx_ctcss)
            data[0x0E:0x10] = tx_tone_bytes

            # TX Priority analog (offset 0x11)
            data[0x11] = channel.tx_priority_analog

            # TOT and CT/DCS Select (offset 0x12)
            data[0x12] = (channel.tot_analog & 0x1F) | ((channel.ctdcs_select & 0x07) << 5)

            # Tail tone and Scrambler (offset 0x13)
            data[0x13] = ((channel.tail_tone & 0x0F) << 4) | (channel.scramble & 0x0F)

            # Encrypted sub-audio codes (offsets 0x14-0x1F)
            # Write as 32-bit little-endian integers
            data[0x14:0x18] = struct.pack('<I', channel.mute_code)

        return bytes(data)

    @staticmethod
    def serialize_channel_new(channel: Channel, contact_idx_map: dict, group_list_idx_map: dict, encrypt_idx_map: dict) -> bytes:
        """Serialize a single beta41+ channel to 48 bytes"""
        data = bytearray(b'\xff' * CHANNEL_SIZE)

        if channel.is_empty():
            return bytes(data)

        # 0x00 layout bits
        data[0x00] = 0x00
        data[0x00] |= (channel.dmr_monitor & 0x01)
        data[0x00] |= (channel.dmr_time_slot & 0x01) << 1
        data[0x00] |= (channel.dmr_mode & 0x01) << 2
        # Bit 3: 0=use radio ID, 1=use channel ID (inverted from old layout)
        data[0x00] |= (0x00 if channel.use_radio_id else 0x08)
        if channel.mode != ChannelMode.DIGITAL:
            data[0x00] |= 0x40

        data[0x01] = (channel.scramble & 0x0F) | ((channel.dmr_color_code & 0x0F) << 4)

        tot_value = channel.tot if channel.mode == ChannelMode.DIGITAL else (channel.tot_analog or channel.tot)
        data[0x02] = tot_value & 0x3F
        if channel.power == PowerLevel.HIGH:
            data[0x02] |= 0x40

        data[0x03] = (channel.tail_tone & 0x07)
        data[0x03] |= (channel.tx_priority_analog & 0x03) << 3
        data[0x03] |= (channel.tx_priority & 0x03) << 5
        if channel.scan == ScanMode.REMOVE:
            data[0x03] |= 0x80

        modulation = channel.analog_modulation.value if channel.analog_modulation else AnalogModulation.FM.value
        data[0x04] = ((channel.ctdcs_select & 0x07) << 1)
        data[0x04] |= (modulation & 0x03) << 4
        data[0x04] |= (channel.bandwidth & 0x01) << 6

        # Frequencies (32-bit little-endian, stored as 10 Hz units)
        struct.pack_into('<I', data, 0x05, channel.rx_freq if channel.rx_freq else 0)
        struct.pack_into('<I', data, 0x09, channel.tx_freq if channel.tx_freq else 0)

        # RX/TX tones
        data[0x0D:0x0F] = encode_subaudio_bytes(channel.rx_ctcss)
        data[0x0F:0x11] = encode_subaudio_bytes(channel.tx_ctcss)

        # Convert UUID references to indices
        contact_index = contact_idx_map.get(channel.contact_uuid, 0)
        contact_slot = 0xFFFF if contact_index == 0 else max(contact_index - 1, 0)
        struct.pack_into('<H', data, 0x11, contact_slot)

        group_list_index = group_list_idx_map.get(channel.group_list_uuid, 0)
        data[0x13] = group_list_index & 0xFF
        encrypt_index = encrypt_idx_map.get(channel.encrypt_uuid, 0)
        struct.pack_into('<H', data, 0x14, encrypt_index & 0xFFFF)

        if channel.use_radio_id:
            bcd_bytes = CodeplugSerializer._to_bcd(0)
        else:
            bcd_bytes = CodeplugSerializer._to_bcd(channel.dmr_id)
        data[0x16:0x1A] = bcd_bytes
        data[0x1A:0x1E] = struct.pack('<I', channel.mute_code & 0xFFFFFFFF)

        # Channel name (GBK encoding, 16 bytes)
        try:
            name_bytes = channel.name.encode('gbk')[:16]
        except Exception:
            name_bytes = channel.name.encode('latin-1', errors='ignore')[:16]

        for i, byte in enumerate(name_bytes):
            data[0x20 + i] = byte
        for i in range(len(name_bytes), 16):
            data[0x20 + i] = EMPTY_BYTE

        return bytes(data)

    @staticmethod
    def serialize_contact(contact: Contact) -> bytes:
        """Serialize a single contact to 32 bytes"""
        data = bytearray(b'\xff' * CONTACT_SIZE)

        if contact.is_empty():
            return bytes(data)

        data[0x00] = 0x00
        data[0x01] = contact.contact_type.value

        # DMR ID as BCD (4 bytes at offset 0x02)
        bcd_bytes = CodeplugSerializer._to_bcd(contact.dmr_id)
        data[0x02:0x06] = bcd_bytes

        # Contact name (GBK encoding, 16 bytes at offset 0x10)
        try:
            name_bytes = contact.name.encode('gbk')[:16]
        except:
            name_bytes = contact.name.encode('latin-1', errors='ignore')[:16]

        for i, byte in enumerate(name_bytes):
            data[0x10 + i] = byte
        for i in range(len(name_bytes), 16):
            data[0x10 + i] = EMPTY_BYTE

        return bytes(data)

    @staticmethod
    def serialize_zone(zone: Zone, channel_idx_map: dict) -> bytes:
        """Serialize a single zone to 512 bytes"""
        data = bytearray(b'\xff' * ZONE_SIZE)

        if zone.is_empty():
            return bytes(data)

        # Zone name (GBK encoding, 16 bytes at offset 0x04)
        try:
            name_bytes = zone.name.encode('gbk')[:16]
        except:
            name_bytes = zone.name.encode('latin-1', errors='ignore')[:16]

        for i, byte in enumerate(name_bytes):
            data[0x04 + i] = byte
        for i in range(len(name_bytes), 16):
            data[0x04 + i] = EMPTY_BYTE

        # Channel list - convert UUIDs to indices
        # First 2 bytes: channel count (uint16_le)
        valid_channels = [channel_idx_map.get(uuid) for uuid in zone.channels if uuid in channel_idx_map]
        channel_count = min(len(valid_channels), 200)  # Max 200 channels
        data[0] = channel_count & 0xFF
        data[1] = (channel_count >> 8) & 0xFF

        # Channel indices start at offset 0x14 (20)
        # Each channel index is 2 bytes (uint16_le)
        for i, channel_idx in enumerate(valid_channels[:200]):
            offset = 0x14 + (i * 2)
            data[offset] = channel_idx & 0xFF
            data[offset + 1] = (channel_idx >> 8) & 0xFF

        return bytes(data)

    @staticmethod
    def serialize_encryption_key(key: EncryptionKey) -> bytes:
        """Serialize a single encryption key to 48 bytes"""
        data = bytearray(b'\xff' * 48)

        if key.is_empty():
            return bytes(data)

        # Key index at offset 0 (1-based)
        data[0] = key.index + 1

        # Key type at offset 1
        data[1] = key.enc_type.value

        # Key alias (GBK encoding, 14 bytes at offset 2-15)
        try:
            alias_bytes = key.alias.encode('gbk')[:14]
        except:
            alias_bytes = key.alias.encode('latin-1', errors='ignore')[:14]

        for i, byte in enumerate(alias_bytes):
            data[2 + i] = byte
        for i in range(len(alias_bytes), 14):
            data[2 + i] = EMPTY_BYTE

        # Key value (hex string to nibble-packed bytes, 32 bytes at offset 16-47)
        # Convert hex string to nibble array
        hex_str = key.value.upper()
        nibbles = []
        for char in hex_str:
            if '0' <= char <= '9':
                nibbles.append(ord(char) - ord('0'))
            elif 'A' <= char <= 'F':
                nibbles.append(ord(char) - ord('A') + 10)
            else:
                nibbles.append(0xF)  # Invalid char becomes 0xF

        # Pad with 0xF to 64 nibbles (32 bytes)
        while len(nibbles) < 64:
            nibbles.append(0xF)

        # Pack nibbles into bytes
        for i in range(32):
            high_nibble = nibbles[i * 2]
            low_nibble = nibbles[i * 2 + 1]
            data[16 + i] = (high_nibble << 4) | low_nibble

        return bytes(data)

    @staticmethod
    def serialize_group_list(group_list, contact_idx_map: dict, group_list_size: int = 272, max_contacts: int = 128) -> bytes:
        """Serialize a single group list to the specified size"""
        data = bytearray(b'\xff' * group_list_size)

        if group_list.is_empty():
            return bytes(data)

        # Byte 0: typically 0x00 or index
        data[0x00] = 0x00

        # Byte 1: enabled flag (0x01 = enabled)
        data[0x01] = 0x01

        # Group list name (14 bytes at offset 0x02, GBK encoding)
        try:
            name_bytes = group_list.name.encode('gbk')[:14]
        except:
            name_bytes = group_list.name.encode('latin-1', errors='ignore')[:14]

        for i, byte in enumerate(name_bytes):
            data[0x02 + i] = byte
        for i in range(len(name_bytes), 14):
            data[0x02 + i] = EMPTY_BYTE

        # Contact indices - convert UUIDs to indices (max_contacts × 2 bytes starting at offset 0x10)
        valid_contacts = [contact_idx_map.get(uuid) for uuid in group_list.contacts if uuid in contact_idx_map]
        for i in range(max_contacts):
            if i < len(valid_contacts):
                contact_idx = valid_contacts[i]
                struct.pack_into('<H', data, 0x10 + (i * 2), contact_idx - 1)
            else:
                # Empty slot: 0xFFFF
                struct.pack_into('<H', data, 0x10 + (i * 2), 0xFFFF)

        return bytes(data)

    @staticmethod
    def serialize_settings(settings, cfg_data: bytes) -> bytes:
        """Serialize RadioSettings to cfg_data buffer"""
        data = bytearray(cfg_data)

        # Encode strings to GBK
        def encode_gbk(text: str, length: int) -> bytes:
            try:
                encoded = text.encode('gbk')[:length]
            except:
                encoded = text.encode('latin-1', errors='ignore')[:length]
            # Pad with 0xFF
            return encoded + (b'\xff' * (length - len(encoded)))

        # Magic bytes (validation/signature)
        data[12] = 0xCD
        data[13] = 0xAB

        # Identity
        data[28:44] = encode_gbk(settings.startup_password, 16)
        data[44:76] = encode_gbk(settings.startup_message, 32)
        data[76:92] = encode_gbk(settings.radio_name, 16)
        data[384:388] = CodeplugSerializer._to_bcd(settings.radio_id)

        # Audio/UI
        data[92] = settings.voice_prompt
        data[93] = settings.key_beep
        data[94] = settings.key_lock
        data[95] = settings.lock_timer

        # Display
        data[96] = settings.led_on_off
        data[97] = settings.backlight_brightness
        data[98] = settings.led_timer
        data[101] = settings.menu_timer
        data[133] = settings.display_mode_a
        data[138] = settings.display_mode_b

        # Power
        data[99] = settings.power_save_mode
        data[100] = settings.power_save_start
        data[105] = 1 if settings.apo_enabled else 0

        # Operation
        data[102] = settings.dual_watch
        data[103] = settings.talkaround
        data[104] = settings.alarm_type
        data[126] = settings.tx_priority_global
        data[127] = settings.main_ptt
        data[128] = settings.vfo_step
        data[131] = settings.main_band
        data[132] = settings.work_mode_a
        data[134] = settings.zone_a
        data[135] = settings.channel_a & 0xFF
        data[136] = (settings.channel_a >> 8) & 0xFF
        data[137] = settings.work_mode_b
        data[139] = settings.zone_b
        data[140] = settings.channel_b & 0xFF
        data[141] = (settings.channel_b >> 8) & 0xFF

        # Clocks/Timers
        data[110] = settings.clock_1_mode
        data[111] = settings.clock_1_hour
        data[112] = settings.clock_1_minute
        data[113] = settings.clock_2_mode
        data[114] = settings.clock_2_hour
        data[115] = settings.clock_2_minute
        data[116] = settings.clock_3_mode
        data[117] = settings.clock_3_hour
        data[118] = settings.clock_3_minute
        data[119] = settings.clock_4_mode
        data[120] = settings.clock_4_hour
        data[121] = settings.clock_4_minute

        # Startup/Boot settings
        data[16] = settings.startup_picture_enable
        data[17] = settings.tx_protection
        data[19] = settings.startup_beep_enable
        data[20] = settings.startup_label_enable
        data[23] = settings.startup_display_line & 0xFF
        data[24] = (settings.startup_display_line >> 8) & 0xFF
        data[25] = settings.startup_display_column & 0xFF
        data[26] = (settings.startup_display_column >> 8) & 0xFF
        data[27] = settings.password_enable

        # Radio clock/time (32-bit value)
        data[106] = settings.radio_time_seconds & 0xFF
        data[107] = (settings.radio_time_seconds >> 8) & 0xFF
        data[108] = (settings.radio_time_seconds >> 16) & 0xFF
        data[109] = (settings.radio_time_seconds >> 24) & 0xFF

        # Frequency lock ranges (4 ranges)
        data[142] = settings.freq_lock_1_mode
        data[143] = settings.freq_lock_1_start & 0xFF
        data[144] = (settings.freq_lock_1_start >> 8) & 0xFF
        data[145] = settings.freq_lock_1_end & 0xFF
        data[146] = (settings.freq_lock_1_end >> 8) & 0xFF
        data[147] = settings.freq_lock_2_mode
        data[148] = settings.freq_lock_2_start & 0xFF
        data[149] = (settings.freq_lock_2_start >> 8) & 0xFF
        data[150] = settings.freq_lock_2_end & 0xFF
        data[151] = (settings.freq_lock_2_end >> 8) & 0xFF
        data[152] = settings.freq_lock_3_mode
        data[153] = settings.freq_lock_3_start & 0xFF
        data[154] = (settings.freq_lock_3_start >> 8) & 0xFF
        data[155] = settings.freq_lock_3_end & 0xFF
        data[156] = (settings.freq_lock_3_end >> 8) & 0xFF
        data[157] = settings.freq_lock_4_mode
        data[158] = settings.freq_lock_4_start & 0xFF
        data[159] = (settings.freq_lock_4_start >> 8) & 0xFF
        data[160] = settings.freq_lock_4_end & 0xFF
        data[161] = (settings.freq_lock_4_end >> 8) & 0xFF

        # Scan settings (0x0A2-0x0A5, 0x34A-0x353)
        data[0x0A2] = settings.scan_direction
        data[0x0A3] = settings.scan_mode
        data[0x0A4] = settings.scan_return
        data[0x0A5] = settings.scan_dwell
        data[0x34A] = settings.ch_direction
        data[0x34B] = settings.sms_prompt
        data[0x34C] = settings.scan_lower & 0xFF
        data[0x34D] = (settings.scan_lower >> 8) & 0xFF
        data[0x34E] = (settings.scan_lower >> 16) & 0xFF
        data[0x34F] = (settings.scan_lower >> 24) & 0xFF
        data[0x350] = settings.scan_upper & 0xFF
        data[0x351] = (settings.scan_upper >> 8) & 0xFF
        data[0x352] = (settings.scan_upper >> 16) & 0xFF
        data[0x353] = (settings.scan_upper >> 24) & 0xFF

        # Function keys
        data[170] = settings.key_fs1_short
        data[171] = settings.key_fs1_long
        data[172] = settings.key_fs2_short
        data[173] = settings.key_fs2_long
        data[176] = settings.key_0
        data[177] = settings.key_1
        data[178] = settings.key_2
        data[179] = settings.key_3
        data[180] = settings.key_4
        data[181] = settings.key_5
        data[182] = settings.key_6
        data[183] = settings.key_7
        data[184] = settings.key_8
        data[185] = settings.key_9

        # Audio Settings (0x100-0x11A)
        data[0x100] = settings.tone_frequency & 0xFF
        data[0x101] = (settings.tone_frequency >> 8) & 0xFF
        data[0x102] = settings.squelch_level
        data[0x105] = settings.tx_mic_gain
        data[0x106] = settings.rx_speaker_volume
        data[0x10B] = settings.tx_start_beep
        data[0x10C] = settings.roger_beep
        data[0x10D] = settings.analog_vox
        data[0x10E] = settings.vox_threshold
        data[0x10F] = settings.vox_delay
        data[0x117] = settings.short_tail
        data[0x118] = settings.tone_timer
        data[0x119] = settings.single_tone_timer & 0xFF
        data[0x11A] = (settings.single_tone_timer >> 8) & 0xFF

        # Display Settings (additional)
        data[0x0A8] = settings.rssi_refresh & 0xFF
        data[0x0A9] = (settings.rssi_refresh >> 8) & 0xFF
        data[0x0E8] = settings.slaver_ptt
        data[0x0E9] = settings.lcd_contrast
        data[0x0EA] = settings.display_lines
        data[0x0EB] = settings.dual_display_mode

        # DMR Audio Settings (0x185-0x193)
        data[0x185] = settings.tx_denoise
        data[0x186] = settings.rx_denoise
        data[0x187] = settings.call_mic_gain
        data[0x188] = settings.call_speaker_volume
        data[0x18D] = settings.call_start_beep
        data[0x18E] = settings.call_end_beep
        data[0x193] = settings.digital_squelch

        # DMR Enhancements (0x184, 0x18F-0x194)
        data[0x184] = settings.remote_control
        data[0x18F] = settings.group_call_hang_time & 0xFF
        data[0x190] = (settings.group_call_hang_time >> 8) & 0xFF
        data[0x191] = settings.private_call_hang_time & 0xFF
        data[0x192] = (settings.private_call_hang_time >> 8) & 0xFF
        data[0x194] = settings.call_group_display

        # DMR SMS Fields (0x195-0x19A)
        data[0x195] = settings.dmr_send_dtmf
        data[0x196] = settings.sms_format
        data[0x197] = settings.sms_font
        data[0x198] = settings.caller_keep
        data[0x199] = settings.call_log_wpos & 0xFF
        data[0x19A] = (settings.call_log_wpos >> 8) & 0xFF

        # Advanced Features (0x110-0x116)
        data[0x110] = settings.detection_range & 0xFF
        data[0x111] = settings.relay_delay & 0xFF
        data[0x112] = (settings.relay_delay >> 8) & 0xFF
        data[0x113] = settings.noaa_channel
        data[0x114] = settings.glitch_filter
        data[0x115] = settings.spectrum_step & 0xFF
        data[0x116] = (settings.spectrum_step >> 8) & 0xFF

        # DTMF System
        data[512] = settings.dtmf_send_delay & 0xFF
        data[513] = settings.dtmf_send_duration & 0xFF
        data[514] = settings.dtmf_send_interval & 0xFF
        data[515] = settings.dtmf_send_mode & 0xFF
        data[516] = settings.dtmf_send_select & 0xFF
        data[517] = settings.dtmf_display_enable & 0xFF
        data[518] = settings.dtmf_gain & 0xFF
        data[519] = settings.dtmf_decode_threshold & 0xFF
        data[520] = settings.dtmf_remote_control & 0xFF
        data[521] = settings.dtmf_remote_cal_time & 0xFF
        # Serialize 20 DTMF codes (each 16 bytes starting at offset 522)
        for i in range(20):
            offset = 522 + (i * 16)
            code = settings.dtmf_codes[i] if i < len(settings.dtmf_codes) else ""
            data[offset:offset+16] = encode_gbk(code, 16)

        # DT Custom Firmware Settings (offset 0x380 = 896)
        data[0x380] = settings.scan_speed_analog & 0xFF
        data[0x381] = settings.tx_backlight & 0xFF
        data[0x382] = settings.green_key_long & 0xFF
        data[0x383] = settings.voltage_display & 0xFF
        data[0x384] = settings.live_sub_tone & 0xFF
        data[0x385] = settings.spectrum_threshold & 0xFF
        data[0x386] = settings.sub_tone_ptt & 0xFF
        data[0x387] = settings.tot_warning & 0xFF
        data[0x388] = settings.scan_end & 0xFF
        data[0x389] = settings.scan_continue & 0xFF
        data[0x392] = settings.dt_scan_return & 0xFF
        # VFO offsets are 32-bit little-endian integers (convert signed to unsigned)
        # Stored in units of 10 Hz, so divide by 10 before storing
        vfo_a_offset = settings.vfo_a_offset // 10  # Convert Hz to storage units
        vfo_a_offset &= 0xFFFFFFFF
        data[0x393] = vfo_a_offset & 0xFF
        data[0x394] = (vfo_a_offset >> 8) & 0xFF
        data[0x395] = (vfo_a_offset >> 16) & 0xFF
        data[0x396] = (vfo_a_offset >> 24) & 0xFF
        vfo_b_offset = settings.vfo_b_offset // 10  # Convert Hz to storage units
        vfo_b_offset &= 0xFFFFFFFF
        data[0x397] = vfo_b_offset & 0xFF
        data[0x398] = (vfo_b_offset >> 8) & 0xFF
        data[0x399] = (vfo_b_offset >> 16) & 0xFF
        data[0x39A] = (vfo_b_offset >> 24) & 0xFF
        data[0x39B] = settings.callsign_lookup & 0xFF
        data[0x39C] = settings.dmr_scan_speed & 0xFF
        data[0x39D] = settings.ptt_lock & 0xFF
        data[0x39E] = settings.zone_channel_display & 0xFF
        data[0x39F] = settings.dmr_gid_name & 0xFF
        data[0x3A0] = settings.tx_alias & 0xFF
        
        if settings.beta41:
            data[4092:4096] = BETA41_MAGIC

        return bytes(data)

    @staticmethod
    def _to_bcd(value: int) -> bytes:
        """Convert integer to BCD encoded bytes (4 bytes)"""
        bcd = bytearray(4)
        for i in range(4):
            low = value % 10
            value //= 10
            high = value % 10
            value //= 10
            bcd[i] = (high << 4) | low
        return bytes(bcd)

    @staticmethod
    def to_file(codeplug: Codeplug, filename: str):
        """Write codeplug to .4rdmf file"""
        data = CodeplugSerializer.serialize(codeplug)
        with open(filename, 'wb') as f:
            f.write(data)
