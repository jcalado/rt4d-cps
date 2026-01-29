"""FM Radio Widget for managing FM radio presets"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QLabel, QComboBox, QGroupBox, QInputDialog, QLineEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator

from . import theme as _theme
from rt4d_codeplug.models import FMSettings, FMPreset
from rt4d_codeplug.fm_radio import FMParser, FMSerializer, FM_FREQ_MIN, FM_FREQ_MAX


class FMWidget(QWidget):
    """Widget for displaying and editing FM radio presets"""

    data_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fm_settings: Optional[FMSettings] = None
        self._loading = False
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Info label
        # info_label = QLabel(
        #     "FM Radio presets are stored in the codeplug file. Each preset (zone) can contain "
        #     f"up to 16 frequencies in the range {FM_FREQ_MIN}-{FM_FREQ_MAX} MHz."
        # )
        # info_label.setWordWrap(True)
        # info_label.setStyleSheet(f"color: {_theme.hint_color()}; font-style: italic; padding: 5px;")
        # layout.addWidget(info_label)

        # Settings bar
        settings_group = QGroupBox("FM Settings")
        settings_layout = QHBoxLayout()
        settings_group.setLayout(settings_layout)

        # FM Mode
        settings_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Channel Mode", 0)
        self.mode_combo.addItem("Frequency Mode", 1)
        self.mode_combo.currentIndexChanged.connect(self.on_setting_changed)
        settings_layout.addWidget(self.mode_combo)

        settings_layout.addSpacing(20)

        # Scan Mode
        settings_layout.addWidget(QLabel("Scan Mode:"))
        self.scan_combo = QComboBox()
        self.scan_combo.addItem("Carrier Stop", 0)
        self.scan_combo.addItem("Scan All", 1)
        self.scan_combo.currentIndexChanged.connect(self.on_setting_changed)
        settings_layout.addWidget(self.scan_combo)

        settings_layout.addSpacing(20)

        # Selected Area (Preset)
        settings_layout.addWidget(QLabel("Area:"))
        self.area_combo = QComboBox()
        for i in range(16):
            self.area_combo.addItem(f"{i + 1}", i)
        self.area_combo.currentIndexChanged.connect(self.on_setting_changed)
        settings_layout.addWidget(self.area_combo)

        settings_layout.addSpacing(20)

        # Selected Channel (within preset)
        settings_layout.addWidget(QLabel("Channel:"))
        self.channel_combo = QComboBox()
        for i in range(16):
            self.channel_combo.addItem(f"FM{i + 1}", i)
        self.channel_combo.currentIndexChanged.connect(self.on_setting_changed)
        settings_layout.addWidget(self.channel_combo)

        settings_layout.addStretch()
        layout.addWidget(settings_group)

        # Presets table
        self.table = QTableWidget()
        self.table.setColumnCount(18)  # #, Name, FM1-FM16
        headers = ["#", "Name"] + [f"FM{i + 1}" for i in range(16)]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)

        # Configure column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # #
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # Name
        self.table.setColumnWidth(1, 120)
        for i in range(2, 18):  # FM1-FM16
            header.setSectionResizeMode(i, QHeaderView.Interactive)
            self.table.setColumnWidth(i, 60)

        # Connect signals
        self.table.cellChanged.connect(self.on_cell_changed)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)

        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()

        self.btn_clear_preset = QPushButton("Clear Preset")
        self.btn_clear_preset.clicked.connect(self.clear_preset)
        button_layout.addWidget(self.btn_clear_preset)

        self.btn_clear_all = QPushButton("Clear All")
        self.btn_clear_all.clicked.connect(self.clear_all)
        button_layout.addWidget(self.btn_clear_all)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def load_fm_data(self, data: bytes):
        """Load FM data from codeplug bytes.

        Args:
            data: Raw FM data bytes (1024 bytes)
        """
        self._loading = True
        try:
            self.fm_settings = FMParser.parse(data)
            self.refresh_settings()
            self.refresh_table()
        finally:
            self._loading = False

    def get_fm_data(self) -> bytes:
        """Get FM data as bytes for codeplug.

        Returns:
            1024 bytes of FM data
        """
        if not self.fm_settings:
            return bytes([0xFF] * 1024)
        return FMSerializer.serialize(self.fm_settings)

    def refresh_settings(self):
        """Refresh settings dropdowns from current FM settings"""
        if not self.fm_settings:
            return

        self._loading = True
        try:
            # FM Mode
            index = self.mode_combo.findData(self.fm_settings.mode)
            if index >= 0:
                self.mode_combo.setCurrentIndex(index)

            # Scan Mode
            index = self.scan_combo.findData(self.fm_settings.scan_mode)
            if index >= 0:
                self.scan_combo.setCurrentIndex(index)

            # Selected Area
            index = self.area_combo.findData(self.fm_settings.selected_area)
            if index >= 0:
                self.area_combo.setCurrentIndex(index)

            # Selected Channel
            index = self.channel_combo.findData(self.fm_settings.selected_channel)
            if index >= 0:
                self.channel_combo.setCurrentIndex(index)
        finally:
            self._loading = False

    def refresh_table(self):
        """Refresh the presets table"""
        self._loading = True
        try:
            self.table.setRowCount(0)

            if not self.fm_settings:
                return

            palette = self.table.palette()
            readonly_bg = palette.alternateBase().color()

            for row, preset in enumerate(self.fm_settings.presets):
                self.table.insertRow(row)

                # Index column (read-only)
                item_index = QTableWidgetItem(str(row + 1))
                item_index.setBackground(readonly_bg)
                item_index.setFlags(item_index.flags() & ~Qt.ItemIsEditable)
                item_index.setData(Qt.UserRole, row)  # Store preset index
                self.table.setItem(row, 0, item_index)

                # Name column (editable)
                item_name = QTableWidgetItem(preset.name)
                self.table.setItem(row, 1, item_name)

                # Frequency columns (editable)
                for col, freq in enumerate(preset.frequencies):
                    freq_str = self._format_frequency(freq)
                    item_freq = QTableWidgetItem(freq_str)
                    item_freq.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row, col + 2, item_freq)
        finally:
            self._loading = False

    def _format_frequency(self, freq: float) -> str:
        """Format frequency for display.

        Args:
            freq: Frequency in MHz

        Returns:
            Formatted string (e.g., "107.5" or "-" for empty)
        """
        if freq <= 0.0:
            return "-"
        return f"{freq:.1f}"

    def _parse_frequency(self, text: str) -> float:
        """Parse frequency from user input.

        Args:
            text: User input string

        Returns:
            Frequency in MHz, or 0.0 if invalid/empty
        """
        text = text.strip()
        if not text or text == "-":
            return 0.0

        try:
            freq = float(text)
            if freq < FM_FREQ_MIN or freq > FM_FREQ_MAX:
                return 0.0
            return freq
        except ValueError:
            return 0.0

    def on_setting_changed(self):
        """Handle settings dropdown changes"""
        if self._loading or not self.fm_settings:
            return

        self.fm_settings.mode = self.mode_combo.currentData()
        self.fm_settings.scan_mode = self.scan_combo.currentData()
        self.fm_settings.selected_area = self.area_combo.currentData()
        self.fm_settings.selected_channel = self.channel_combo.currentData()

        self.data_modified.emit()

    def on_cell_changed(self, row: int, column: int):
        """Handle cell content changes"""
        if self._loading or not self.fm_settings:
            return

        if row < 0 or row >= len(self.fm_settings.presets):
            return

        preset = self.fm_settings.presets[row]
        item = self.table.item(row, column)
        if not item:
            return

        text = item.text()

        if column == 1:
            # Name column
            new_name = text[:16]  # Max 16 chars
            if preset.name != new_name:
                preset.name = new_name
                self.data_modified.emit()

        elif column >= 2 and column < 18:
            # Frequency columns (FM1-FM16)
            freq_index = column - 2
            new_freq = self._parse_frequency(text)

            # Validate and update display
            self._loading = True
            item.setText(self._format_frequency(new_freq))
            self._loading = False

            if preset.frequencies[freq_index] != new_freq:
                preset.frequencies[freq_index] = new_freq
                self.data_modified.emit()

    def on_cell_double_clicked(self, row: int, column: int):
        """Handle double-click for editing"""
        if column >= 2 and column < 18:
            # For frequency columns, show input dialog with validation
            if not self.fm_settings or row >= len(self.fm_settings.presets):
                return

            preset = self.fm_settings.presets[row]
            freq_index = column - 2
            current_freq = preset.frequencies[freq_index]

            current_str = f"{current_freq:.1f}" if current_freq > 0 else ""

            freq_str, ok = QInputDialog.getText(
                self,
                "Edit Frequency",
                f"Enter frequency ({FM_FREQ_MIN}-{FM_FREQ_MAX} MHz)\nor leave empty to clear:",
                QLineEdit.Normal,
                current_str
            )

            if ok:
                new_freq = self._parse_frequency(freq_str)

                # Validate non-zero frequency
                if freq_str.strip() and freq_str.strip() != "-" and new_freq == 0.0:
                    QMessageBox.warning(
                        self,
                        "Invalid Frequency",
                        f"Frequency must be between {FM_FREQ_MIN} and {FM_FREQ_MAX} MHz."
                    )
                    return

                preset.frequencies[freq_index] = new_freq
                self._loading = True
                self.table.item(row, column).setText(self._format_frequency(new_freq))
                self._loading = False
                self.data_modified.emit()

    def clear_preset(self):
        """Clear the selected preset"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "No preset selected")
            return

        if not self.fm_settings or current_row >= len(self.fm_settings.presets):
            return

        preset = self.fm_settings.presets[current_row]

        reply = QMessageBox.question(
            self,
            "Clear Preset",
            f"Clear preset {current_row + 1} '{preset.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            preset.name = ""
            preset.frequencies = [0.0] * 16
            self.refresh_table()
            self.data_modified.emit()

    def clear_all(self):
        """Clear all presets"""
        if not self.fm_settings:
            return

        reply = QMessageBox.question(
            self,
            "Clear All Presets",
            "Are you sure you want to clear all FM presets?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            for preset in self.fm_settings.presets:
                preset.name = ""
                preset.frequencies = [0.0] * 16
            self.refresh_table()
            self.data_modified.emit()
