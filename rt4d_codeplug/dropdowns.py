"""Dropdown values extracted from RT-4D CPS"""

from rt4d_codeplug.timer_conversion import generate_timer_values, TOT_MAX_INDEX, LED_MENU_MAX_INDEX, LOCK_MAX_INDEX, POWER_SAVE_MAX_INDEX

# Timeout (TOT) values - stores firmware INDEX (0-40), converted to seconds via CONV_GetDuration()
# Firmware conversion: index 0=0s, 1=5s, 2=10s, 3=15s, 4=30s, 5=45s, 6=60s, etc.
# Formula: if (index <= 3) { seconds = index * 5 } else { seconds = (index - 2) * 15 }
TOT_VALUES = [(label, index) for index, label in generate_timer_values(TOT_MAX_INDEX).items()]

# TX Priority values
TX_PRIORITY_VALUES = [
    ("No Restriction", 0),
    ("Carrier Match Prohibit", 1),
    ("Sub-tone Match Prohibit", 2),
]

# Power levels
POWER_VALUES = [
    ("High", 0),
    ("Low", 1),
]

# Scan modes
SCAN_VALUES = [
    ("Add", 0),
    ("Remove", 1),
]

# Alarm system
ALARM_VALUES = [
    ("Disabled", 0),
    ("Enabled", 1),
]

# DMR Monitor Mode (Promiscuous Mode)
DMR_MONITOR_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# DCDM
DMR_MODE_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# Analog modulation - offset 0x00
ANALOG_MODULATION_VALUES = [
    ("FM", 0),
    ("AM", 1),
    ("SSB", 2),
]

# Bandwidth (analog) - offset 0x03
BANDWIDTH_VALUES = [
    ("Wide (25 kHz)", 0),
    ("Narrow (12.5 kHz)", 1),
]

# Scrambler modes
SCRAMBLER_VALUES = [
    ("Off", 0),
    ("1", 1),
    ("2", 2),
    ("3", 3),
    ("4", 4),
    ("5", 5),
    ("6", 6),
    ("7", 7),
    ("8", 8),
]

# CT/DCS Select (sub-tone matching)
CTDCS_SELECT_VALUES = [
    ("Normal Sub-tone", 0),
    ("Encrypted Sub-tone 1", 1),
    ("Encrypted Sub-tone 2", 2),
    ("Encrypted Sub-tone 3", 3),
    ("Decode Sub-tone", 4),
]

# Tail Tone Elimination - stores dropdown INDEX (0-4) in upper 3 bits at offset 0x13
# CPS stores: (byte >> 4) & 7, so values 0-7 possible, but only 0-4 used
# CPS MainForm.cs line 17043: 5 items - "关闭", "55Hz", "120°相移", "180°相移", "240°相移"
# Note: AnalogCH.cs has a copy-paste bug showing 41 TOT items, ignore it - MainForm is correct
TAIL_TONE_VALUES = [
    ("Off", 0),
    ("55Hz No Shift", 1),
    ("120° Phase Shift", 2),
    ("180° Phase Shift", 3),
    ("240° Phase Shift", 4),
]

