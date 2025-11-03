"""RT-4D Codeplug Binary Serializer"""

import struct
from .models import (Codeplug, Channel, Contact, Zone, ChannelMode, PowerLevel,
                      ScanMode, ContactType, EncryptionKey, EncryptionType)
from .constants import *
from .tones import encode_subaudio_bytes


class CodeplugSerializer:
    """Serialize Codeplug objects to binary .4rdmf format"""

    @staticmethod
    def serialize(codeplug: Codeplug) -> bytes:
        """Serialize complete codeplug to binary data"""
        # Initialize with empty data (all 0xFF)
        data = bytearray(b'\xff' * TOTAL_SIZE)

        # Serialize settings to cfg_data if settings exist
        if codeplug.settings:
            codeplug.cfg_data = CodeplugSerializer.serialize_settings(codeplug.settings, codeplug.cfg_data)

        # Write CFG section
        data[OFFSET_CFG:OFFSET_CFG + SIZE_CFG] = codeplug.cfg_data

        # Write channels
        for channel in codeplug.channels:
            ch_data = CodeplugSerializer.serialize_channel(channel)
            offset = OFFSET_CHANNELS + (channel.index * CHANNEL_SIZE)
            data[offset:offset + CHANNEL_SIZE] = ch_data

        # Write contacts
        for contact in codeplug.contacts:
            contact_data = CodeplugSerializer.serialize_contact(contact)
            # Contact index is 1-based, convert to 0-based slot for file offset
            offset = OFFSET_CONTACTS + ((contact.index - 1) * CONTACT_SIZE)
            data[offset:offset + CONTACT_SIZE] = contact_data

        # Write zones
        for zone in codeplug.zones:
            zone_data = CodeplugSerializer.serialize_zone(zone)
            offset = OFFSET_ZONES + (zone.index * ZONE_SIZE)
            data[offset:offset + ZONE_SIZE] = zone_data

        # Write group lists
        for group_list in codeplug.group_lists:
            gl_data = CodeplugSerializer.serialize_group_list(group_list)
            GROUP_LIST_SIZE = 272
            # Group list index is 1-based, convert to 0-based slot for file offset
            offset = OFFSET_GROUPLISTS + ((group_list.index - 1) * GROUP_LIST_SIZE)
            data[offset:offset + GROUP_LIST_SIZE] = gl_data

        # Write encryption keys
        for key in codeplug.encryption_keys:
            key_data = CodeplugSerializer.serialize_encryption_key(key)
            offset = OFFSET_ENCRYPT + (key.index * 48)  # Each key is 48 bytes
            data[offset:offset + 48] = key_data

        # Write other sections
        data[OFFSET_FM:OFFSET_FM + SIZE_FM] = codeplug.fm_data

        return bytes(data)

    @staticmethod
    def serialize_channel(channel: Channel) -> bytes:
        """Serialize a single channel to 48 bytes"""
        data = bytearray(b'\xff' * CHANNEL_SIZE)

        if channel.is_empty():
            return bytes(data)

        # Basic fields
        data[0x01] = 0x01 if channel.enabled else 0xFF
        data[0x02] = channel.mode.value

        # Frequencies (32-bit little-endian)
        rx_freq_int = int(channel.rx_freq * FREQ_MULTIPLIER)
        tx_freq_int = int(channel.tx_freq * FREQ_MULTIPLIER)
        struct.pack_into('<I', data, 0x06, rx_freq_int)
        struct.pack_into('<I', data, 0x0A, tx_freq_int)

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
            struct.pack_into('<H', data, 0x16, channel.group_list_index)
            # Contact index: convert from 1-based contact.index to 0-based slot number for file
            if channel.contact_index == 0:
                contact_slot = 0xFFFF  # No contact selected
            else:
                contact_slot = channel.contact_index - 1  # Convert index to slot
            struct.pack_into('<H', data, 0x18, contact_slot)
            struct.pack_into('<H', data, 0x1A, channel.encrypt_index)
            # DMR ID is always written at offset 0x1C-0x1F (BCD encoded)
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
            data[0x14:0x18] = struct.pack('<I', channel.encrypted_code_1)
            data[0x18:0x1C] = struct.pack('<I', channel.encrypted_code_2)
            data[0x1C:0x20] = struct.pack('<I', channel.encrypted_code_3)

        return bytes(data)

    @staticmethod
    def serialize_contact(contact: Contact) -> bytes:
        """Serialize a single contact to 32 bytes"""
        data = bytearray(b'\xff' * CONTACT_SIZE)

        if contact.is_empty():
            return bytes(data)

        data[0x00] = contact.index if contact.index > 0 else 1
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
    def serialize_zone(zone: Zone) -> bytes:
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

        # Channel list
        # First 2 bytes: channel count (uint16_le)
        channel_count = min(len(zone.channels), 200)  # Max 200 channels
        data[0] = channel_count & 0xFF
        data[1] = (channel_count >> 8) & 0xFF

        # Channel indices start at offset 0x14 (20)
        # Each channel index is 2 bytes (uint16_le)
        for i, channel_idx in enumerate(zone.channels[:200]):
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
    def serialize_group_list(group_list) -> bytes:
        """Serialize a single group list to 272 bytes"""
        GROUP_LIST_SIZE = 272
        data = bytearray(b'\xff' * GROUP_LIST_SIZE)

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

        # Contact indices (128 × 2 bytes starting at offset 0x10)
        for i in range(128):
            if i < len(group_list.contacts):
                contact_idx = group_list.contacts[i]
                struct.pack_into('<H', data, 0x10 + (i * 2), contact_idx)
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

        # Scan settings
        data[162] = settings.scan_direction
        data[163] = settings.scan_mode
        data[164] = settings.scan_return
        data[165] = settings.scan_dwell

        # Function keys
        data[170] = settings.key_fs1_short
        data[171] = settings.key_fs1_long
        data[172] = settings.key_fs2_short
        data[173] = settings.key_fs2_long
        data[174] = settings.key_alarm_short
        data[175] = settings.key_alarm_long
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

        # Audio Settings
        data[256] = settings.tone_frequency & 0xFF
        data[257] = (settings.tone_frequency >> 8) & 0xFF
        data[258] = settings.squelch_level
        data[261] = settings.tx_mic_gain
        data[262] = settings.rx_speaker_volume
        data[267] = settings.tx_start_beep
        data[268] = settings.roger_beep
        data[391] = settings.call_mic_gain
        data[392] = settings.call_speaker_volume
        data[397] = settings.call_start_beep
        data[398] = settings.call_end_beep
        data[403] = settings.digital_squelch

        # Display Settings (additional)
        data[233] = settings.lcd_contrast
        data[234] = settings.display_lines
        data[235] = settings.dual_display_mode

        # DMR Enhancements
        data[388] = settings.remote_control
        data[389] = settings.group_call_hang_time & 0xFF
        data[390] = (settings.group_call_hang_time >> 8) & 0xFF
        data[395] = settings.private_call_hang_time & 0xFF
        data[396] = (settings.private_call_hang_time >> 8) & 0xFF
        data[400] = settings.group_id_display
        data[404] = settings.call_timing_display

        # Advanced Features
        data[272] = settings.noaa_channel
        data[273] = settings.spectrum_scan_mode
        data[274] = settings.detection_range & 0xFF
        data[275] = (settings.detection_range >> 8) & 0xFF
        data[276] = settings.relay_delay
        data[842] = settings.glitch_filter

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
        data[896] = settings.scan_speed_analog & 0xFF
        data[897] = settings.tx_backlight & 0xFF
        data[898] = settings.green_key_long & 0xFF
        data[899] = settings.voltage_display & 0xFF
        data[900] = settings.live_sub_tone & 0xFF
        data[901] = settings.spectrum_threshold & 0xFF
        data[902] = settings.sub_tone_ptt & 0xFF
        data[903] = settings.tot_warning & 0xFF
        data[904] = settings.scan_end & 0xFF
        data[905] = settings.scan_continue & 0xFF
        data[914] = settings.scan_return & 0xFF
        # VFO offsets are 32-bit little-endian integers (convert signed to unsigned)
        # Stored in units of 10 Hz, so divide by 10 before storing
        vfo_a_offset = settings.vfo_a_offset // 10  # Convert Hz to storage units
        vfo_a_offset = vfo_a_offset if vfo_a_offset >= 0 else 0x100000000 + vfo_a_offset
        data[915] = vfo_a_offset & 0xFF
        data[916] = (vfo_a_offset >> 8) & 0xFF
        data[917] = (vfo_a_offset >> 16) & 0xFF
        data[918] = (vfo_a_offset >> 24) & 0xFF
        vfo_b_offset = settings.vfo_b_offset // 10  # Convert Hz to storage units
        vfo_b_offset = vfo_b_offset if vfo_b_offset >= 0 else 0x100000000 + vfo_b_offset
        data[919] = vfo_b_offset & 0xFF
        data[920] = (vfo_b_offset >> 8) & 0xFF
        data[921] = (vfo_b_offset >> 16) & 0xFF
        data[922] = (vfo_b_offset >> 24) & 0xFF
        data[923] = settings.callsign_lookup & 0xFF
        data[924] = settings.dmr_scan_speed & 0xFF
        data[925] = settings.ptt_lock & 0xFF
        data[926] = settings.zone_channel_display & 0xFF
        data[927] = settings.dmr_gid_name & 0xFF

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
