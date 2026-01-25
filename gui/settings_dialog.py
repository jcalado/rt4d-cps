"""Radio Settings Editor Dialog"""

from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QComboBox, QCheckBox,
    QPushButton, QGroupBox, QScrollArea, QWidget, QStyle
)
from PySide6.QtCore import Qt, Signal

from rt4d_codeplug.models import RadioSettings
from rt4d_codeplug.dropdowns import (
    VOICE_PROMPT_VALUES, KEY_BEEP_VALUES, KEY_LOCK_VALUES,
    DUAL_WATCH_VALUES, WORK_MODE_VALUES, TALKAROUND_VALUES,
    ALARM_TYPE_VALUES, LOCK_TIMER_VALUES, LED_ON_OFF_VALUES,
    LED_TIMER_VALUES, MENU_TIMER_VALUES,
    BACKLIGHT_BRIGHTNESS_VALUES, POWER_SAVE_START_VALUES,
    TX_PRIORITY_GLOBAL_VALUES, MAIN_PTT_VALUES, VFO_STEP_VALUES,
    MAIN_BAND_VALUES, DISPLAY_MODE_VALUES, CLOCK_MODE_VALUES,
    STARTUP_PICTURE_VALUES, TX_PROTECTION_VALUES, STARTUP_BEEP_VALUES,
    STARTUP_LABEL_VALUES,
    FREQUENCY_LOCK_VALUES, SCAN_DIRECTION_VALUES, SCAN_RETURN_VALUES,
    SCAN_MODE_VALUES, SCAN_DWELL_VALUES, FUNCTION_KEY_VALUES,
    SQUELCH_LEVEL_VALUES, BEEP_VALUES,
    LCD_CONTRAST_VALUES, DISPLAY_LINES_VALUES, DUAL_DISPLAY_VALUES,
    REMOTE_CONTROL_VALUES, HANG_TIME_VALUES, DISPLAY_ENABLE_VALUES,
    NOAA_CHANNEL_VALUES, REPEATER_DELAY_VALUES
)
# Custom firmware settings
from rt4d_codeplug.dropdowns import (
    SCAN_SPEED_ANALOG_VALUES, TX_BACKLIGHT_VALUES, GREEN_KEY_LONG_VALUES,
    VOLTAGE_DISPLAY_VALUES, LIVE_SUB_TONE_VALUES, SPECTRUM_THRESHOLD_VALUES,
    SUB_TONE_PTT_VALUES, TOT_WARNING_VALUES, SCAN_END_VALUES,
    SCAN_CONTINUE_VALUES, SCAN_RETURN_CUSTOM_VALUES, CALLSIGN_LOOKUP_VALUES,
    DMR_SCAN_SPEED_VALUES, PTT_LOCK_VALUES, ZONE_CHANNEL_DISPLAY_VALUES,
    DMR_GID_NAME_VALUES
)