# CTCSS/DCS codes for analog channels
CTCSS_DCS_VALUES = [
    "None",
    # CTCSS tones (Hz)
    "67.0", "69.3", "71.9", "74.4", "77.0", "79.7", "82.5", "85.4", "88.5",
    "91.5", "94.8", "97.4", "100.0", "103.5", "107.2", "110.9", "114.8", "118.8", "123.0",
    "127.3", "131.8", "136.5", "141.3", "146.2", "151.4", "156.7", "159.8", "162.2", "165.5",
    "167.9", "171.3", "173.8", "177.3", "179.9", "183.5", "186.2", "189.9", "192.8", "196.6",
    "199.5", "203.5", "206.5", "210.7", "218.1", "225.7", "229.1", "233.6", "241.8", "250.3",
    "254.1",
    # DCS codes (Normal polarity)
    "D023N", "D025N", "D026N", "D031N", "D032N", "D036N", "D043N", "D047N", "D051N",
    "D053N", "D054N", "D065N", "D071N", "D072N", "D073N", "D074N", "D114N", "D115N", "D116N",
    "D122N", "D125N", "D131N", "D132N", "D134N", "D143N", "D145N", "D152N", "D155N", "D156N",
    "D162N", "D165N", "D172N", "D174N", "D205N", "D212N", "D223N", "D225N", "D226N", "D243N",
    "D244N", "D245N", "D246N", "D251N", "D252N", "D255N", "D261N", "D263N", "D265N", "D266N",
    "D271N", "D274N", "D306N", "D311N", "D315N", "D325N", "D331N", "D332N", "D343N", "D346N",
    "D351N", "D356N", "D364N", "D365N", "D371N", "D411N", "D412N", "D413N", "D423N", "D431N",
    "D432N", "D445N", "D446N", "D452N", "D454N", "D455N", "D462N", "D464N", "D465N", "D466N",
    "D503N", "D506N", "D516N", "D523N", "D526N", "D532N", "D546N", "D565N", "D606N", "D612N",
    "D624N", "D627N", "D631N", "D632N", "D645N", "D654N", "D662N", "D664N", "D703N", "D712N",
    "D723N", "D731N", "D732N", "D734N", "D743N", "D754N",
    # DCS codes (Inverted polarity)
    "D023I", "D025I", "D026I", "D031I", "D032I", "D036I", "D043I", "D047I", "D051I",
    "D053I", "D054I", "D065I", "D071I", "D072I", "D073I", "D074I", "D114I", "D115I", "D116I",
    "D122I", "D125I", "D131I", "D132I", "D134I", "D143I", "D145I", "D152I", "D155I", "D156I",
    "D162I", "D165I", "D172I", "D174I", "D205I", "D212I", "D223I", "D225I", "D226I", "D243I",
    "D244I", "D245I", "D246I", "D251I", "D252I", "D255I", "D261I", "D263I", "D265I", "D266I",
    "D271I", "D274I", "D306I", "D311I", "D315I", "D325I", "D331I", "D332I", "D343I", "D346I",
    "D351I", "D356I", "D364I", "D365I", "D371I", "D411I", "D412I", "D413I", "D423I", "D431I",
    "D432I", "D445I", "D446I", "D452I", "D454I", "D455I", "D462I", "D464I", "D465I", "D466I",
    "D503I", "D506I", "D516I", "D523I", "D526I", "D532I", "D546I", "D565I", "D606I", "D612I",
    "D624I", "D627I", "D631I", "D632I", "D645I", "D654I", "D662I", "D664I", "D703I", "D712I",
    "D723I", "D731I", "D732I", "D734I", "D743I", "D754I",
]

# Radio settings dropdowns
VOICE_PROMPT_VALUES = [
    ("Off", 0),
    ("On", 1),
]

KEY_BEEP_VALUES = [
    ("Off", 0),
    ("On", 1),
]

KEY_LOCK_VALUES = [
    ("Manual", 0),
    ("Auto", 1),
]

DUAL_WATCH_VALUES = [
    ("Off", 0),
    ("On", 1),
]

WORK_MODE_VALUES = [
    ("VFO", 0),
    ("Channel", 1),
    ("Zone", 2),
]

# Talkaround modes
TALKAROUND_VALUES = [
    ("Off", 0),
    ("Direct/Offline", 1),
    ("Reverse", 2),
]

# Alarm type
ALARM_TYPE_VALUES = [
    ("Local", 0),
    ("Remote", 1),
    ("Local+Remote", 2),
]

# Lock timer values - stores firmware INDEX, converted to seconds via CONV_GetDuration()
# Same conversion as TOT: index 0=0s (Off), 1=5s, 2=10s, 3=15s, 4=30s, etc.
LOCK_TIMER_VALUES = [(label, index) for index, label in generate_timer_values(LOCK_MAX_INDEX).items()]

# LED timer values - stores firmware INDEX, converted to seconds via CONV_GetDuration()
LED_TIMER_VALUES = [(label, index) for index, label in generate_timer_values(LED_MENU_MAX_INDEX).items()]

# Menu timer values - stores firmware INDEX, converted to seconds via CONV_GetDuration()
MENU_TIMER_VALUES = [(label, index) for index, label in generate_timer_values(LED_MENU_MAX_INDEX).items()]

# LED on/off
LED_ON_OFF_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# Backlight brightness levels
BACKLIGHT_BRIGHTNESS_VALUES = [
    ("0", 0),
    ("1", 1),
    ("2", 2),
    ("3", 3),
    ("4", 4),
]

