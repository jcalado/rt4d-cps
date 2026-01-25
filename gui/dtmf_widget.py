"""DTMF Settings and Preset Codes Widget"""

import re
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QSpinBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QPushButton, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator

from rt4d_codeplug import RadioSettings
from rt4d_codeplug.dropdowns import (
    DTMF_SEND_DELAY_VALUES, DTMF_DURATION_VALUES,
    DTMF_SEND_MODE_VALUES, DTMF_PRESET_VALUES
)


class DTMFWidget(QWidget):
    """Widget for editing DTMF settings and preset codes"""

    settings_changed = Signal()

    # Valid DTMF characters: 0-9, A-D, *, #
    VALID_DTMF_CHARS = re.compile(r'^[0-9A-D\*#]*$')

    # Preset code names (codes 17-20 have special names)
    PRESET_NAMES = [
        "DTMF-01", "DTMF-02", "DTMF-03", "DTMF-04", "DTMF-05",
        "DTMF-06", "DTMF-07", "DTMF-08", "DTMF-09", "DTMF-10",
        "DTMF-11", "DTMF-12", "DTMF-13", "DTMF-14", "DTMF-15",
        "DTMF-16", "Remote Stun", "Remote Kill", "Remote Wake", "Remote Monitor"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings: Optional[RadioSettings] = None
        self._updating = False
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)

        # DTMF Settings Group
        settings_group = QGroupBox("DTMF Settings")
        settings_layout = QFormLayout()

        # Send Delay
        self.send_delay_combo = QComboBox()
        for label, value in DTMF_SEND_DELAY_VALUES:
            self.send_delay_combo.addItem(label, value)
        self.send_delay_combo.currentIndexChanged.connect(self.on_settings_changed)
        settings_layout.addRow("Send Delay:", self.send_delay_combo)

        # Send Duration
        self.send_duration_combo = QComboBox()
        for label, value in DTMF_DURATION_VALUES:
            self.send_duration_combo.addItem(label, value)
        self.send_duration_combo.currentIndexChanged.connect(self.on_settings_changed)
        settings_layout.addRow("Send Duration:", self.send_duration_combo)

        # Send Interval
        self.send_interval_combo = QComboBox()
        for label, value in DTMF_DURATION_VALUES:
            self.send_interval_combo.addItem(label, value)
        self.send_interval_combo.currentIndexChanged.connect(self.on_settings_changed)
        settings_layout.addRow("Send Interval:", self.send_interval_combo)

        # Send Mode
        self.send_mode_combo = QComboBox()
        for label, value in DTMF_SEND_MODE_VALUES:
            self.send_mode_combo.addItem(label, value)
        self.send_mode_combo.currentIndexChanged.connect(self.on_settings_changed)
        settings_layout.addRow("Send Mode:", self.send_mode_combo)

        # Send Select (Preset Code Selection)
        self.send_select_combo = QComboBox()
        for label, value in DTMF_PRESET_VALUES:
            self.send_select_combo.addItem(label, value)
        self.send_select_combo.currentIndexChanged.connect(self.on_settings_changed)
        settings_layout.addRow("Send Select:", self.send_select_combo)

        # Display Enable
        self.display_enable_check = QCheckBox("Enable DTMF Display/Decode")
        self.display_enable_check.stateChanged.connect(self.on_settings_changed)
        settings_layout.addRow("", self.display_enable_check)

        # DTMF Gain
        self.gain_spin = QSpinBox()
        self.gain_spin.setRange(0, 127)
        self.gain_spin.setValue(0)
        self.gain_spin.valueChanged.connect(self.on_settings_changed)
        settings_layout.addRow("DTMF Gain:", self.gain_spin)

        # Decode Threshold
        self.decode_threshold_spin = QSpinBox()
        self.decode_threshold_spin.setRange(0, 63)
        self.decode_threshold_spin.setValue(0)
        self.decode_threshold_spin.valueChanged.connect(self.on_settings_changed)
        settings_layout.addRow("Decode Threshold:", self.decode_threshold_spin)

        # Remote Control
        self.remote_control_check = QCheckBox("Enable Remote Control")
        self.remote_control_check.stateChanged.connect(self.on_settings_changed)
        settings_layout.addRow("", self.remote_control_check)

        # Remote Cal Time
        self.remote_cal_time_check = QCheckBox("Enable Remote Cal Time")
        self.remote_cal_time_check.stateChanged.connect(self.on_settings_changed)
        settings_layout.addRow("", self.remote_cal_time_check)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # DTMF Preset Codes Group
        codes_group = QGroupBox("DTMF Preset Codes (20 programmable codes)")
        codes_layout = QVBoxLayout()

        # Info label
        info_label = QLabel("Valid characters: 0-9, A-D, *, # (max 14 characters per code)")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        codes_layout.addWidget(info_label)

        # Codes table
        self.codes_table = QTableWidget(20, 3)
        self.codes_table.setHorizontalHeaderLabels(["#", "Name", "DTMF Code"])
        self.codes_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.codes_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.codes_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.codes_table.verticalHeader().setVisible(False)
        self.codes_table.setAlternatingRowColors(True)
        self.codes_table.itemChanged.connect(self.on_code_changed)

        # Populate table
        for i in range(20):
            # Index column (read-only)
            index_item = QTableWidgetItem(str(i + 1))
            index_item.setFlags(index_item.flags() & ~Qt.ItemIsEditable)
            index_item.setTextAlignment(Qt.AlignCenter)
            self.codes_table.setItem(i, 0, index_item)

            # Name column (read-only)
            name_item = QTableWidgetItem(self.PRESET_NAMES[i])
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.codes_table.setItem(i, 1, name_item)

            # Code column (editable)
            code_item = QTableWidgetItem("")
            self.codes_table.setItem(i, 2, code_item)

        codes_layout.addWidget(self.codes_table)

        # Buttons
        buttons_layout = QHBoxLayout()

        clear_all_btn = QPushButton("Clear All Codes")
        clear_all_btn.clicked.connect(self.clear_all_codes)
        buttons_layout.addWidget(clear_all_btn)

        buttons_layout.addStretch()
        codes_layout.addLayout(buttons_layout)

        codes_group.setLayout(codes_layout)
        layout.addWidget(codes_group)

    def load_settings(self, settings: RadioSettings):
        """Load settings into the widget"""
        self.settings = settings
        self._updating = True

        # Load DTMF settings
        # Send Delay
        for i in range(self.send_delay_combo.count()):
            if self.send_delay_combo.itemData(i) == settings.dtmf_send_delay:
                self.send_delay_combo.setCurrentIndex(i)
                break

        # Send Duration
        for i in range(self.send_duration_combo.count()):
            if self.send_duration_combo.itemData(i) == settings.dtmf_send_duration:
                self.send_duration_combo.setCurrentIndex(i)
                break

        # Send Interval
        for i in range(self.send_interval_combo.count()):
            if self.send_interval_combo.itemData(i) == settings.dtmf_send_interval:
                self.send_interval_combo.setCurrentIndex(i)
                break

        # Send Mode
        for i in range(self.send_mode_combo.count()):
            if self.send_mode_combo.itemData(i) == settings.dtmf_send_mode:
                self.send_mode_combo.setCurrentIndex(i)
                break

        # Send Select
        for i in range(self.send_select_combo.count()):
            if self.send_select_combo.itemData(i) == settings.dtmf_send_select:
                self.send_select_combo.setCurrentIndex(i)
                break

        # Checkboxes
        self.display_enable_check.setChecked(settings.dtmf_display_enable == 1)
        self.remote_control_check.setChecked(settings.dtmf_remote_control == 1)
        self.remote_cal_time_check.setChecked(settings.dtmf_remote_cal_time == 1)

        # Spinboxes
        self.gain_spin.setValue(settings.dtmf_gain)
        self.decode_threshold_spin.setValue(settings.dtmf_decode_threshold)

        # Load DTMF codes
        for i in range(20):
            code = settings.dtmf_codes[i] if i < len(settings.dtmf_codes) else ""
            self.codes_table.item(i, 2).setText(code)

        self._updating = False

    def save_settings(self, settings: RadioSettings):
        """Save settings from the widget"""
        if not self.settings:
            return

        # Save DTMF settings
        settings.dtmf_send_delay = self.send_delay_combo.currentData()
        settings.dtmf_send_duration = self.send_duration_combo.currentData()
        settings.dtmf_send_interval = self.send_interval_combo.currentData()
        settings.dtmf_send_mode = self.send_mode_combo.currentData()
        settings.dtmf_send_select = self.send_select_combo.currentData()
        settings.dtmf_display_enable = 1 if self.display_enable_check.isChecked() else 0
        settings.dtmf_gain = self.gain_spin.value()
        settings.dtmf_decode_threshold = self.decode_threshold_spin.value()
        settings.dtmf_remote_control = 1 if self.remote_control_check.isChecked() else 0
        settings.dtmf_remote_cal_time = 1 if self.remote_cal_time_check.isChecked() else 0

        # Save DTMF codes
        settings.dtmf_codes = []
        for i in range(20):
            code = self.codes_table.item(i, 2).text()
            settings.dtmf_codes.append(code)

    def on_settings_changed(self):
        """Handle settings change"""
        if not self._updating and self.settings:
            self.save_settings(self.settings)
            self.settings_changed.emit()

    def on_code_changed(self, item: QTableWidgetItem):
        """Handle DTMF code change with validation"""
        if self._updating:
            return

        # Only validate code column (column 2)
        if item.column() != 2:
            return

        code = item.text().upper()

        # Validate characters
        if not self.VALID_DTMF_CHARS.match(code):
            # Invalid characters found - show error and revert
            QMessageBox.warning(
                self,
                "Invalid DTMF Code",
                "DTMF codes can only contain: 0-9, A-D, *, #"
            )
            self._updating = True
            item.setText("")
            self._updating = False
            return

        # Check length (max 14 characters per DTMF struct)
        if len(code) > 14:
            code = code[:14]
            self._updating = True
            item.setText(code)
            self._updating = False

        # Save if valid
        if self.settings:
            self.save_settings(self.settings)
            self.settings_changed.emit()

    def clear_all_codes(self):
        """Clear all DTMF codes"""
        reply = QMessageBox.question(
            self,
            "Clear All Codes",
            "Are you sure you want to clear all DTMF preset codes?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._updating = True
            for i in range(20):
                self.codes_table.item(i, 2).setText("")
            self._updating = False

            if self.settings:
                self.settings.dtmf_codes = [""] * 20
                self.settings_changed.emit()