class SettingsDialog(QDialog):
    """Dialog for editing radio settings"""

    def __init__(self, settings: Optional[RadioSettings], parent=None):
        super().__init__(parent)
        self.settings = settings or RadioSettings()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Radio Settings")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

        # Title/Info
        info_label = QLabel("<b>Advanced Settings</b><br/>"
                           "Basic settings (Identity, Audio, Display, Operation) are available in the main Settings tab.")
        info_label.setWordWrap(True)
        scroll_layout.addWidget(info_label)

        # Startup/Boot Options section
        startup_group = QGroupBox("Startup/Boot Options")
        startup_layout = QFormLayout()

        self.combo_startup_picture = QComboBox()
        for label, value in STARTUP_PICTURE_VALUES:
            self.combo_startup_picture.addItem(label, value)
        startup_layout.addRow("Startup Picture:", self.combo_startup_picture)

        self.combo_tx_protection = QComboBox()
        for label, value in TX_PROTECTION_VALUES:
            self.combo_tx_protection.addItem(label, value)
        startup_layout.addRow("TX Protection:", self.combo_tx_protection)

        self.combo_startup_beep = QComboBox()
        for label, value in STARTUP_BEEP_VALUES:
            self.combo_startup_beep.addItem(label, value)
        startup_layout.addRow("Startup Beep:", self.combo_startup_beep)

        self.combo_startup_label = QComboBox()
        for label, value in STARTUP_LABEL_VALUES:
            self.combo_startup_label.addItem(label, value)
        startup_layout.addRow("Startup Label:", self.combo_startup_label)

        self.spin_startup_line = QSpinBox()
        self.spin_startup_line.setRange(0, 255)
        startup_layout.addRow("Display Line:", self.spin_startup_line)

        self.spin_startup_column = QSpinBox()
        self.spin_startup_column.setRange(0, 255)
        startup_layout.addRow("Display Column:", self.spin_startup_column)

        startup_group.setLayout(startup_layout)
        scroll_layout.addWidget(startup_group)

        # Radio Clock section
        self.clock_group = QGroupBox("Radio Clock")
        clock_layout = QFormLayout()

        time_layout = QHBoxLayout()
        self.spin_clock_hour = QSpinBox()
        self.spin_clock_hour.setRange(0, 23)
        time_layout.addWidget(QLabel("Hour:"))
        time_layout.addWidget(self.spin_clock_hour)

        self.spin_clock_minute = QSpinBox()
        self.spin_clock_minute.setRange(0, 59)
        time_layout.addWidget(QLabel("Minute:"))
        time_layout.addWidget(self.spin_clock_minute)

        self.spin_clock_second = QSpinBox()
        self.spin_clock_second.setRange(0, 59)
        time_layout.addWidget(QLabel("Second:"))
        time_layout.addWidget(self.spin_clock_second)

        clock_layout.addRow("Current Time:", time_layout)

        self.clock_group.setLayout(clock_layout)
        scroll_layout.addWidget(self.clock_group)

        # Frequency Lock Ranges section
        freq_lock_group = QGroupBox("Frequency Lock Ranges")
        freq_lock_layout = QFormLayout()

        # Range 1
        self.combo_freq_lock_1 = QComboBox()
        for label, value in FREQUENCY_LOCK_VALUES:
            self.combo_freq_lock_1.addItem(label, value)
        freq_lock_layout.addRow("Range 1 Mode:", self.combo_freq_lock_1)

        self.spin_freq_lock_1_start = QSpinBox()
        self.spin_freq_lock_1_start.setRange(0, 999)
        self.spin_freq_lock_1_start.setSuffix(" MHz")
        freq_lock_layout.addRow("Range 1 Start:", self.spin_freq_lock_1_start)

        self.spin_freq_lock_1_end = QSpinBox()
        self.spin_freq_lock_1_end.setRange(0, 999)
        self.spin_freq_lock_1_end.setSuffix(" MHz")
        freq_lock_layout.addRow("Range 1 End:", self.spin_freq_lock_1_end)

        # Range 2
        self.combo_freq_lock_2 = QComboBox()
        for label, value in FREQUENCY_LOCK_VALUES:
            self.combo_freq_lock_2.addItem(label, value)
        freq_lock_layout.addRow("Range 2 Mode:", self.combo_freq_lock_2)

        self.spin_freq_lock_2_start = QSpinBox()
        self.spin_freq_lock_2_start.setRange(0, 999)
        self.spin_freq_lock_2_start.setSuffix(" MHz")
        freq_lock_layout.addRow("Range 2 Start:", self.spin_freq_lock_2_start)

        self.spin_freq_lock_2_end = QSpinBox()
        self.spin_freq_lock_2_end.setRange(0, 999)
        self.spin_freq_lock_2_end.setSuffix(" MHz")
        freq_lock_layout.addRow("Range 2 End:", self.spin_freq_lock_2_end)

        # Range 3
        self.combo_freq_lock_3 = QComboBox()
        for label, value in FREQUENCY_LOCK_VALUES:
            self.combo_freq_lock_3.addItem(label, value)
        freq_lock_layout.addRow("Range 3 Mode:", self.combo_freq_lock_3)

        self.spin_freq_lock_3_start = QSpinBox()
        self.spin_freq_lock_3_start.setRange(0, 999)
        self.spin_freq_lock_3_start.setSuffix(" MHz")
        freq_lock_layout.addRow("Range 3 Start:", self.spin_freq_lock_3_start)

        self.spin_freq_lock_3_end = QSpinBox()
        self.spin_freq_lock_3_end.setRange(0, 999)
        self.spin_freq_lock_3_end.setSuffix(" MHz")
        freq_lock_layout.addRow("Range 3 End:", self.spin_freq_lock_3_end)

        # Range 4
        self.combo_freq_lock_4 = QComboBox()
        for label, value in FREQUENCY_LOCK_VALUES:
            self.combo_freq_lock_4.addItem(label, value)
        freq_lock_layout.addRow("Range 4 Mode:", self.combo_freq_lock_4)

        self.spin_freq_lock_4_start = QSpinBox()
        self.spin_freq_lock_4_start.setRange(0, 999)
        self.spin_freq_lock_4_start.setSuffix(" MHz")
        freq_lock_layout.addRow("Range 4 Start:", self.spin_freq_lock_4_start)

        self.spin_freq_lock_4_end = QSpinBox()
        self.spin_freq_lock_4_end.setRange(0, 999)
        self.spin_freq_lock_4_end.setSuffix(" MHz")
        freq_lock_layout.addRow("Range 4 End:", self.spin_freq_lock_4_end)

        freq_lock_group.setLayout(freq_lock_layout)
        scroll_layout.addWidget(freq_lock_group)

        # Scan Options section
        scan_group = QGroupBox("Scan Options")
        scan_layout = QFormLayout()

        self.combo_scan_direction = QComboBox()
        for label, value in SCAN_DIRECTION_VALUES:
            self.combo_scan_direction.addItem(label, value)
        scan_layout.addRow("Scan Direction:", self.combo_scan_direction)

        self.combo_scan_mode = QComboBox()
        for label, value in SCAN_MODE_VALUES:
            self.combo_scan_mode.addItem(label, value)
        scan_layout.addRow("Scan Mode:", self.combo_scan_mode)

        self.combo_scan_return = QComboBox()
        for label, value in SCAN_RETURN_VALUES:
            self.combo_scan_return.addItem(label, value)
        scan_layout.addRow("Scan Return:", self.combo_scan_return)

        self.combo_scan_dwell = QComboBox()
        for label, value in SCAN_DWELL_VALUES:
            self.combo_scan_dwell.addItem(label, value)
        scan_layout.addRow("Scan Dwell:", self.combo_scan_dwell)

        scan_group.setLayout(scan_layout)
        scroll_layout.addWidget(scan_group)

        # Analog Audio Settings section
        analog_audio_group = QGroupBox("Analog Audio Settings")
        analog_audio_layout = QFormLayout()

        self.combo_squelch_level = QComboBox()
        for label, value in SQUELCH_LEVEL_VALUES:
            self.combo_squelch_level.addItem(label, value)
        analog_audio_layout.addRow("Analog Squelch:", self.combo_squelch_level)

        self.spin_tx_mic_gain = QSpinBox()
        self.spin_tx_mic_gain.setRange(0, 31)
        analog_audio_layout.addRow("TX Mic Gain (0-31):", self.spin_tx_mic_gain)

        self.spin_rx_speaker_volume = QSpinBox()
        self.spin_rx_speaker_volume.setRange(0, 63)
        analog_audio_layout.addRow("RX Speaker Volume (0-63):", self.spin_rx_speaker_volume)

        self.combo_tx_start_beep = QComboBox()
        for label, value in BEEP_VALUES:
            self.combo_tx_start_beep.addItem(label, value)
        analog_audio_layout.addRow("TX Start Beep:", self.combo_tx_start_beep)

        self.combo_roger_beep = QComboBox()
        for label, value in BEEP_VALUES:
            self.combo_roger_beep.addItem(label, value)
        analog_audio_layout.addRow("Roger Beep:", self.combo_roger_beep)

        self.spin_tone_frequency = QSpinBox()
        self.spin_tone_frequency.setRange(0, 65535)
        self.spin_tone_frequency.setSuffix(" Hz")
        analog_audio_layout.addRow("Tone Frequency:", self.spin_tone_frequency)

        analog_audio_group.setLayout(analog_audio_layout)
        scroll_layout.addWidget(analog_audio_group)

        # DMR Audio Settings section
        dmr_audio_group = QGroupBox("DMR Audio Settings")
        dmr_audio_layout = QFormLayout()

        self.combo_digital_squelch = QComboBox()
        for label, value in SQUELCH_LEVEL_VALUES:
            self.combo_digital_squelch.addItem(label, value)
        dmr_audio_layout.addRow("Digital Squelch:", self.combo_digital_squelch)

        self.spin_call_mic_gain = QSpinBox()
        self.spin_call_mic_gain.setRange(0, 24)
        dmr_audio_layout.addRow("Call Mic Gain (0-24):", self.spin_call_mic_gain)

        self.spin_call_speaker_volume = QSpinBox()
        self.spin_call_speaker_volume.setRange(0, 24)
        dmr_audio_layout.addRow("Call Speaker Volume (0-24):", self.spin_call_speaker_volume)

        self.combo_call_start_beep = QComboBox()
        for label, value in BEEP_VALUES:
            self.combo_call_start_beep.addItem(label, value)
        dmr_audio_layout.addRow("Call Start Beep:", self.combo_call_start_beep)

        self.combo_call_end_beep = QComboBox()
        for label, value in BEEP_VALUES:
            self.combo_call_end_beep.addItem(label, value)
        dmr_audio_layout.addRow("Call End Beep:", self.combo_call_end_beep)

        dmr_audio_group.setLayout(dmr_audio_layout)
        scroll_layout.addWidget(dmr_audio_group)

        # Display Settings section
        display_settings_group = QGroupBox("Display Settings")
        display_settings_layout = QFormLayout()

        self.combo_lcd_contrast = QComboBox()
        for label, value in LCD_CONTRAST_VALUES:
            self.combo_lcd_contrast.addItem(label, value)
        display_settings_layout.addRow("LCD Contrast:", self.combo_lcd_contrast)

        self.combo_display_lines = QComboBox()
        for label, value in DISPLAY_LINES_VALUES:
            self.combo_display_lines.addItem(label, value)
        display_settings_layout.addRow("Frequency digits:", self.combo_display_lines)

        self.combo_dual_display_mode = QComboBox()
        for label, value in DUAL_DISPLAY_VALUES:
            self.combo_dual_display_mode.addItem(label, value)
        display_settings_layout.addRow("Dual Display:", self.combo_dual_display_mode)

        display_settings_group.setLayout(display_settings_layout)
        scroll_layout.addWidget(display_settings_group)

        # DMR Operation Settings section
        dmr_group = QGroupBox("DMR Operation Settings")
        dmr_layout = QFormLayout()

        self.combo_remote_control = QComboBox()
        for label, value in REMOTE_CONTROL_VALUES:
            self.combo_remote_control.addItem(label, value)
        dmr_layout.addRow("Remote Control:", self.combo_remote_control)

        self.combo_group_call_hang_time = QComboBox()
        for label, value in HANG_TIME_VALUES:
            self.combo_group_call_hang_time.addItem(label, value)
        dmr_layout.addRow("Group Call Hang Time:", self.combo_group_call_hang_time)

        self.combo_private_call_hang_time = QComboBox()
        for label, value in HANG_TIME_VALUES:
            self.combo_private_call_hang_time.addItem(label, value)
        dmr_layout.addRow("Private Call Hang Time:", self.combo_private_call_hang_time)

        self.combo_call_group_display = QComboBox()
        for label, value in DISPLAY_ENABLE_VALUES:
            self.combo_call_group_display.addItem(label, value)
        dmr_layout.addRow("Show Call Group:", self.combo_call_group_display)

        dmr_group.setLayout(dmr_layout)
        scroll_layout.addWidget(dmr_group)

        # Advanced Features section
        advanced_group = QGroupBox("Advanced Features")
        advanced_layout = QFormLayout()

        self.combo_noaa_channel = QComboBox()
        for label, value in NOAA_CHANNEL_VALUES:
            self.combo_noaa_channel.addItem(label, value)
        advanced_layout.addRow("NOAA Weather Channel:", self.combo_noaa_channel)

        self.spin_detection_range = QSpinBox()
        self.spin_detection_range.setRange(0, 65535)
        advanced_layout.addRow("Detection Range:", self.spin_detection_range)

        self.combo_relay_delay = QComboBox()
        for label, value in REPEATER_DELAY_VALUES:
            self.combo_relay_delay.addItem(label, value)
        advanced_layout.addRow("Repeater Delay:", self.combo_relay_delay)

        self.spin_glitch_filter = QSpinBox()
        self.spin_glitch_filter.setRange(0, 255)
        advanced_layout.addRow("Glitch Filter:", self.spin_glitch_filter)

        advanced_group.setLayout(advanced_layout)
        scroll_layout.addWidget(advanced_group)

        # Function Keys section
        funckeys_group = QGroupBox("Function Keys")
        funckeys_layout = QFormLayout()

        # FS1 button
        self.combo_key_fs1_short = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_fs1_short.addItem(display_label, value)
        funckeys_layout.addRow("FS1 (Short Press):", self.combo_key_fs1_short)

        self.combo_key_fs1_long = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_fs1_long.addItem(display_label, value)
        funckeys_layout.addRow("FS1 (Long Press):", self.combo_key_fs1_long)

        # FS2 button
        self.combo_key_fs2_short = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_fs2_short.addItem(display_label, value)
        funckeys_layout.addRow("FS2 (Short Press):", self.combo_key_fs2_short)

        self.combo_key_fs2_long = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_fs2_long.addItem(display_label, value)
        funckeys_layout.addRow("FS2 (Long Press):", self.combo_key_fs2_long)

        # Numeric keys 0-9
        self.combo_key_0 = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_0.addItem(display_label, value)
        funckeys_layout.addRow("Key 0:", self.combo_key_0)

        self.combo_key_1 = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_1.addItem(display_label, value)
        funckeys_layout.addRow("Key 1:", self.combo_key_1)

        self.combo_key_2 = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_2.addItem(display_label, value)
        funckeys_layout.addRow("Key 2:", self.combo_key_2)

        self.combo_key_3 = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_3.addItem(display_label, value)
        funckeys_layout.addRow("Key 3:", self.combo_key_3)

        self.combo_key_4 = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_4.addItem(display_label, value)
        funckeys_layout.addRow("Key 4:", self.combo_key_4)

        self.combo_key_5 = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_5.addItem(display_label, value)
        funckeys_layout.addRow("Key 5:", self.combo_key_5)

        self.combo_key_6 = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_6.addItem(display_label, value)
        funckeys_layout.addRow("Key 6:", self.combo_key_6)

        self.combo_key_7 = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_7.addItem(display_label, value)
        funckeys_layout.addRow("Key 7:", self.combo_key_7)

        self.combo_key_8 = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_8.addItem(display_label, value)
        funckeys_layout.addRow("Key 8:", self.combo_key_8)

        self.combo_key_9 = QComboBox()
        for label, value in FUNCTION_KEY_VALUES:
            display_label = self._get_function_key_label(label, value)
            self.combo_key_9.addItem(display_label, value)
        funckeys_layout.addRow("Key 9:", self.combo_key_9)

        funckeys_group.setLayout(funckeys_layout)
        scroll_layout.addWidget(funckeys_group)

        scroll_layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        button_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_cancel)

        main_layout.addLayout(button_layout)

        self._apply_beta41_visibility()

    def _set_combo_value(self, combo, value):
        """Helper method to set combo box to matching value"""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                break

    def _get_function_key_label(self, label, value):
        """Return beta41-aware label for function key."""
        if label == "Color Code Detect" and self.settings and self.settings.beta41:
            return "Talker Alias"
        return label

    def _apply_beta41_visibility(self):
        """Apply visibility based on beta41 flag."""
        if self.settings and self.settings.beta41:
            self.clock_group.setVisible(False)
        else:
            self.clock_group.setVisible(True)

    def load_settings(self):
        """Load settings into form"""
        # Startup/Boot settings combo boxes
        combo_settings = [
            (self.combo_startup_picture, self.settings.startup_picture_enable),
            (self.combo_tx_protection, self.settings.tx_protection),
            (self.combo_startup_beep, self.settings.startup_beep_enable),
            (self.combo_startup_label, self.settings.startup_label_enable),
        ]
        for combo, value in combo_settings:
            self._set_combo_value(combo, value)
        self.spin_startup_line.setValue(self.settings.startup_display_line)
        self.spin_startup_column.setValue(self.settings.startup_display_column)

        # Radio clock - convert seconds to hour/minute/second
        total_seconds = self.settings.radio_time_seconds
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        self.spin_clock_hour.setValue(hours)
        self.spin_clock_minute.setValue(minutes)
        self.spin_clock_second.setValue(seconds)

        # Frequency lock ranges
        freq_lock_combos = [
            (self.combo_freq_lock_1, self.settings.freq_lock_1_mode),
            (self.combo_freq_lock_2, self.settings.freq_lock_2_mode),
            (self.combo_freq_lock_3, self.settings.freq_lock_3_mode),
            (self.combo_freq_lock_4, self.settings.freq_lock_4_mode),
        ]
        for combo, value in freq_lock_combos:
            self._set_combo_value(combo, value)
        self.spin_freq_lock_1_start.setValue(self.settings.freq_lock_1_start)
        self.spin_freq_lock_1_end.setValue(self.settings.freq_lock_1_end)
        self.spin_freq_lock_2_start.setValue(self.settings.freq_lock_2_start)
        self.spin_freq_lock_2_end.setValue(self.settings.freq_lock_2_end)
        self.spin_freq_lock_3_start.setValue(self.settings.freq_lock_3_start)
        self.spin_freq_lock_3_end.setValue(self.settings.freq_lock_3_end)
        self.spin_freq_lock_4_start.setValue(self.settings.freq_lock_4_start)
        self.spin_freq_lock_4_end.setValue(self.settings.freq_lock_4_end)

        # All other combo boxes
        other_combos = [
            # Scan settings
            (self.combo_scan_direction, self.settings.scan_direction),
            (self.combo_scan_mode, self.settings.scan_mode),
            (self.combo_scan_return, self.settings.scan_return),
            (self.combo_scan_dwell, self.settings.scan_dwell),
            # Analog audio settings
            (self.combo_squelch_level, self.settings.squelch_level),
            (self.combo_tx_start_beep, self.settings.tx_start_beep),
            (self.combo_roger_beep, self.settings.roger_beep),
            # DMR audio settings
            (self.combo_digital_squelch, self.settings.digital_squelch),
            (self.combo_call_start_beep, self.settings.call_start_beep),
            (self.combo_call_end_beep, self.settings.call_end_beep),
            # Display settings
            (self.combo_lcd_contrast, self.settings.lcd_contrast),
            (self.combo_display_lines, self.settings.display_lines),
            (self.combo_dual_display_mode, self.settings.dual_display_mode),
            # DMR operation settings
            (self.combo_remote_control, self.settings.remote_control),
            (self.combo_group_call_hang_time, self.settings.group_call_hang_time),
            (self.combo_private_call_hang_time, self.settings.private_call_hang_time),
            (self.combo_call_group_display, self.settings.call_group_display),
            # Advanced features
            (self.combo_noaa_channel, self.settings.noaa_channel),
            # Function keys
            (self.combo_key_fs1_short, self.settings.key_fs1_short),
            (self.combo_key_fs1_long, self.settings.key_fs1_long),
            (self.combo_key_fs2_short, self.settings.key_fs2_short),
            (self.combo_key_fs2_long, self.settings.key_fs2_long),
            (self.combo_key_0, self.settings.key_0),
            (self.combo_key_1, self.settings.key_1),
            (self.combo_key_2, self.settings.key_2),
            (self.combo_key_3, self.settings.key_3),
            (self.combo_key_4, self.settings.key_4),
            (self.combo_key_5, self.settings.key_5),
            (self.combo_key_6, self.settings.key_6),
            (self.combo_key_7, self.settings.key_7),
            (self.combo_key_8, self.settings.key_8),
            (self.combo_key_9, self.settings.key_9),
        ]
        for combo, value in other_combos:
            self._set_combo_value(combo, value)

        # Spin boxes
        self.spin_tx_mic_gain.setValue(self.settings.tx_mic_gain)
        self.spin_rx_speaker_volume.setValue(self.settings.rx_speaker_volume)
        self.spin_tone_frequency.setValue(self.settings.tone_frequency)
        self.spin_call_mic_gain.setValue(self.settings.call_mic_gain)
        self.spin_call_speaker_volume.setValue(self.settings.call_speaker_volume)
        self.spin_detection_range.setValue(self.settings.detection_range)
        self._set_combo_value(self.combo_relay_delay, self.settings.relay_delay)
        self.spin_glitch_filter.setValue(self.settings.glitch_filter)

    def save_settings(self) -> RadioSettings:
        """Save form data to settings"""
        # List of (attribute_name, combo_box/spin_box) pairs
        combo_mappings = [
            # Startup/Boot settings
            ('startup_picture_enable', self.combo_startup_picture),
            ('tx_protection', self.combo_tx_protection),
            ('startup_beep_enable', self.combo_startup_beep),
            ('startup_label_enable', self.combo_startup_label),
            # Frequency lock ranges
            ('freq_lock_1_mode', self.combo_freq_lock_1),
            ('freq_lock_2_mode', self.combo_freq_lock_2),
            ('freq_lock_3_mode', self.combo_freq_lock_3),
            ('freq_lock_4_mode', self.combo_freq_lock_4),
            # Scan settings
            ('scan_direction', self.combo_scan_direction),
            ('scan_mode', self.combo_scan_mode),
            ('scan_return', self.combo_scan_return),
            ('scan_dwell', self.combo_scan_dwell),
            # Analog audio settings
            ('squelch_level', self.combo_squelch_level),
            ('tx_start_beep', self.combo_tx_start_beep),
            ('roger_beep', self.combo_roger_beep),
            # DMR audio settings
            ('digital_squelch', self.combo_digital_squelch),
            ('call_start_beep', self.combo_call_start_beep),
            ('call_end_beep', self.combo_call_end_beep),
            # Display settings
            ('lcd_contrast', self.combo_lcd_contrast),
            ('display_lines', self.combo_display_lines),
            ('dual_display_mode', self.combo_dual_display_mode),
            # DMR operation settings
            ('remote_control', self.combo_remote_control),
            ('group_call_hang_time', self.combo_group_call_hang_time),
            ('private_call_hang_time', self.combo_private_call_hang_time),
            ('call_group_display', self.combo_call_group_display),
            # Advanced features
            ('noaa_channel', self.combo_noaa_channel),
            # Function keys
            ('key_fs1_short', self.combo_key_fs1_short),
            ('key_fs1_long', self.combo_key_fs1_long),
            ('key_fs2_short', self.combo_key_fs2_short),
            ('key_fs2_long', self.combo_key_fs2_long),
            ('key_0', self.combo_key_0),
            ('key_1', self.combo_key_1),
            ('key_2', self.combo_key_2),
            ('key_3', self.combo_key_3),
            ('key_4', self.combo_key_4),
            ('key_5', self.combo_key_5),
            ('key_6', self.combo_key_6),
            ('key_7', self.combo_key_7),
            ('key_8', self.combo_key_8),
            ('key_9', self.combo_key_9),
        ]

        # Save all combo box values
        for attr_name, combo in combo_mappings:
            setattr(self.settings, attr_name, combo.currentData())

        # Spin boxes
        self.settings.startup_display_line = self.spin_startup_line.value()
        self.settings.startup_display_column = self.spin_startup_column.value()
        self.settings.freq_lock_1_start = self.spin_freq_lock_1_start.value()
        self.settings.freq_lock_1_end = self.spin_freq_lock_1_end.value()
        self.settings.freq_lock_2_start = self.spin_freq_lock_2_start.value()
        self.settings.freq_lock_2_end = self.spin_freq_lock_2_end.value()
        self.settings.freq_lock_3_start = self.spin_freq_lock_3_start.value()
        self.settings.freq_lock_3_end = self.spin_freq_lock_3_end.value()
        self.settings.freq_lock_4_start = self.spin_freq_lock_4_start.value()
        self.settings.freq_lock_4_end = self.spin_freq_lock_4_end.value()
        self.settings.tx_mic_gain = self.spin_tx_mic_gain.value()
        self.settings.rx_speaker_volume = self.spin_rx_speaker_volume.value()
        self.settings.tone_frequency = self.spin_tone_frequency.value()
        self.settings.call_mic_gain = self.spin_call_mic_gain.value()
        self.settings.call_speaker_volume = self.spin_call_speaker_volume.value()
        self.settings.detection_range = self.spin_detection_range.value()
        self.settings.relay_delay = self.combo_relay_delay.currentData()
        self.settings.glitch_filter = self.spin_glitch_filter.value()

        # Radio clock - convert hour/minute/second to total seconds
        hours = self.spin_clock_hour.value()
        minutes = self.spin_clock_minute.value()
        seconds = self.spin_clock_second.value()
        self.settings.radio_time_seconds = hours * 3600 + minutes * 60 + seconds

        return self.settings

    def accept(self):
        """Accept and save settings"""
        self.save_settings()
        super().accept()