# Power save start timer - stores firmware INDEX, converted to seconds via CONV_GetDuration()
# Same conversion as TOT: index 0=0s, 1=5s, 2=10s, 3=15s, 4=30s, etc.
POWER_SAVE_START_VALUES = [(label, index) for index, label in generate_timer_values(POWER_SAVE_MAX_INDEX).items()]

# Global TX Priority
TX_PRIORITY_GLOBAL_VALUES = [
    ("Edit", 0),
    ("Busy", 1),
]

# Main PTT behavior
MAIN_PTT_VALUES = [
    ("Band A", 0),
    ("Main Band", 1),
]

# VFO frequency step
VFO_STEP_VALUES = [
    ("0.25 kHz", 0),
    ("1.25 kHz", 1),
    ("2.5 kHz", 2),
    ("5 kHz", 3),
    ("6.25 kHz", 4),
    ("10 kHz", 5),
    ("12.5 kHz", 6),
    ("20 kHz", 7),
    ("25 kHz", 8),
    ("50 kHz", 9),
    ("100 kHz", 10),
    ("500 kHz", 11),
    ("1 MHz", 12),
    ("5 MHz", 13),
]

# Main band selection
MAIN_BAND_VALUES = [
    ("A", 0),
    ("B", 1),
]

# Display mode
DISPLAY_MODE_VALUES = [
    ("Channel Number", 0),
    ("Frequency", 1),
    ("Channel Name", 2),
]

# Clock/Timer mode
CLOCK_MODE_VALUES = [
    ("Off", 0),
    ("Once", 1),
    ("Daily", 2),
]

# Startup/Boot settings
STARTUP_PICTURE_VALUES = [
    ("Off", 0),
    ("On", 1),
]

TX_PROTECTION_VALUES = [
    ("Off", 0),
    ("On", 1),
]

STARTUP_BEEP_VALUES = [
    ("Off", 0),
    ("On", 1),
]

STARTUP_LABEL_VALUES = [
    ("Off", 0),
    ("On", 1),
]

PASSWORD_ENABLE_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# Frequency lock range modes
FREQUENCY_LOCK_VALUES = [
    ("Unlock", 0),
    ("RX Only", 1),
    ("Lock", 2),
]

# Scan settings
SCAN_DIRECTION_VALUES = [
    ("Up", 0),
    ("Down", 1),
]

SCAN_RETURN_VALUES = [
    ("Original CH", 0),
    ("Current CH", 1),
]

# Scan mode values
SCAN_MODE_VALUES = [
    ("CO", 0),
    ("TO", 1),
    ("SE", 2),
]

# Scan dwell time values (0-30 seconds)
SCAN_DWELL_VALUES = [
    ("0s", 0), ("1s", 1), ("2s", 2), ("3s", 3), ("4s", 4), ("5s", 5),
    ("6s", 6), ("7s", 7), ("8s", 8), ("9s", 9), ("10s", 10),
    ("11s", 11), ("12s", 12), ("13s", 13), ("14s", 14), ("15s", 15),
    ("16s", 16), ("17s", 17), ("18s", 18), ("19s", 19), ("20s", 20),
    ("21s", 21), ("22s", 22), ("23s", 23), ("24s", 24), ("25s", 25),
    ("26s", 26), ("27s", 27), ("28s", 28), ("29s", 29), ("30s", 30),
]

# Squelch level values (0-9)
SQUELCH_LEVEL_VALUES = [
    ("0", 0), ("1", 1), ("2", 2), ("3", 3), ("4", 4),
    ("5", 5), ("6", 6), ("7", 7), ("8", 8), ("9", 9),
]

# Audio beep on/off
BEEP_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# LCD contrast values (0-15)
LCD_CONTRAST_VALUES = [
    ("0", 0), ("1", 1), ("2", 2), ("3", 3), ("4", 4), ("5", 5),
    ("6", 6), ("7", 7), ("8", 8), ("9", 9), ("10", 10), ("11", 11),
    ("12", 12), ("13", 13), ("14", 14), ("15", 15),
]

# Display lines mode
DISPLAY_LINES_VALUES = [
    ("6 digits", 0),
    ("8 digits", 1),
]