class CustomFirmwareDialog(QDialog):
    """Dialog for editing DT custom firmware settings"""

    def __init__(self, settings: Optional[RadioSettings], parent=None):
        super().__init__(parent)
        self.settings = settings or RadioSettings()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("DT Custom Firmware Settings")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Warning/Info label
        info_label = QLabel(
            "<b>REFW Settings</b><br/><br/>"
            "<i>These settings are only available with REFW custom firmware. "
            "If you are using stock firmware, these values will be ignored by the radio.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("QLabel { background-color: #fff3cd; color: #856404; border: 1px solid #ffc107; padding: 10px; border-radius: 4px; }")
        main_layout.addWidget(info_label)

        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

        # Scan Settings section
        scan_group = QGroupBox("Scan Settings")
        scan_layout = QFormLayout()

        self.combo_scan_speed_analog = QComboBox()
        for label, value in SCAN_SPEED_ANALOG_VALUES:
            self.combo_scan_speed_analog.addItem(label, value)
        scan_layout.addRow("Analog Scan Speed:", self.combo_scan_speed_analog)

        self.combo_dmr_scan_speed = QComboBox()
        for label, value in DMR_SCAN_SPEED_VALUES:
            self.combo_dmr_scan_speed.addItem(label, value)
        scan_layout.addRow("DMR Scan Speed:", self.combo_dmr_scan_speed)

        self.combo_scan_end = QComboBox()
        for label, value in SCAN_END_VALUES:
            self.combo_scan_end.addItem(label, value)
        scan_layout.addRow("Scan End:", self.combo_scan_end)

        self.combo_scan_continue = QComboBox()
        for label, value in SCAN_CONTINUE_VALUES:
            self.combo_scan_continue.addItem(label, value)
        scan_layout.addRow("Scan Continue:", self.combo_scan_continue)

        self.combo_scan_return_custom = QComboBox()
        for label, value in SCAN_RETURN_CUSTOM_VALUES:
            self.combo_scan_return_custom.addItem(label, value)
        scan_layout.addRow("Scan Return:", self.combo_scan_return_custom)

        scan_group.setLayout(scan_layout)
        scroll_layout.addWidget(scan_group)

        # Display Settings section
        display_group = QGroupBox("Display Settings")
        display_layout = QFormLayout()

        self.combo_tx_backlight = QComboBox()
        for label, value in TX_BACKLIGHT_VALUES:
            self.combo_tx_backlight.addItem(label, value)
        display_layout.addRow("TX Backlight:", self.combo_tx_backlight)

        self.combo_voltage_display = QComboBox()
        for label, value in VOLTAGE_DISPLAY_VALUES:
            self.combo_voltage_display.addItem(label, value)
        display_layout.addRow("Voltage Display:", self.combo_voltage_display)

        self.combo_zone_channel_display = QComboBox()
        for label, value in ZONE_CHANNEL_DISPLAY_VALUES:
            self.combo_zone_channel_display.addItem(label, value)
        display_layout.addRow("Show Zone CH:", self.combo_zone_channel_display)

        display_group.setLayout(display_layout)
        scroll_layout.addWidget(display_group)

        # Audio & Tone Settings section
        audio_group = QGroupBox("Audio & Tone Settings")
        audio_layout = QFormLayout()

        self.combo_live_sub_tone = QComboBox()
        for label, value in LIVE_SUB_TONE_VALUES:
            self.combo_live_sub_tone.addItem(label, value)
        audio_layout.addRow("Live Sub-tone:", self.combo_live_sub_tone)

        self.combo_tot_warning = QComboBox()
        for label, value in TOT_WARNING_VALUES:
            self.combo_tot_warning.addItem(label, value)
        audio_layout.addRow("TOT Warning Beep:", self.combo_tot_warning)

        audio_group.setLayout(audio_layout)
        scroll_layout.addWidget(audio_group)

        # Function Keys section
        keys_group = QGroupBox("Function Keys")
        keys_layout = QFormLayout()

        self.combo_green_key_long = QComboBox()
        for label, value in GREEN_KEY_LONG_VALUES:
            self.combo_green_key_long.addItem(label, value)
        keys_layout.addRow("Green Key (Long Press):", self.combo_green_key_long)

        keys_group.setLayout(keys_layout)
        scroll_layout.addWidget(keys_group)

        # PTT & DTMF Settings section
        ptt_group = QGroupBox("PTT & DTMF Settings")
        ptt_layout = QFormLayout()

        self.combo_sub_tone_ptt = QComboBox()
        for label, value in SUB_TONE_PTT_VALUES:
            self.combo_sub_tone_ptt.addItem(label, value)
        ptt_layout.addRow("Sub-tone PTT:", self.combo_sub_tone_ptt)

        self.combo_ptt_lock = QComboBox()
        for label, value in PTT_LOCK_VALUES:
            self.combo_ptt_lock.addItem(label, value)
        ptt_layout.addRow("PTT Lock:", self.combo_ptt_lock)

        ptt_group.setLayout(ptt_layout)
        scroll_layout.addWidget(ptt_group)

        # DMR Settings section
        dmr_group = QGroupBox("DMR Settings")
        dmr_layout = QFormLayout()

        self.combo_dmr_gid_name = QComboBox()
        for label, value in DMR_GID_NAME_VALUES:
            self.combo_dmr_gid_name.addItem(label, value)
        self.label_dmr_gid_name = QLabel("Show DMR Group Name:")
        dmr_layout.addRow(self.label_dmr_gid_name, self.combo_dmr_gid_name)

        self.combo_callsign_lookup = QComboBox()
        for label, value in CALLSIGN_LOOKUP_VALUES:
            self.combo_callsign_lookup.addItem(label, value)
        dmr_layout.addRow("Callsign Lookup:", self.combo_callsign_lookup)

        dmr_group.setLayout(dmr_layout)
        scroll_layout.addWidget(dmr_group)

        # Advanced Settings section
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QFormLayout()

        self.combo_spectrum_threshold = QComboBox()
        for label, value in SPECTRUM_THRESHOLD_VALUES:
            self.combo_spectrum_threshold.addItem(label, value)
        advanced_layout.addRow("Spectrum Threshold:", self.combo_spectrum_threshold)

        # VFO offsets (frequency offsets in Hz)
        self.spin_vfo_a_offset = QSpinBox()
        self.spin_vfo_a_offset.setRange(-100000000, 100000000)
        self.spin_vfo_a_offset.setSuffix(" Hz")
        advanced_layout.addRow("VFO A Offset:", self.spin_vfo_a_offset)

        self.spin_vfo_b_offset = QSpinBox()
        self.spin_vfo_b_offset.setRange(-100000000, 100000000)
        self.spin_vfo_b_offset.setSuffix(" Hz")
        advanced_layout.addRow("VFO B Offset:", self.spin_vfo_b_offset)

        advanced_group.setLayout(advanced_layout)
        scroll_layout.addWidget(advanced_group)

        scroll_layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        button_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_cancel)

        main_layout.addLayout(button_layout)

        self._apply_beta41_visibility()

    def _set_combo_value(self, combo, value):
        """Helper method to set combo box to matching value"""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                break

    def _apply_beta41_visibility(self):
        """Apply visibility based on beta41 flag."""
        if self.settings and self.settings.beta41:
            self.combo_dmr_gid_name.setVisible(False)
            self.label_dmr_gid_name.setVisible(False)
        else:
            self.combo_dmr_gid_name.setVisible(True)
            self.label_dmr_gid_name.setVisible(True)

    def load_settings(self):
        """Load settings into form"""
        # List of (combo_box, settings_value) pairs
        combo_settings = [
            # Scan settings
            (self.combo_scan_speed_analog, self.settings.scan_speed_analog),
            (self.combo_dmr_scan_speed, self.settings.dmr_scan_speed),
            (self.combo_scan_end, self.settings.scan_end),
            (self.combo_scan_continue, self.settings.scan_continue),
            (self.combo_scan_return_custom, self.settings.scan_return),
            # Display settings
            (self.combo_tx_backlight, self.settings.tx_backlight),
            (self.combo_voltage_display, self.settings.voltage_display),
            (self.combo_zone_channel_display, self.settings.zone_channel_display),
            # Audio settings
            (self.combo_live_sub_tone, self.settings.live_sub_tone),
            (self.combo_tot_warning, self.settings.tot_warning),
            # Function keys
            (self.combo_green_key_long, self.settings.green_key_long),
            # PTT settings
            (self.combo_sub_tone_ptt, self.settings.sub_tone_ptt),
            (self.combo_ptt_lock, self.settings.ptt_lock),
            # DMR settings
            (self.combo_dmr_gid_name, self.settings.dmr_gid_name),
            (self.combo_callsign_lookup, self.settings.callsign_lookup),
            # Advanced settings
            (self.combo_spectrum_threshold, self.settings.spectrum_threshold),
        ]

        # Set all combo boxes
        for combo, value in combo_settings:
            self._set_combo_value(combo, value)

        # Spin boxes (non-combo settings)
        self.spin_vfo_a_offset.setValue(self.settings.vfo_a_offset)
        self.spin_vfo_b_offset.setValue(self.settings.vfo_b_offset)

    def save_settings(self) -> RadioSettings:
        """Save form data to settings"""
        # List of (attribute_name, combo_box) pairs for combo boxes
        combo_mappings = [
            # Scan settings
            ('scan_speed_analog', self.combo_scan_speed_analog),
            ('dmr_scan_speed', self.combo_dmr_scan_speed),
            ('scan_end', self.combo_scan_end),
            ('scan_continue', self.combo_scan_continue),
            ('scan_return', self.combo_scan_return_custom),
            # Display settings
            ('tx_backlight', self.combo_tx_backlight),
            ('voltage_display', self.combo_voltage_display),
            ('zone_channel_display', self.combo_zone_channel_display),
            # Audio settings
            ('live_sub_tone', self.combo_live_sub_tone),
            ('tot_warning', self.combo_tot_warning),
            # Function keys
            ('green_key_long', self.combo_green_key_long),
            # PTT settings
            ('sub_tone_ptt', self.combo_sub_tone_ptt),
            ('ptt_lock', self.combo_ptt_lock),
            # DMR settings
            ('dmr_gid_name', self.combo_dmr_gid_name),
            ('callsign_lookup', self.combo_callsign_lookup),
            # Advanced settings
            ('spectrum_threshold', self.combo_spectrum_threshold),
        ]

        # Save all combo box values
        for attr_name, combo in combo_mappings:
            setattr(self.settings, attr_name, combo.currentData())

        # Spin boxes (non-combo settings)
        self.settings.vfo_a_offset = self.spin_vfo_a_offset.value()
        self.settings.vfo_b_offset = self.spin_vfo_b_offset.value()

        return self.settings

    def accept(self):
        """Accept and save settings"""
        self.save_settings()
        super().accept()


class SettingsWidget(QWidget):
    """Widget for displaying settings in the main window"""

    data_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings: Optional[RadioSettings] = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Title
        title = QLabel("<h2>Radio Settings</h2>")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Advanced settings button at the top
        button_layout_top = QHBoxLayout()
        button_layout_top.addStretch()

        self.btn_edit_advanced = QPushButton(" Edit Advanced Settings...")
        self.btn_edit_advanced.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.btn_edit_advanced.setToolTip("Open full settings dialog for Function Keys, Frequency Lock Ranges, Radio Clock, and Scan settings")
        self.btn_edit_advanced.clicked.connect(self.open_settings_dialog)
        self.btn_edit_advanced.setStyleSheet("QPushButton { font-weight: bold; padding: 8px; }")
        button_layout_top.addWidget(self.btn_edit_advanced)

        self.btn_edit_custom_fw = QPushButton(" REFW Settings...")
        self.btn_edit_custom_fw.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.btn_edit_custom_fw.setToolTip("Open REFW settings (only applies if using custom firmware)")
        self.btn_edit_custom_fw.clicked.connect(self.open_custom_fw_dialog)
        self.btn_edit_custom_fw.setStyleSheet("QPushButton { font-weight: bold; padding: 8px; }")
        button_layout_top.addWidget(self.btn_edit_custom_fw)

        button_layout_top.addStretch()
        main_layout.addLayout(button_layout_top)

        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll)

        # Container widget
        container = QWidget()
        layout = QVBoxLayout()
        container.setLayout(layout)
        scroll.setWidget(container)

        # Identity section
        identity_group = QGroupBox("Identity")
        identity_layout = QFormLayout()

        self.edit_radio_name = QLineEdit()
        self.edit_radio_name.setMaxLength(16)
        self.edit_radio_name.textChanged.connect(self.on_settings_changed)
        identity_layout.addRow("Radio Name:", self.edit_radio_name)

        self.spin_radio_id = QSpinBox()
        self.spin_radio_id.setRange(1, 16777215)
        self.spin_radio_id.valueChanged.connect(self.on_settings_changed)
        identity_layout.addRow("Radio ID (DMR):", self.spin_radio_id)

        self.edit_startup_msg = QLineEdit()
        self.edit_startup_msg.setMaxLength(32)
        self.edit_startup_msg.textChanged.connect(self.on_settings_changed)
        identity_layout.addRow("Startup Message:", self.edit_startup_msg)

        # Password enable/disable checkbox
        self.check_password_enabled = QCheckBox("Enable Startup Password")
        self.check_password_enabled.stateChanged.connect(self.on_password_enabled_changed)
        identity_layout.addRow("", self.check_password_enabled)

        # Password field (only shown when enabled)
        pwd_layout = QHBoxLayout()
        self.edit_startup_pwd = QLineEdit()
        self.edit_startup_pwd.setMaxLength(16)
        self.edit_startup_pwd.setEchoMode(QLineEdit.Password)
        self.edit_startup_pwd.textChanged.connect(self.on_settings_changed)
        self.edit_startup_pwd.setEnabled(False)
        self.edit_startup_pwd.setPlaceholderText("Enter password (max 16 characters)")
        pwd_layout.addWidget(self.edit_startup_pwd)

        # Show/hide password button
        self.btn_show_pwd = QPushButton("Show")
        self.btn_show_pwd.setFixedWidth(60)
        self.btn_show_pwd.setEnabled(False)
        self.btn_show_pwd.setCheckable(True)
        self.btn_show_pwd.toggled.connect(self.on_show_password_toggled)
        pwd_layout.addWidget(self.btn_show_pwd)

        identity_layout.addRow("Password:", pwd_layout)

        identity_group.setLayout(identity_layout)
        layout.addWidget(identity_group)

        # Audio & UI section
        audio_group = QGroupBox("Audio & User Interface")
        audio_layout = QFormLayout()

        self.combo_voice_prompt = QComboBox()
        for label, value in VOICE_PROMPT_VALUES:
            self.combo_voice_prompt.addItem(label, value)
        self.combo_voice_prompt.currentIndexChanged.connect(self.on_settings_changed)
        audio_layout.addRow("Voice Prompt:", self.combo_voice_prompt)

        self.combo_key_beep = QComboBox()
        for label, value in KEY_BEEP_VALUES:
            self.combo_key_beep.addItem(label, value)
        self.combo_key_beep.currentIndexChanged.connect(self.on_settings_changed)
        audio_layout.addRow("Key Beep:", self.combo_key_beep)

        self.combo_key_lock = QComboBox()
        for label, value in KEY_LOCK_VALUES:
            self.combo_key_lock.addItem(label, value)
        self.combo_key_lock.currentIndexChanged.connect(self.on_settings_changed)
        audio_layout.addRow("Key Lock:", self.combo_key_lock)

        self.combo_lock_timer = QComboBox()
        for label, value in LOCK_TIMER_VALUES:
            self.combo_lock_timer.addItem(label, value)
        self.combo_lock_timer.currentIndexChanged.connect(self.on_settings_changed)
        audio_layout.addRow("Lock Timer:", self.combo_lock_timer)

        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)

        # Display section
        display_group = QGroupBox("Display Settings")
        display_layout = QFormLayout()

        self.combo_led_on_off = QComboBox()
        for label, value in LED_ON_OFF_VALUES:
            self.combo_led_on_off.addItem(label, value)
        self.combo_led_on_off.currentIndexChanged.connect(self.on_settings_changed)
        display_layout.addRow("LED On/Off:", self.combo_led_on_off)

        self.combo_led_timer = QComboBox()
        for label, value in LED_TIMER_VALUES:
            self.combo_led_timer.addItem(label, value)
        self.combo_led_timer.currentIndexChanged.connect(self.on_settings_changed)
        display_layout.addRow("LED Timer:", self.combo_led_timer)

        self.combo_backlight = QComboBox()
        for label, value in BACKLIGHT_BRIGHTNESS_VALUES:
            self.combo_backlight.addItem(label, value)
        self.combo_backlight.currentIndexChanged.connect(self.on_settings_changed)
        display_layout.addRow("Backlight Brightness:", self.combo_backlight)

        self.combo_menu_timer = QComboBox()
        for label, value in MENU_TIMER_VALUES:
            self.combo_menu_timer.addItem(label, value)
        self.combo_menu_timer.currentIndexChanged.connect(self.on_settings_changed)
        display_layout.addRow("Menu Timer:", self.combo_menu_timer)

        self.combo_display_mode_a = QComboBox()
        for label, value in DISPLAY_MODE_VALUES:
            self.combo_display_mode_a.addItem(label, value)
        self.combo_display_mode_a.currentIndexChanged.connect(self.on_settings_changed)
        display_layout.addRow("Display Mode (Band A):", self.combo_display_mode_a)

        self.combo_display_mode_b = QComboBox()
        for label, value in DISPLAY_MODE_VALUES:
            self.combo_display_mode_b.addItem(label, value)
        self.combo_display_mode_b.currentIndexChanged.connect(self.on_settings_changed)
        display_layout.addRow("Display Mode (Band B):", self.combo_display_mode_b)

        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        # Power section
        power_group = QGroupBox("Power Management")
        power_layout = QFormLayout()

        self.spin_power_save = QSpinBox()
        self.spin_power_save.setRange(0, 255)
        self.spin_power_save.valueChanged.connect(self.on_settings_changed)
        power_layout.addRow("Power Save Mode:", self.spin_power_save)

        self.combo_power_save_start = QComboBox()
        for label, value in POWER_SAVE_START_VALUES:
            self.combo_power_save_start.addItem(label, value)
        self.combo_power_save_start.currentIndexChanged.connect(self.on_settings_changed)
        power_layout.addRow("Power Save Start:", self.combo_power_save_start)

        self.check_apo = QCheckBox("Enable Auto Power Off")
        self.check_apo.stateChanged.connect(self.on_settings_changed)
        power_layout.addRow("", self.check_apo)

        power_group.setLayout(power_layout)
        layout.addWidget(power_group)

        # Operation section
        operation_group = QGroupBox("Operation Settings")
        operation_layout = QFormLayout()

        self.combo_dual_watch = QComboBox()
        for label, value in DUAL_WATCH_VALUES:
            self.combo_dual_watch.addItem(label, value)
        self.combo_dual_watch.currentIndexChanged.connect(self.on_settings_changed)
        operation_layout.addRow("Dual Watch:", self.combo_dual_watch)

        self.combo_talkaround = QComboBox()
        for label, value in TALKAROUND_VALUES:
            self.combo_talkaround.addItem(label, value)
        self.combo_talkaround.currentIndexChanged.connect(self.on_settings_changed)
        operation_layout.addRow("Talkaround:", self.combo_talkaround)

        self.combo_alarm_type = QComboBox()
        for label, value in ALARM_TYPE_VALUES:
            self.combo_alarm_type.addItem(label, value)
        self.combo_alarm_type.currentIndexChanged.connect(self.on_settings_changed)
        operation_layout.addRow("Alarm Type:", self.combo_alarm_type)

        self.combo_tx_priority = QComboBox()
        for label, value in TX_PRIORITY_GLOBAL_VALUES:
            self.combo_tx_priority.addItem(label, value)
        self.combo_tx_priority.currentIndexChanged.connect(self.on_settings_changed)
        operation_layout.addRow("TX Priority:", self.combo_tx_priority)

        self.combo_main_band = QComboBox()
        for label, value in MAIN_BAND_VALUES:
            self.combo_main_band.addItem(label, value)
        self.combo_main_band.currentIndexChanged.connect(self.on_settings_changed)
        operation_layout.addRow("Main Band:", self.combo_main_band)

        self.combo_main_ptt = QComboBox()
        for label, value in MAIN_PTT_VALUES:
            self.combo_main_ptt.addItem(label, value)
        self.combo_main_ptt.currentIndexChanged.connect(self.on_settings_changed)
        operation_layout.addRow("Main PTT:", self.combo_main_ptt)

        self.combo_vfo_step = QComboBox()
        for label, value in VFO_STEP_VALUES:
            self.combo_vfo_step.addItem(label, value)
        self.combo_vfo_step.currentIndexChanged.connect(self.on_settings_changed)
        operation_layout.addRow("VFO Step:", self.combo_vfo_step)

        self.combo_work_mode_a = QComboBox()
        for label, value in WORK_MODE_VALUES:
            self.combo_work_mode_a.addItem(label, value)
        self.combo_work_mode_a.currentIndexChanged.connect(self.on_settings_changed)
        operation_layout.addRow("Band A Mode:", self.combo_work_mode_a)

        self.spin_zone_a = QSpinBox()
        self.spin_zone_a.setRange(0, 255)
        self.spin_zone_a.valueChanged.connect(self.on_settings_changed)
        operation_layout.addRow("Band A Zone:", self.spin_zone_a)

        self.spin_channel_a = QSpinBox()
        self.spin_channel_a.setRange(1, 1024)
        self.spin_channel_a.valueChanged.connect(self.on_settings_changed)
        operation_layout.addRow("Band A Channel:", self.spin_channel_a)

        self.combo_work_mode_b = QComboBox()
        for label, value in WORK_MODE_VALUES:
            self.combo_work_mode_b.addItem(label, value)
        self.combo_work_mode_b.currentIndexChanged.connect(self.on_settings_changed)
        operation_layout.addRow("Band B Mode:", self.combo_work_mode_b)

        self.spin_zone_b = QSpinBox()
        self.spin_zone_b.setRange(0, 255)
        self.spin_zone_b.valueChanged.connect(self.on_settings_changed)
        operation_layout.addRow("Band B Zone:", self.spin_zone_b)

        self.spin_channel_b = QSpinBox()
        self.spin_channel_b.setRange(1, 1024)
        self.spin_channel_b.valueChanged.connect(self.on_settings_changed)
        operation_layout.addRow("Band B Channel:", self.spin_channel_b)

        operation_group.setLayout(operation_layout)
        layout.addWidget(operation_group)

        # Clocks/Timers section
        self.clock_group = QGroupBox("Programmable Clocks/Timers")
        clock_layout = QFormLayout()

        # Clock 1
        clock1_layout = QHBoxLayout()
        self.combo_clock_1_mode = QComboBox()
        for label, value in CLOCK_MODE_VALUES:
            self.combo_clock_1_mode.addItem(label, value)
        self.combo_clock_1_mode.currentIndexChanged.connect(self.on_settings_changed)
        clock1_layout.addWidget(self.combo_clock_1_mode)
        self.spin_clock_1_hour = QSpinBox()
        self.spin_clock_1_hour.setRange(0, 23)
        self.spin_clock_1_hour.setPrefix("H:")
        self.spin_clock_1_hour.valueChanged.connect(self.on_settings_changed)
        clock1_layout.addWidget(self.spin_clock_1_hour)
        self.spin_clock_1_minute = QSpinBox()
        self.spin_clock_1_minute.setRange(0, 59)
        self.spin_clock_1_minute.setPrefix("M:")
        self.spin_clock_1_minute.valueChanged.connect(self.on_settings_changed)
        clock1_layout.addWidget(self.spin_clock_1_minute)
        clock_layout.addRow("Clock 1:", clock1_layout)

        # Clock 2
        clock2_layout = QHBoxLayout()
        self.combo_clock_2_mode = QComboBox()
        for label, value in CLOCK_MODE_VALUES:
            self.combo_clock_2_mode.addItem(label, value)
        self.combo_clock_2_mode.currentIndexChanged.connect(self.on_settings_changed)
        clock2_layout.addWidget(self.combo_clock_2_mode)
        self.spin_clock_2_hour = QSpinBox()
        self.spin_clock_2_hour.setRange(0, 23)
        self.spin_clock_2_hour.setPrefix("H:")
        self.spin_clock_2_hour.valueChanged.connect(self.on_settings_changed)
        clock2_layout.addWidget(self.spin_clock_2_hour)
        self.spin_clock_2_minute = QSpinBox()
        self.spin_clock_2_minute.setRange(0, 59)
        self.spin_clock_2_minute.setPrefix("M:")
        self.spin_clock_2_minute.valueChanged.connect(self.on_settings_changed)
        clock2_layout.addWidget(self.spin_clock_2_minute)
        clock_layout.addRow("Clock 2:", clock2_layout)

        # Clock 3
        clock3_layout = QHBoxLayout()
        self.combo_clock_3_mode = QComboBox()
        for label, value in CLOCK_MODE_VALUES:
            self.combo_clock_3_mode.addItem(label, value)
        self.combo_clock_3_mode.currentIndexChanged.connect(self.on_settings_changed)
        clock3_layout.addWidget(self.combo_clock_3_mode)
        self.spin_clock_3_hour = QSpinBox()
        self.spin_clock_3_hour.setRange(0, 23)
        self.spin_clock_3_hour.setPrefix("H:")
        self.spin_clock_3_hour.valueChanged.connect(self.on_settings_changed)
        clock3_layout.addWidget(self.spin_clock_3_hour)
        self.spin_clock_3_minute = QSpinBox()
        self.spin_clock_3_minute.setRange(0, 59)
        self.spin_clock_3_minute.setPrefix("M:")
        self.spin_clock_3_minute.valueChanged.connect(self.on_settings_changed)
        clock3_layout.addWidget(self.spin_clock_3_minute)
        clock_layout.addRow("Clock 3:", clock3_layout)

        # Clock 4
        clock4_layout = QHBoxLayout()
        self.combo_clock_4_mode = QComboBox()
        for label, value in CLOCK_MODE_VALUES:
            self.combo_clock_4_mode.addItem(label, value)
        self.combo_clock_4_mode.currentIndexChanged.connect(self.on_settings_changed)
        clock4_layout.addWidget(self.combo_clock_4_mode)
        self.spin_clock_4_hour = QSpinBox()
        self.spin_clock_4_hour.setRange(0, 23)
        self.spin_clock_4_hour.setPrefix("H:")
        self.spin_clock_4_hour.valueChanged.connect(self.on_settings_changed)
        clock4_layout.addWidget(self.spin_clock_4_hour)
        self.spin_clock_4_minute = QSpinBox()
        self.spin_clock_4_minute.setRange(0, 59)
        self.spin_clock_4_minute.setPrefix("M:")
        self.spin_clock_4_minute.valueChanged.connect(self.on_settings_changed)
        clock4_layout.addWidget(self.spin_clock_4_minute)
        clock_layout.addRow("Clock 4:", clock4_layout)

        self.clock_group.setLayout(clock_layout)
        layout.addWidget(self.clock_group)

        # Startup/Boot Options section
        startup_group = QGroupBox("Startup/Boot Options")
        startup_layout = QFormLayout()

        self.combo_startup_picture_widget = QComboBox()
        for label, value in STARTUP_PICTURE_VALUES:
            self.combo_startup_picture_widget.addItem(label, value)
        self.combo_startup_picture_widget.currentIndexChanged.connect(self.on_settings_changed)
        startup_layout.addRow("Startup Picture:", self.combo_startup_picture_widget)

        self.combo_tx_protection_widget = QComboBox()
        for label, value in TX_PROTECTION_VALUES:
            self.combo_tx_protection_widget.addItem(label, value)
        self.combo_tx_protection_widget.currentIndexChanged.connect(self.on_settings_changed)
        startup_layout.addRow("TX Protection:", self.combo_tx_protection_widget)

        startup_group.setLayout(startup_layout)
        layout.addWidget(startup_group)

        layout.addStretch()

        # Initially disable all controls
        self.set_enabled(False)

    def on_password_enabled_changed(self, state):
        """Handle password enable/disable"""
        enabled = state == Qt.CheckState.Checked.value
        self.edit_startup_pwd.setEnabled(enabled)
        self.btn_show_pwd.setEnabled(enabled)

        # Update password_enable field in settings
        if self.settings:
            self.settings.password_enable = 1 if enabled else 0

        # Clear password if disabled
        if not enabled:
            self.edit_startup_pwd.clear()

        self.on_settings_changed()

    def on_show_password_toggled(self, checked):
        """Toggle password visibility"""
        if checked:
            self.edit_startup_pwd.setEchoMode(QLineEdit.Normal)
            self.btn_show_pwd.setText("Hide")
        else:
            self.edit_startup_pwd.setEchoMode(QLineEdit.Password)
            self.btn_show_pwd.setText("Show")

    def open_settings_dialog(self):
        """Open the advanced settings dialog"""
        if not self.settings:
            return

        # Create and show settings dialog
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            # Settings were modified in the dialog
            # Reload the widget to reflect any changes
            self.load_settings(self.settings)

    def open_custom_fw_dialog(self):
        """Open the custom firmware settings dialog"""
        if not self.settings:
            return

        # Create and show custom firmware settings dialog
        dialog = CustomFirmwareDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            # Settings were modified in the dialog
            # Emit data modified signal
            self.data_modified.emit()

    def set_enabled(self, enabled: bool):
        """Enable/disable all settings controls"""
        self.edit_radio_name.setEnabled(enabled)
        self.spin_radio_id.setEnabled(enabled)
        self.edit_startup_msg.setEnabled(enabled)
        self.check_password_enabled.setEnabled(enabled)
        # Password field and button enabled state controlled by checkbox
        self.combo_voice_prompt.setEnabled(enabled)
        self.combo_key_beep.setEnabled(enabled)
        self.combo_key_lock.setEnabled(enabled)
        self.combo_lock_timer.setEnabled(enabled)
        self.combo_led_on_off.setEnabled(enabled)
        self.combo_led_timer.setEnabled(enabled)
        self.combo_backlight.setEnabled(enabled)
        self.combo_menu_timer.setEnabled(enabled)
        self.combo_display_mode_a.setEnabled(enabled)
        self.combo_display_mode_b.setEnabled(enabled)
        self.spin_power_save.setEnabled(enabled)
        self.combo_power_save_start.setEnabled(enabled)
        self.check_apo.setEnabled(enabled)
        self.combo_dual_watch.setEnabled(enabled)
        self.combo_talkaround.setEnabled(enabled)
        self.combo_alarm_type.setEnabled(enabled)
        self.combo_tx_priority.setEnabled(enabled)
        self.combo_main_band.setEnabled(enabled)
        self.combo_main_ptt.setEnabled(enabled)
        self.combo_vfo_step.setEnabled(enabled)
        self.combo_work_mode_a.setEnabled(enabled)
        self.spin_zone_a.setEnabled(enabled)
        self.spin_channel_a.setEnabled(enabled)
        self.combo_work_mode_b.setEnabled(enabled)
        self.spin_zone_b.setEnabled(enabled)
        self.spin_channel_b.setEnabled(enabled)
        self.combo_clock_1_mode.setEnabled(enabled)
        self.spin_clock_1_hour.setEnabled(enabled)
        self.spin_clock_1_minute.setEnabled(enabled)
        self.combo_clock_2_mode.setEnabled(enabled)
        self.spin_clock_2_hour.setEnabled(enabled)
        self.spin_clock_2_minute.setEnabled(enabled)
        self.combo_clock_3_mode.setEnabled(enabled)
        self.spin_clock_3_hour.setEnabled(enabled)
        self.spin_clock_3_minute.setEnabled(enabled)
        self.combo_clock_4_mode.setEnabled(enabled)
        self.spin_clock_4_hour.setEnabled(enabled)
        self.spin_clock_4_minute.setEnabled(enabled)
        self.combo_startup_picture_widget.setEnabled(enabled)
        self.combo_tx_protection_widget.setEnabled(enabled)
        self.btn_edit_advanced.setEnabled(enabled)
        self.btn_edit_custom_fw.setEnabled(enabled)

    def load_settings(self, settings: Optional[RadioSettings]):
        """Load settings"""
        self.settings = settings
        if not settings:
            self.set_enabled(False)
            return

        # Block signals while loading
        self.edit_radio_name.blockSignals(True)
        self.spin_radio_id.blockSignals(True)
        self.edit_startup_msg.blockSignals(True)
        self.check_password_enabled.blockSignals(True)
        self.edit_startup_pwd.blockSignals(True)
        self.btn_show_pwd.blockSignals(True)
        self.combo_voice_prompt.blockSignals(True)
        self.combo_key_beep.blockSignals(True)
        self.combo_key_lock.blockSignals(True)
        self.combo_lock_timer.blockSignals(True)
        self.combo_led_on_off.blockSignals(True)
        self.combo_led_timer.blockSignals(True)
        self.combo_backlight.blockSignals(True)
        self.combo_menu_timer.blockSignals(True)
        self.combo_display_mode_a.blockSignals(True)
        self.combo_display_mode_b.blockSignals(True)
        self.spin_power_save.blockSignals(True)
        self.combo_power_save_start.blockSignals(True)
        self.check_apo.blockSignals(True)
        self.combo_dual_watch.blockSignals(True)
        self.combo_talkaround.blockSignals(True)
        self.combo_alarm_type.blockSignals(True)
        self.combo_tx_priority.blockSignals(True)
        self.combo_main_band.blockSignals(True)
        self.combo_main_ptt.blockSignals(True)
        self.combo_vfo_step.blockSignals(True)
        self.combo_work_mode_a.blockSignals(True)
        self.spin_zone_a.blockSignals(True)
        self.spin_channel_a.blockSignals(True)
        self.combo_work_mode_b.blockSignals(True)
        self.spin_zone_b.blockSignals(True)
        self.spin_channel_b.blockSignals(True)
        self.combo_clock_1_mode.blockSignals(True)
        self.spin_clock_1_hour.blockSignals(True)
        self.spin_clock_1_minute.blockSignals(True)
        self.combo_clock_2_mode.blockSignals(True)
        self.spin_clock_2_hour.blockSignals(True)
        self.spin_clock_2_minute.blockSignals(True)
        self.combo_clock_3_mode.blockSignals(True)
        self.spin_clock_3_hour.blockSignals(True)
        self.spin_clock_3_minute.blockSignals(True)
        self.combo_clock_4_mode.blockSignals(True)
        self.spin_clock_4_hour.blockSignals(True)
        self.spin_clock_4_minute.blockSignals(True)
        self.combo_startup_picture_widget.blockSignals(True)
        self.combo_tx_protection_widget.blockSignals(True)

        # Load values
        self.edit_radio_name.setText(settings.radio_name)
        self.spin_radio_id.setValue(settings.radio_id)
        self.edit_startup_msg.setText(settings.startup_message)

        # Password - check password_enable flag
        password_enabled = bool(settings.password_enable)
        self.check_password_enabled.setChecked(password_enabled)
        self.edit_startup_pwd.setText(settings.startup_password if password_enabled else "")
        self.edit_startup_pwd.setEnabled(password_enabled)
        self.btn_show_pwd.setEnabled(password_enabled)
        self.btn_show_pwd.setChecked(False)  # Reset show/hide state

        # Voice prompt
        for i in range(self.combo_voice_prompt.count()):
            if self.combo_voice_prompt.itemData(i) == settings.voice_prompt:
                self.combo_voice_prompt.setCurrentIndex(i)
                break

        # Key beep
        for i in range(self.combo_key_beep.count()):
            if self.combo_key_beep.itemData(i) == settings.key_beep:
                self.combo_key_beep.setCurrentIndex(i)
                break

        # Key lock
        for i in range(self.combo_key_lock.count()):
            if self.combo_key_lock.itemData(i) == settings.key_lock:
                self.combo_key_lock.setCurrentIndex(i)
                break

        # Lock timer
        for i in range(self.combo_lock_timer.count()):
            if self.combo_lock_timer.itemData(i) == settings.lock_timer:
                self.combo_lock_timer.setCurrentIndex(i)
                break

        # LED on/off
        for i in range(self.combo_led_on_off.count()):
            if self.combo_led_on_off.itemData(i) == settings.led_on_off:
                self.combo_led_on_off.setCurrentIndex(i)
                break

        for i in range(self.combo_led_timer.count()):
            if self.combo_led_timer.itemData(i) == settings.led_timer:
                self.combo_led_timer.setCurrentIndex(i)
                break

        # Backlight brightness
        for i in range(self.combo_backlight.count()):
            if self.combo_backlight.itemData(i) == settings.backlight_brightness:
                self.combo_backlight.setCurrentIndex(i)
                break

        for i in range(self.combo_menu_timer.count()):
            if self.combo_menu_timer.itemData(i) == settings.menu_timer:
                self.combo_menu_timer.setCurrentIndex(i)
                break

        # Display mode A
        for i in range(self.combo_display_mode_a.count()):
            if self.combo_display_mode_a.itemData(i) == settings.display_mode_a:
                self.combo_display_mode_a.setCurrentIndex(i)
                break

        # Display mode B
        for i in range(self.combo_display_mode_b.count()):
            if self.combo_display_mode_b.itemData(i) == settings.display_mode_b:
                self.combo_display_mode_b.setCurrentIndex(i)
                break

        self.spin_power_save.setValue(settings.power_save_mode)

        # Power save start
        for i in range(self.combo_power_save_start.count()):
            if self.combo_power_save_start.itemData(i) == settings.power_save_start:
                self.combo_power_save_start.setCurrentIndex(i)
                break

        self.check_apo.setChecked(settings.apo_enabled)

        # Dual watch
        for i in range(self.combo_dual_watch.count()):
            if self.combo_dual_watch.itemData(i) == settings.dual_watch:
                self.combo_dual_watch.setCurrentIndex(i)
                break

        # Talkaround
        for i in range(self.combo_talkaround.count()):
            if self.combo_talkaround.itemData(i) == settings.talkaround:
                self.combo_talkaround.setCurrentIndex(i)
                break

        # Alarm type
        for i in range(self.combo_alarm_type.count()):
            if self.combo_alarm_type.itemData(i) == settings.alarm_type:
                self.combo_alarm_type.setCurrentIndex(i)
                break

        # TX priority global
        for i in range(self.combo_tx_priority.count()):
            if self.combo_tx_priority.itemData(i) == settings.tx_priority_global:
                self.combo_tx_priority.setCurrentIndex(i)
                break

        # Main band
        for i in range(self.combo_main_band.count()):
            if self.combo_main_band.itemData(i) == settings.main_band:
                self.combo_main_band.setCurrentIndex(i)
                break

        # Main PTT
        for i in range(self.combo_main_ptt.count()):
            if self.combo_main_ptt.itemData(i) == settings.main_ptt:
                self.combo_main_ptt.setCurrentIndex(i)
                break

        # VFO step
        for i in range(self.combo_vfo_step.count()):
            if self.combo_vfo_step.itemData(i) == settings.vfo_step:
                self.combo_vfo_step.setCurrentIndex(i)
                break

        # Work mode A
        for i in range(self.combo_work_mode_a.count()):
            if self.combo_work_mode_a.itemData(i) == settings.work_mode_a:
                self.combo_work_mode_a.setCurrentIndex(i)
                break

        self.spin_zone_a.setValue(settings.zone_a)
        self.spin_channel_a.setValue(settings.channel_a + 1)

        # Work mode B
        for i in range(self.combo_work_mode_b.count()):
            if self.combo_work_mode_b.itemData(i) == settings.work_mode_b:
                self.combo_work_mode_b.setCurrentIndex(i)
                break

        self.spin_zone_b.setValue(settings.zone_b)
        self.spin_channel_b.setValue(settings.channel_b + 1)

        # Clocks
        for i in range(self.combo_clock_1_mode.count()):
            if self.combo_clock_1_mode.itemData(i) == settings.clock_1_mode:
                self.combo_clock_1_mode.setCurrentIndex(i)
                break
        self.spin_clock_1_hour.setValue(settings.clock_1_hour)
        self.spin_clock_1_minute.setValue(settings.clock_1_minute)

        for i in range(self.combo_clock_2_mode.count()):
            if self.combo_clock_2_mode.itemData(i) == settings.clock_2_mode:
                self.combo_clock_2_mode.setCurrentIndex(i)
                break
        self.spin_clock_2_hour.setValue(settings.clock_2_hour)
        self.spin_clock_2_minute.setValue(settings.clock_2_minute)

        for i in range(self.combo_clock_3_mode.count()):
            if self.combo_clock_3_mode.itemData(i) == settings.clock_3_mode:
                self.combo_clock_3_mode.setCurrentIndex(i)
                break
        self.spin_clock_3_hour.setValue(settings.clock_3_hour)
        self.spin_clock_3_minute.setValue(settings.clock_3_minute)

        for i in range(self.combo_clock_4_mode.count()):
            if self.combo_clock_4_mode.itemData(i) == settings.clock_4_mode:
                self.combo_clock_4_mode.setCurrentIndex(i)
                break
        self.spin_clock_4_hour.setValue(settings.clock_4_hour)
        self.spin_clock_4_minute.setValue(settings.clock_4_minute)

        # Startup/Boot settings
        for i in range(self.combo_startup_picture_widget.count()):
            if self.combo_startup_picture_widget.itemData(i) == settings.startup_picture_enable:
                self.combo_startup_picture_widget.setCurrentIndex(i)
                break
        for i in range(self.combo_tx_protection_widget.count()):
            if self.combo_tx_protection_widget.itemData(i) == settings.tx_protection:
                self.combo_tx_protection_widget.setCurrentIndex(i)
                break

        # Unblock signals
        self.edit_radio_name.blockSignals(False)
        self.spin_radio_id.blockSignals(False)
        self.edit_startup_msg.blockSignals(False)
        self.check_password_enabled.blockSignals(False)
        self.edit_startup_pwd.blockSignals(False)
        self.btn_show_pwd.blockSignals(False)
        self.combo_voice_prompt.blockSignals(False)
        self.combo_key_beep.blockSignals(False)
        self.combo_key_lock.blockSignals(False)
        self.combo_lock_timer.blockSignals(False)
        self.combo_led_on_off.blockSignals(False)
        self.combo_led_timer.blockSignals(False)
        self.combo_backlight.blockSignals(False)
        self.combo_menu_timer.blockSignals(False)
        self.combo_display_mode_a.blockSignals(False)
        self.combo_display_mode_b.blockSignals(False)
        self.spin_power_save.blockSignals(False)
        self.combo_power_save_start.blockSignals(False)
        self.check_apo.blockSignals(False)
        self.combo_dual_watch.blockSignals(False)
        self.combo_talkaround.blockSignals(False)
        self.combo_alarm_type.blockSignals(False)
        self.combo_tx_priority.blockSignals(False)
        self.combo_main_band.blockSignals(False)
        self.combo_main_ptt.blockSignals(False)
        self.combo_vfo_step.blockSignals(False)
        self.combo_work_mode_a.blockSignals(False)
        self.spin_zone_a.blockSignals(False)
        self.spin_channel_a.blockSignals(False)
        self.combo_work_mode_b.blockSignals(False)
        self.spin_zone_b.blockSignals(False)
        self.spin_channel_b.blockSignals(False)
        self.combo_clock_1_mode.blockSignals(False)
        self.spin_clock_1_hour.blockSignals(False)
        self.spin_clock_1_minute.blockSignals(False)
        self.combo_clock_2_mode.blockSignals(False)
        self.spin_clock_2_hour.blockSignals(False)
        self.spin_clock_2_minute.blockSignals(False)
        self.combo_clock_3_mode.blockSignals(False)
        self.spin_clock_3_hour.blockSignals(False)
        self.spin_clock_3_minute.blockSignals(False)
        self.combo_clock_4_mode.blockSignals(False)
        self.spin_clock_4_hour.blockSignals(False)
        self.spin_clock_4_minute.blockSignals(False)
        self.combo_startup_picture_widget.blockSignals(False)
        self.combo_tx_protection_widget.blockSignals(False)

        self.set_enabled(True)
        self._apply_beta41_visibility()

    def _apply_beta41_visibility(self):
        """Apply visibility based on beta41 flag."""
        if self.settings and self.settings.beta41:
            self.check_apo.setVisible(False)
            self.clock_group.setVisible(False)
        else:
            self.check_apo.setVisible(True)
            self.clock_group.setVisible(True)

    def on_settings_changed(self):
        """Handle settings changes"""
        if not self.settings:
            return

        # Save changes back to settings object
        self.settings.radio_name = self.edit_radio_name.text()
        self.settings.radio_id = self.spin_radio_id.value()
        self.settings.startup_message = self.edit_startup_msg.text()
        # Password: save both password_enable flag and password text
        password_enabled = self.check_password_enabled.isChecked()
        self.settings.password_enable = 1 if password_enabled else 0
        self.settings.startup_password = self.edit_startup_pwd.text() if password_enabled else ""
        self.settings.voice_prompt = self.combo_voice_prompt.currentData()
        self.settings.key_beep = self.combo_key_beep.currentData()
        self.settings.key_lock = self.combo_key_lock.currentData()
        self.settings.lock_timer = self.combo_lock_timer.currentData()
        self.settings.led_on_off = self.combo_led_on_off.currentData()
        self.settings.led_timer = self.combo_led_timer.currentData()
        self.settings.backlight_brightness = self.combo_backlight.currentData()
        self.settings.menu_timer = self.combo_menu_timer.currentData()
        self.settings.display_mode_a = self.combo_display_mode_a.currentData()
        self.settings.display_mode_b = self.combo_display_mode_b.currentData()
        self.settings.power_save_mode = self.spin_power_save.value()
        self.settings.power_save_start = self.combo_power_save_start.currentData()
        self.settings.apo_enabled = self.check_apo.isChecked()
        self.settings.dual_watch = self.combo_dual_watch.currentData()
        self.settings.talkaround = self.combo_talkaround.currentData()
        self.settings.alarm_type = self.combo_alarm_type.currentData()
        self.settings.tx_priority_global = self.combo_tx_priority.currentData()
        self.settings.main_band = self.combo_main_band.currentData()
        self.settings.main_ptt = self.combo_main_ptt.currentData()
        self.settings.vfo_step = self.combo_vfo_step.currentData()
        self.settings.work_mode_a = self.combo_work_mode_a.currentData()
        self.settings.zone_a = self.spin_zone_a.value()
        self.settings.channel_a = self.spin_channel_a.value() - 1
        self.settings.work_mode_b = self.combo_work_mode_b.currentData()
        self.settings.zone_b = self.spin_zone_b.value()
        self.settings.channel_b = self.spin_channel_b.value() - 1
        self.settings.clock_1_mode = self.combo_clock_1_mode.currentData()
        self.settings.clock_1_hour = self.spin_clock_1_hour.value()
        self.settings.clock_1_minute = self.spin_clock_1_minute.value()
        self.settings.clock_2_mode = self.combo_clock_2_mode.currentData()
        self.settings.clock_2_hour = self.spin_clock_2_hour.value()
        self.settings.clock_2_minute = self.spin_clock_2_minute.value()
        self.settings.clock_3_mode = self.combo_clock_3_mode.currentData()
        self.settings.clock_3_hour = self.spin_clock_3_hour.value()
        self.settings.clock_3_minute = self.spin_clock_3_minute.value()
        self.settings.clock_4_mode = self.combo_clock_4_mode.currentData()
        self.settings.clock_4_hour = self.spin_clock_4_hour.value()
        self.settings.clock_4_minute = self.spin_clock_4_minute.value()
        self.settings.startup_picture_enable = self.combo_startup_picture_widget.currentData()
        self.settings.tx_protection = self.combo_tx_protection_widget.currentData()

        self.data_modified.emit()