# Dual display mode
DUAL_DISPLAY_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# Remote control enable
REMOTE_CONTROL_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# Group/Private call hang time (ms)
HANG_TIME_VALUES = [
    ("0 ms", 0),
    ("500 ms", 500),
    ("1000 ms", 1000),
    ("1500 ms", 1500),
    ("2000 ms", 2000),
    ("2500 ms", 2500),
    ("3000 ms", 3000),
    ("3500 ms", 3500),
    ("4000 ms", 4000),
    ("4500 ms", 4500),
    ("5000 ms", 5000),
]

# Group ID / Call timing display
DISPLAY_ENABLE_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# NOAA weather channels
NOAA_CHANNEL_VALUES = [
    ("1 (162.550 MHz)", 0),
    ("2 (162.400 MHz)", 1),
    ("3 (162.475 MHz)", 2),
    ("4 (162.425 MHz)", 3),
    ("5 (162.450 MHz)", 4),
    ("6 (162.500 MHz)", 5),
    ("7 (162.525 MHz)", 6),
    ("8 (161.650 MHz)", 7),
    ("9 (161.775 MHz)", 8),
    ("10 (163.275 MHz)", 9),
]

# Function key actions - stores dropdown INDEX (0-44)
# CPS MainForm.cs line 369: CBOX_KEY array with 120 items = 40 per language (stock firmware)
# Custom firmware extends this to 45 function types (indices 40-44)
# CPS stores directly: bufCFG[170] = (byte)cboxFS1S.SelectedIndex (lines 5514-5525)
FUNCTION_KEY_VALUES = [
    ("None", 0),
    ("Analog Monitor", 1),
    ("Power Switch", 2),
    ("Dual Standby", 3),
    ("TX Priority", 4),
    ("Scanning", 5),
    ("Backlight", 6),
    ("Analog Roger Beep", 7),
    ("FM Radio", 8),
    ("Talkaround", 9),
    ("Emergency Alarm", 10),
    ("Freq Detect", 11),
    ("Remote CTC/DCS Decode", 12),
    ("Send Tone", 13),
    ("Query State", 14),
    ("Remote Monitor", 15),
    ("Color Code Detect", 16),
    ("DMR Remote Stun", 17),
    ("DMR Remote Kill", 18),
    ("DMR Remote Wakeup", 19),
    ("Online Detect", 20),
    ("Group Call ID Show", 21),
    ("AM/FM Switch (RX)", 22),
    ("Analog Spectrum", 23),
    ("Squelch Level", 24),
    ("Freq Step", 25),
    ("Analog/DMR Switch", 26),
    ("NOAA Weather CH", 27),
    ("Save Channel", 28),
    ("New SMS", 29),
    ("Jump to SMS", 30),
    ("LCD Brightness", 31),
    ("Analog VOX", 32),
    ("Zone Selection", 33),
    ("Promiscuous Mode", 34),
    ("Dual Slot On/Off", 35),
    ("Time Slot Switch", 36),
    ("Color Code Switch", 37),
    ("DMR Encrypt On/Off", 38),
    ("RX Group List Selection", 39),
    # --- Custom Firmware Extensions (requires custom firmware) ---
    ("Address Book (Custom FW)", 40),          # Custom FW only
    ("Contacts List (Custom FW)", 41),         # Custom FW only
    ("Next Zone (Custom FW)", 42),             # Custom FW only
    ("Send DTMF (Custom FW)", 43),             # Custom FW only
    ("Freq Monitor (Custom FW)", 44),          # Custom FW only
]

# DTMF Send Delay (offset 512)
DTMF_SEND_DELAY_VALUES = [
    ("0ms", 0), ("100ms", 1), ("200ms", 2), ("300ms", 3), ("400ms", 4),
    ("500ms", 5), ("600ms", 6), ("700ms", 7), ("800ms", 8), ("900ms", 9),
    ("1000ms", 10), ("1100ms", 11), ("1200ms", 12), ("1300ms", 13), ("1400ms", 14),
    ("1500ms", 15), ("1600ms", 16), ("1700ms", 17), ("1800ms", 18), ("1900ms", 19),
    ("2000ms", 20),
]

# DTMF Send Duration and Send Interval (offsets 513, 514)
DTMF_DURATION_VALUES = [
    ("30ms", 0), ("40ms", 1), ("50ms", 2), ("60ms", 3), ("70ms", 4),
    ("80ms", 5), ("90ms", 6), ("100ms", 7), ("110ms", 8), ("120ms", 9),
    ("130ms", 10), ("140ms", 11), ("150ms", 12), ("160ms", 13), ("170ms", 14),
    ("180ms", 15), ("190ms", 16), ("200ms", 17),
]

# DTMF Send Mode (offset 515)
DTMF_SEND_MODE_VALUES = [
    ("Off", 0),
    ("TX Begin", 1),
    ("TX End", 2),
    ("Begin And End", 3),
]

# DTMF Preset Code Selection (offset 516)
DTMF_PRESET_VALUES = [
    ("DTMF-01", 0), ("DTMF-02", 1), ("DTMF-03", 2), ("DTMF-04", 3),
    ("DTMF-05", 4), ("DTMF-06", 5), ("DTMF-07", 6), ("DTMF-08", 7),
    ("DTMF-09", 8), ("DTMF-10", 9), ("DTMF-11", 10), ("DTMF-12", 11),
    ("DTMF-13", 12), ("DTMF-14", 13), ("DTMF-15", 14), ("DTMF-16", 15),
]

# === DT Custom Firmware Settings (offset 0x380) ===

# Scan Speed for Analog channels (offset 0x380)
# DT custom firmware: 4 values representing milliseconds
SCAN_SPEED_ANALOG_VALUES = [
    ("60 ms", 0),
    ("100 ms", 1),
    ("150 ms", 2),
    ("200 ms", 3),
]

# TX Backlight (offset 0x381)
TX_BACKLIGHT_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# Green Key Long Press - same values as function keys (offset 0x382)
GREEN_KEY_LONG_VALUES = FUNCTION_KEY_VALUES

# Voltage Display (offset 0x383)
VOLTAGE_DISPLAY_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# Live Sub-tone Detection (offset 0x384)
LIVE_SUB_TONE_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# Spectrum Threshold (offset 0x385)
# Level to open squelch - typically not shown in CPS per DT's notes
SPECTRUM_THRESHOLD_VALUES = [
    ("0", 0), ("1", 1), ("2", 2), ("3", 3), ("4", 4),
    ("5", 5), ("6", 6), ("7", 7), ("8", 8), ("9", 9),
]

# Sub-tone PTT (offset 0x386)
# Enable pressing PTT from the DTMF list (e.g., EchoLink/Allstar)
SUB_TONE_PTT_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# TOT Warning (offset 0x387)
# Beep before TOT timeout
TOT_WARNING_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# Scan End behavior (offset 0x388)
SCAN_END_VALUES = [
    ("Continue", 0),
    ("Stop", 1),
]

# Scan Continue mode (offset 0x389)
# DT custom firmware: values from 0 to 31
# Old style scanner modes (TO/CO/SE) are gone and configurable by other options
SCAN_CONTINUE_VALUES = [
    ("0", 0), ("1", 1), ("2", 2), ("3", 3), ("4", 4), ("5", 5),
    ("6", 6), ("7", 7), ("8", 8), ("9", 9), ("10", 10),
    ("11", 11), ("12", 12), ("13", 13), ("14", 14), ("15", 15),
    ("16", 16), ("17", 17), ("18", 18), ("19", 19), ("20", 20),
    ("21", 21), ("22", 22), ("23", 23), ("24", 24), ("25", 25),
    ("26", 26), ("27", 27), ("28", 28), ("29", 29), ("30", 30),
    ("31", 31),
]

# Scan Return (offset 0x392)
SCAN_RETURN_CUSTOM_VALUES = [
    ("Original CH", 0),
    ("Current CH", 1),
    ("Last Call CH", 2),
]

# Callsign Lookup (offset 0x39B)
# Look up callsign and display in Call Log
CALLSIGN_LOOKUP_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# DMR Scan Speed (offset 0x39C)
DMR_SCAN_SPEED_VALUES = [
    ("Fast", 0),
    ("Medium", 1),
    ("Slow", 2),
]

# PTT Lock (offset 0x39D)
# DT custom firmware: 3 options
PTT_LOCK_VALUES = [
    ("Off", 0),
    ("When Locked", 1),
    ("Always", 2),
]

# Zone Channel Display (offset 0x39E)
# Show "Zone CH" on display
ZONE_CHANNEL_DISPLAY_VALUES = [
    ("Off", 0),
    ("On", 1),
]

# DMR Group ID Name (offset 0x39F)
# Show DMR group name if available
DMR_GID_NAME_VALUES = [
    ("Off", 0),
    ("On", 1),
]
