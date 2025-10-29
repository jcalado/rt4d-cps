"""Channel Table Widget with drag-and-drop support"""

import csv
import copy
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox, QMessageBox, QSplitter, QGroupBox, QFormLayout,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QLabel, QScrollArea,
    QFileDialog
)
from PySide6.QtCore import Qt, Signal, QRegularExpression
from PySide6.QtGui import QColor, QDropEvent, QKeyEvent, QKeySequence, QRegularExpressionValidator

from rt4d_codeplug import Codeplug, Channel, ChannelMode, PowerLevel, ScanMode
from rt4d_codeplug.dropdowns import (
    TOT_VALUES, TX_PRIORITY_VALUES, ALARM_VALUES, SCRAMBLER_VALUES,
    CTCSS_DCS_VALUES, BANDWIDTH_VALUES, CTDCS_SELECT_VALUES, TAIL_TONE_VALUES,
    DMR_MONITOR_VALUES, DMR_MODE_VALUES
)


class DraggableTableWidget(QTableWidget):
    """Table widget that supports drag-and-drop reordering"""

    rows_reordered = Signal()
    copy_requested = Signal(int)  # row index
    paste_requested = Signal(int)  # row index to paste after (-1 for end)
    delete_requested = Signal(int)  # row index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDropIndicatorShown(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setVisible(False)
        self._item_changed_handler = None

    def set_item_changed_handler(self, handler):
        """Store reference to itemChanged handler so we can disconnect it temporarily"""
        self._item_changed_handler = handler

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts for copy/paste/delete"""
        if event.matches(QKeySequence.StandardKey.Copy):
            # Ctrl+C - Copy selected channel
            current_row = self.currentRow()
            if current_row >= 0:
                self.copy_requested.emit(current_row)
                event.accept()
                return
        elif event.matches(QKeySequence.StandardKey.Paste):
            # Ctrl+V - Paste channel
            current_row = self.currentRow()
            self.paste_requested.emit(current_row)
            event.accept()
            return
        elif event.matches(QKeySequence.StandardKey.Delete):
            # Delete - Delete selected channel
            current_row = self.currentRow()
            if current_row >= 0:
                self.delete_requested.emit(current_row)
                event.accept()
                return

        # Default handling for other keys
        super().keyPressEvent(event)

    def dropEvent(self, event: QDropEvent):
        """Handle drop event to reorder rows"""
        if event.source() != self:
            event.ignore()
            return

        # Get source row (the row being dragged)
        source_row = self.currentRow()
        if source_row < 0:
            event.ignore()
            return

        # Get drop position
        drop_pos = event.position().toPoint()
        drop_index = self.indexAt(drop_pos)

        # Determine target row - insert BEFORE the hovered row
        if drop_index.isValid():
            target_row = drop_index.row()
        else:
            # Dropped below all rows - insert at end
            target_row = self.rowCount()

        # Don't do anything if dropping on itself
        if source_row == target_row or source_row == target_row - 1:
            event.ignore()
            return

        # Accept the event
        event.accept()

        # Temporarily disconnect itemChanged to prevent it firing during manual move
        if self._item_changed_handler:
            try:
                self.itemChanged.disconnect(self._item_changed_handler)
            except:
                pass

        # Manually move the row
        self._move_row(source_row, target_row)

        # Reconnect itemChanged
        if self._item_changed_handler:
            self.itemChanged.connect(self._item_changed_handler)

        # Emit signal so parent can update the underlying data
        self.rows_reordered.emit()

    def _move_row(self, source_row: int, target_row: int):
        """Manually move a row from source to target position"""
        # Extract all items from source row
        items = []
        for col in range(self.columnCount()):
            item = self.takeItem(source_row, col)
            if item:
                items.append(item)
            else:
                items.append(None)

        # Remove the source row
        self.removeRow(source_row)

        # Adjust target row if needed (if source was before target)
        if source_row < target_row:
            target_row -= 1

        # Insert new row at target position
        self.insertRow(target_row)

        # Put items back
        for col, item in enumerate(items):
            if item:
                self.setItem(target_row, col, item)

        # Select the moved row
        self.selectRow(target_row)


class ChannelTableWidget(QWidget):
    """Widget for displaying and editing channels"""

    data_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.codeplug: Optional[Codeplug] = None
        self.copied_channel: Optional[Channel] = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create splitter for table and details
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left side: Table and buttons
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        # Create table
        self.table = DraggableTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "#", "Name", "RX Freq", "TX Freq", "Mode", "Power",
            "Scan", "Color Code", "Time Slot"
        ])

        # Configure table
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)

        # Resize columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Index
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Name
        for i in range(2, 9):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        # Connect signals
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.rows_reordered.connect(self.on_rows_reordered)
        self.table.copy_requested.connect(self.on_copy_channel)
        self.table.paste_requested.connect(self.on_paste_channel)
        self.table.delete_requested.connect(self.on_delete_channel)

        # Register the itemChanged handler so table can disconnect it during drops
        self.table.set_item_changed_handler(self.on_item_changed)

        left_layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()

        self.btn_add = QPushButton("Add Channel")
        self.btn_add.clicked.connect(self.add_channel)
        button_layout.addWidget(self.btn_add)

        self.btn_delete = QPushButton("Delete Channel")
        self.btn_delete.clicked.connect(self.delete_channel)
        button_layout.addWidget(self.btn_delete)

        button_layout.addStretch()

        self.btn_import = QPushButton("Import CSV")
        self.btn_import.clicked.connect(self.on_import_csv_clicked)
        button_layout.addWidget(self.btn_import)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.clicked.connect(self.on_export_csv_clicked)
        button_layout.addWidget(self.btn_export)

        left_layout.addLayout(button_layout)

        # Right side: Details panel
        self.details_panel = self.create_details_panel()

        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(self.details_panel)
        splitter.setStretchFactor(0, 2)  # Table takes 2/3
        splitter.setStretchFactor(1, 1)  # Details takes 1/3

    def create_details_panel(self):
        """Create channel details panel"""
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Create panel widget
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)

        label = QLabel("<b>Channel Details</b>")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        # Basic settings group
        basic_group = QGroupBox("Basic Settings")
        basic_layout = QFormLayout()

        self.detail_name = QLineEdit()
        self.detail_name.setMaxLength(16)
        self.detail_name.textChanged.connect(self.on_detail_changed)
        basic_layout.addRow("Name:", self.detail_name)

        self.detail_rx_freq = QDoubleSpinBox()
        self.detail_rx_freq.setRange(0, 1000)
        self.detail_rx_freq.setDecimals(5)
        self.detail_rx_freq.setSuffix(" MHz")
        self.detail_rx_freq.valueChanged.connect(self.on_detail_changed)
        basic_layout.addRow("RX Frequency:", self.detail_rx_freq)

        self.detail_tx_freq = QDoubleSpinBox()
        self.detail_tx_freq.setRange(0, 1000)
        self.detail_tx_freq.setDecimals(5)
        self.detail_tx_freq.setSuffix(" MHz")
        self.detail_tx_freq.valueChanged.connect(self.on_detail_changed)
        basic_layout.addRow("TX Frequency:", self.detail_tx_freq)

        self.detail_mode = QComboBox()
        self.detail_mode.addItems(["Analog", "Digital"])
        self.detail_mode.currentIndexChanged.connect(self.on_mode_changed)
        basic_layout.addRow("Mode:", self.detail_mode)

        self.detail_power = QComboBox()
        self.detail_power.addItems(["High", "Low"])
        self.detail_power.currentIndexChanged.connect(self.on_detail_changed)
        basic_layout.addRow("Power:", self.detail_power)

        self.detail_scan = QComboBox()
        self.detail_scan.addItems(["Add", "Remove"])
        self.detail_scan.currentIndexChanged.connect(self.on_detail_changed)
        basic_layout.addRow("Scan:", self.detail_scan)

        self.detail_enabled = QCheckBox("Channel Enabled")
        self.detail_enabled.stateChanged.connect(self.on_detail_changed)
        basic_layout.addRow("", self.detail_enabled)

        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # Digital/DMR settings group
        self.dmr_group = QGroupBox("Digital (DMR) Settings")
        dmr_layout = QFormLayout()

        self.detail_time_slot = QComboBox()
        self.detail_time_slot.addItems(["Slot 1", "Slot 2"])
        self.detail_time_slot.currentIndexChanged.connect(self.on_detail_changed)
        dmr_layout.addRow("Time Slot:", self.detail_time_slot)

        self.detail_color_code = QSpinBox()
        self.detail_color_code.setRange(0, 15)
        self.detail_color_code.valueChanged.connect(self.on_detail_changed)
        dmr_layout.addRow("Color Code:", self.detail_color_code)

        self.detail_dmr_mode = QComboBox()
        for label, value in DMR_MODE_VALUES:
            self.detail_dmr_mode.addItem(label, value)
        self.detail_dmr_mode.currentIndexChanged.connect(self.on_detail_changed)
        dmr_layout.addRow("DMR Mode:", self.detail_dmr_mode)

        self.detail_dmr_monitor = QComboBox()
        for label, value in DMR_MONITOR_VALUES:
            self.detail_dmr_monitor.addItem(label, value)
        self.detail_dmr_monitor.currentIndexChanged.connect(self.on_detail_changed)
        dmr_layout.addRow("Monitor (Promiscuous):", self.detail_dmr_monitor)

        self.detail_contact = QComboBox()
        self.detail_contact.setEditable(False)
        self.detail_contact.currentIndexChanged.connect(self.on_detail_changed)
        dmr_layout.addRow("Contact:", self.detail_contact)

        self.detail_group_list = QComboBox()
        self.detail_group_list.setEditable(False)
        self.detail_group_list.currentIndexChanged.connect(self.on_detail_changed)
        dmr_layout.addRow("Group List:", self.detail_group_list)

        self.detail_encrypt = QComboBox()
        self.detail_encrypt.setEditable(False)
        self.detail_encrypt.currentIndexChanged.connect(self.on_detail_changed)
        dmr_layout.addRow("Encryption:", self.detail_encrypt)

        self.detail_tx_priority = QComboBox()
        for label, value in TX_PRIORITY_VALUES:
            self.detail_tx_priority.addItem(label, value)
        self.detail_tx_priority.currentIndexChanged.connect(self.on_detail_changed)
        dmr_layout.addRow("TX Priority:", self.detail_tx_priority)

        self.detail_tot = QComboBox()
        for label, value in TOT_VALUES:
            self.detail_tot.addItem(label, value)
        self.detail_tot.currentIndexChanged.connect(self.on_detail_changed)
        dmr_layout.addRow("Timeout (TOT):", self.detail_tot)

        self.detail_alarm = QComboBox()
        for label, value in ALARM_VALUES:
            self.detail_alarm.addItem(label, value)
        self.detail_alarm.currentIndexChanged.connect(self.on_detail_changed)
        dmr_layout.addRow("Alarm:", self.detail_alarm)

        self.detail_dmr_id = QSpinBox()
        self.detail_dmr_id.setRange(0, 16777215)
        self.detail_dmr_id.valueChanged.connect(self.on_detail_changed)
        dmr_layout.addRow("DMR ID:", self.detail_dmr_id)

        self.detail_use_radio_id = QCheckBox("Use Radio DMR ID")
        self.detail_use_radio_id.stateChanged.connect(self.on_use_radio_id_changed)
        dmr_layout.addRow("", self.detail_use_radio_id)

        self.dmr_group.setLayout(dmr_layout)
        layout.addWidget(self.dmr_group)

        # Analog settings group
        self.analog_group = QGroupBox("Analog (FM) Settings")
        analog_layout = QFormLayout()

        self.detail_rx_ctcss = QComboBox()
        self.detail_rx_ctcss.setEditable(False)
        for value in CTCSS_DCS_VALUES:
            self.detail_rx_ctcss.addItem(value)
        self.detail_rx_ctcss.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("RX CTCSS/DCS:", self.detail_rx_ctcss)

        self.detail_tx_ctcss = QComboBox()
        self.detail_tx_ctcss.setEditable(False)
        for value in CTCSS_DCS_VALUES:
            self.detail_tx_ctcss.addItem(value)
        self.detail_tx_ctcss.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("TX CTCSS/DCS:", self.detail_tx_ctcss)

        self.detail_scramble = QComboBox()
        for label, value in SCRAMBLER_VALUES:
            self.detail_scramble.addItem(label, value)
        self.detail_scramble.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("Scrambler:", self.detail_scramble)

        self.detail_bandwidth = QComboBox()
        for label, value in BANDWIDTH_VALUES:
            self.detail_bandwidth.addItem(label, value)
        self.detail_bandwidth.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("Modulation:", self.detail_bandwidth)

        self.detail_tx_priority_analog = QComboBox()
        for label, value in TX_PRIORITY_VALUES:
            self.detail_tx_priority_analog.addItem(label, value)
        self.detail_tx_priority_analog.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("TX Priority:", self.detail_tx_priority_analog)

        self.detail_tot_analog = QComboBox()
        for label, value in TOT_VALUES:
            self.detail_tot_analog.addItem(label, value)
        self.detail_tot_analog.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("TOT:", self.detail_tot_analog)

        self.detail_ctdcs_select = QComboBox()
        for label, value in CTDCS_SELECT_VALUES:
            self.detail_ctdcs_select.addItem(label, value)
        self.detail_ctdcs_select.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("CT/DCS Select:", self.detail_ctdcs_select)

        self.detail_tail_tone = QComboBox()
        for label, value in TAIL_TONE_VALUES:
            self.detail_tail_tone.addItem(label, value)
        self.detail_tail_tone.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("Tail Tone:", self.detail_tail_tone)

        # Encrypted Sub-audio Codes (used when CT/DCS Select is set to Encrypted 1/2/3)
        hex_validator = QRegularExpressionValidator(QRegularExpression("[0-9A-Fa-f]{0,8}"))

        self.detail_encrypted_code_1 = QLineEdit()
        self.detail_encrypted_code_1.setPlaceholderText("00000000")
        self.detail_encrypted_code_1.setMaxLength(8)
        self.detail_encrypted_code_1.setValidator(hex_validator)
        self.detail_encrypted_code_1.textChanged.connect(self.on_detail_changed)
        analog_layout.addRow("Encrypted Code 1:", self.detail_encrypted_code_1)

        self.detail_encrypted_code_2 = QLineEdit()
        self.detail_encrypted_code_2.setPlaceholderText("00000000")
        self.detail_encrypted_code_2.setMaxLength(8)
        self.detail_encrypted_code_2.setValidator(hex_validator)
        self.detail_encrypted_code_2.textChanged.connect(self.on_detail_changed)
        analog_layout.addRow("Encrypted Code 2:", self.detail_encrypted_code_2)

        self.detail_encrypted_code_3 = QLineEdit()
        self.detail_encrypted_code_3.setPlaceholderText("00000000")
        self.detail_encrypted_code_3.setMaxLength(8)
        self.detail_encrypted_code_3.setValidator(hex_validator)
        self.detail_encrypted_code_3.textChanged.connect(self.on_detail_changed)
        analog_layout.addRow("Encrypted Code 3:", self.detail_encrypted_code_3)

        self.analog_group.setLayout(analog_layout)
        layout.addWidget(self.analog_group)

        layout.addStretch()

        # Initially disable all controls
        self.set_details_enabled(False)

        # Set panel in scroll area
        scroll.setWidget(panel)
        return scroll

    def set_details_enabled(self, enabled: bool):
        """Enable/disable details panel"""
        self.detail_name.setEnabled(enabled)
        self.detail_rx_freq.setEnabled(enabled)
        self.detail_tx_freq.setEnabled(enabled)
        self.detail_mode.setEnabled(enabled)
        self.detail_power.setEnabled(enabled)
        self.detail_scan.setEnabled(enabled)
        self.detail_enabled.setEnabled(enabled)
        self.dmr_group.setEnabled(enabled)
        self.analog_group.setEnabled(enabled)

    def on_selection_changed(self):
        """Handle table selection change"""
        current_row = self.table.currentRow()
        if current_row < 0:
            self.set_details_enabled(False)
            return

        # Get selected channel
        index_item = self.table.item(current_row, 0)
        if not index_item:
            return

        channel_index = int(index_item.text()) - 1
        channel = self.codeplug.get_channel(channel_index)

        if channel:
            self.load_channel_details(channel)
            self.set_details_enabled(True)

    def reload_current_channel_details(self):
        """Reload details for currently displayed channel (useful after dropdown refresh)"""
        current_row = self.table.currentRow()
        if current_row < 0 or not self.codeplug:
            return

        # Get selected channel
        index_item = self.table.item(current_row, 0)
        if not index_item:
            return

        channel_index = int(index_item.text()) - 1
        channel = self.codeplug.get_channel(channel_index)

        if channel:
            self.load_channel_details(channel)

    def load_channel_details(self, channel: Channel):
        """Load channel data into details panel"""
        # Block signals while loading
        self.detail_name.blockSignals(True)
        self.detail_rx_freq.blockSignals(True)
        self.detail_tx_freq.blockSignals(True)
        self.detail_mode.blockSignals(True)
        self.detail_power.blockSignals(True)
        self.detail_scan.blockSignals(True)
        self.detail_enabled.blockSignals(True)
        self.detail_time_slot.blockSignals(True)
        self.detail_color_code.blockSignals(True)
        self.detail_dmr_mode.blockSignals(True)
        self.detail_dmr_monitor.blockSignals(True)
        self.detail_contact.blockSignals(True)
        self.detail_group_list.blockSignals(True)
        self.detail_encrypt.blockSignals(True)
        self.detail_tx_priority.blockSignals(True)
        self.detail_tot.blockSignals(True)
        self.detail_alarm.blockSignals(True)
        self.detail_dmr_id.blockSignals(True)
        self.detail_rx_ctcss.blockSignals(True)
        self.detail_tx_ctcss.blockSignals(True)
        self.detail_scramble.blockSignals(True)
        self.detail_bandwidth.blockSignals(True)
        self.detail_tx_priority_analog.blockSignals(True)
        self.detail_tot_analog.blockSignals(True)
        self.detail_ctdcs_select.blockSignals(True)
        self.detail_tail_tone.blockSignals(True)
        self.detail_encrypted_code_1.blockSignals(True)
        self.detail_encrypted_code_2.blockSignals(True)
        self.detail_encrypted_code_3.blockSignals(True)

        # Load basic settings
        self.detail_name.setText(channel.name)
        self.detail_rx_freq.setValue(channel.rx_freq)
        self.detail_tx_freq.setValue(channel.tx_freq)
        self.detail_mode.setCurrentIndex(1 if channel.is_digital() else 0)
        self.detail_power.setCurrentIndex(0 if channel.power == PowerLevel.HIGH else 1)
        self.detail_scan.setCurrentIndex(0 if channel.scan == ScanMode.ADD else 1)
        self.detail_enabled.setChecked(channel.enabled)

        # Load DMR settings
        self.detail_time_slot.setCurrentIndex(channel.dmr_time_slot)
        self.detail_color_code.setValue(channel.dmr_color_code)
        # DMR Mode - find index by value
        for i in range(self.detail_dmr_mode.count()):
            if self.detail_dmr_mode.itemData(i) == channel.dmr_mode:
                self.detail_dmr_mode.setCurrentIndex(i)
                break
        # DMR Monitor - find index by value
        for i in range(self.detail_dmr_monitor.count()):
            if self.detail_dmr_monitor.itemData(i) == channel.dmr_monitor:
                self.detail_dmr_monitor.setCurrentIndex(i)
                break
        # Contact - find dropdown index by contact_index value
        contact_found = False
        for i in range(self.detail_contact.count()):
            if self.detail_contact.itemData(i) == channel.contact_index:
                self.detail_contact.setCurrentIndex(i)
                contact_found = True
                break
        if not contact_found:
            self.detail_contact.setCurrentIndex(0)  # Default to "None"
        # Group List - find dropdown index by group_list_index value
        group_list_found = False
        for i in range(self.detail_group_list.count()):
            if self.detail_group_list.itemData(i) == channel.group_list_index:
                self.detail_group_list.setCurrentIndex(i)
                group_list_found = True
                break
        if not group_list_found:
            self.detail_group_list.setCurrentIndex(0)  # Default to "None"
        # Encryption - find dropdown index by encrypt_index value
        encrypt_found = False
        for i in range(self.detail_encrypt.count()):
            if self.detail_encrypt.itemData(i) == channel.encrypt_index:
                self.detail_encrypt.setCurrentIndex(i)
                encrypt_found = True
                break
        if not encrypt_found:
            self.detail_encrypt.setCurrentIndex(0)  # Default to "None"
        # TX Priority - find index by value
        for i in range(self.detail_tx_priority.count()):
            if self.detail_tx_priority.itemData(i) == channel.tx_priority:
                self.detail_tx_priority.setCurrentIndex(i)
                break
        # TOT - find index by value
        for i in range(self.detail_tot.count()):
            if self.detail_tot.itemData(i) == channel.tot:
                self.detail_tot.setCurrentIndex(i)
                break
        # Alarm - find index by value
        for i in range(self.detail_alarm.count()):
            if self.detail_alarm.itemData(i) == channel.alarm:
                self.detail_alarm.setCurrentIndex(i)
                break
        self.detail_dmr_id.setValue(channel.dmr_id)
        self.detail_use_radio_id.setChecked(channel.use_radio_id)
        # Enable/disable DMR ID spinbox based on checkbox state
        self.detail_dmr_id.setEnabled(not channel.use_radio_id)

        # Load analog settings
        # RX CTCSS/DCS
        rx_ctcss_text = channel.rx_ctcss or "None"
        idx = self.detail_rx_ctcss.findText(rx_ctcss_text)
        if idx >= 0:
            self.detail_rx_ctcss.setCurrentIndex(idx)
        else:
            self.detail_rx_ctcss.setCurrentIndex(0)  # None
        # TX CTCSS/DCS
        tx_ctcss_text = channel.tx_ctcss or "None"
        idx = self.detail_tx_ctcss.findText(tx_ctcss_text)
        if idx >= 0:
            self.detail_tx_ctcss.setCurrentIndex(idx)
        else:
            self.detail_tx_ctcss.setCurrentIndex(0)  # None
        # Scrambler
        for i in range(self.detail_scramble.count()):
            if self.detail_scramble.itemData(i) == channel.scramble:
                self.detail_scramble.setCurrentIndex(i)
                break
        # Bandwidth
        for i in range(self.detail_bandwidth.count()):
            if self.detail_bandwidth.itemData(i) == channel.bandwidth:
                self.detail_bandwidth.setCurrentIndex(i)
                break
        # TX Priority (analog)
        for i in range(self.detail_tx_priority_analog.count()):
            if self.detail_tx_priority_analog.itemData(i) == channel.tx_priority_analog:
                self.detail_tx_priority_analog.setCurrentIndex(i)
                break
        # TOT (analog)
        for i in range(self.detail_tot_analog.count()):
            if self.detail_tot_analog.itemData(i) == channel.tot_analog:
                self.detail_tot_analog.setCurrentIndex(i)
                break
        # CT/DCS Select
        for i in range(self.detail_ctdcs_select.count()):
            if self.detail_ctdcs_select.itemData(i) == channel.ctdcs_select:
                self.detail_ctdcs_select.setCurrentIndex(i)
                break
        # Tail Tone
        for i in range(self.detail_tail_tone.count()):
            if self.detail_tail_tone.itemData(i) == channel.tail_tone:
                self.detail_tail_tone.setCurrentIndex(i)
                break
        # Encrypted codes (display as 8-digit hex)
        self.detail_encrypted_code_1.setText(f"{channel.encrypted_code_1:08X}")
        self.detail_encrypted_code_2.setText(f"{channel.encrypted_code_2:08X}")
        self.detail_encrypted_code_3.setText(f"{channel.encrypted_code_3:08X}")

        # Show/hide groups based on mode
        self.dmr_group.setVisible(channel.is_digital())
        self.analog_group.setVisible(channel.is_analog())

        # Unblock signals
        self.detail_name.blockSignals(False)
        self.detail_rx_freq.blockSignals(False)
        self.detail_tx_freq.blockSignals(False)
        self.detail_mode.blockSignals(False)
        self.detail_power.blockSignals(False)
        self.detail_scan.blockSignals(False)
        self.detail_enabled.blockSignals(False)
        self.detail_time_slot.blockSignals(False)
        self.detail_color_code.blockSignals(False)
        self.detail_dmr_mode.blockSignals(False)
        self.detail_dmr_monitor.blockSignals(False)
        self.detail_contact.blockSignals(False)
        self.detail_group_list.blockSignals(False)
        self.detail_encrypt.blockSignals(False)
        self.detail_tx_priority.blockSignals(False)
        self.detail_tot.blockSignals(False)
        self.detail_alarm.blockSignals(False)
        self.detail_dmr_id.blockSignals(False)
        self.detail_rx_ctcss.blockSignals(False)
        self.detail_tx_ctcss.blockSignals(False)
        self.detail_scramble.blockSignals(False)
        self.detail_bandwidth.blockSignals(False)
        self.detail_tx_priority_analog.blockSignals(False)
        self.detail_tot_analog.blockSignals(False)
        self.detail_ctdcs_select.blockSignals(False)
        self.detail_tail_tone.blockSignals(False)
        self.detail_encrypted_code_1.blockSignals(False)
        self.detail_encrypted_code_2.blockSignals(False)
        self.detail_encrypted_code_3.blockSignals(False)

    def on_mode_changed(self):
        """Handle mode change"""
        # Show/hide groups based on mode
        is_digital = self.detail_mode.currentIndex() == 1
        self.dmr_group.setVisible(is_digital)
        self.analog_group.setVisible(not is_digital)
        self.on_detail_changed()

    def on_detail_changed(self):
        """Handle detail field changes"""
        current_row = self.table.currentRow()
        if current_row < 0 or not self.codeplug:
            return

        # Get channel
        index_item = self.table.item(current_row, 0)
        if not index_item:
            return

        channel_index = int(index_item.text()) - 1
        channel = self.codeplug.get_channel(channel_index)

        if not channel:
            return

        # Update channel from details
        channel.name = self.detail_name.text()[:16]
        channel.rx_freq = self.detail_rx_freq.value()
        channel.tx_freq = self.detail_tx_freq.value()
        channel.mode = ChannelMode.DIGITAL if self.detail_mode.currentIndex() == 1 else ChannelMode.ANALOG
        channel.power = PowerLevel.HIGH if self.detail_power.currentIndex() == 0 else PowerLevel.LOW
        channel.scan = ScanMode.ADD if self.detail_scan.currentIndex() == 0 else ScanMode.REMOVE
        channel.enabled = self.detail_enabled.isChecked()

        # DMR settings
        channel.dmr_time_slot = self.detail_time_slot.currentIndex()
        channel.dmr_color_code = self.detail_color_code.value()
        channel.dmr_mode = self.detail_dmr_mode.currentData()
        channel.dmr_monitor = self.detail_dmr_monitor.currentData()
        channel.contact_index = self.detail_contact.currentData() if self.detail_contact.currentData() is not None else 0
        channel.group_list_index = self.detail_group_list.currentData() if self.detail_group_list.currentData() is not None else 0
        channel.encrypt_index = self.detail_encrypt.currentData() if self.detail_encrypt.currentData() is not None else 0
        channel.tx_priority = self.detail_tx_priority.currentData()
        channel.tot = self.detail_tot.currentData()
        channel.alarm = self.detail_alarm.currentData()
        channel.dmr_id = self.detail_dmr_id.value()
        channel.use_radio_id = self.detail_use_radio_id.isChecked()

        # Analog settings
        rx_ctcss_text = self.detail_rx_ctcss.currentText()
        channel.rx_ctcss = None if rx_ctcss_text == "None" else rx_ctcss_text
        tx_ctcss_text = self.detail_tx_ctcss.currentText()
        channel.tx_ctcss = None if tx_ctcss_text == "None" else tx_ctcss_text
        channel.scramble = self.detail_scramble.currentData()
        channel.bandwidth = self.detail_bandwidth.currentData()
        channel.tx_priority_analog = self.detail_tx_priority_analog.currentData()
        channel.tot_analog = self.detail_tot_analog.currentData()
        channel.ctdcs_select = self.detail_ctdcs_select.currentData()
        channel.tail_tone = self.detail_tail_tone.currentData()
        # Encrypted codes - parse as hex integers
        try:
            channel.encrypted_code_1 = int(self.detail_encrypted_code_1.text() or "0", 16)
        except ValueError:
            channel.encrypted_code_1 = 0
        try:
            channel.encrypted_code_2 = int(self.detail_encrypted_code_2.text() or "0", 16)
        except ValueError:
            channel.encrypted_code_2 = 0
        try:
            channel.encrypted_code_3 = int(self.detail_encrypted_code_3.text() or "0", 16)
        except ValueError:
            channel.encrypted_code_3 = 0

        # Refresh the table row
        self.table.blockSignals(True)
        self.populate_row(current_row, channel)
        self.table.blockSignals(False)

        self.data_modified.emit()

    def on_use_radio_id_changed(self):
        """Handle Use Radio ID checkbox state change"""
        # Enable/disable DMR ID spinbox based on checkbox state
        use_radio = self.detail_use_radio_id.isChecked()
        self.detail_dmr_id.setEnabled(not use_radio)
        # Trigger the detail changed handler to save the change
        self.on_detail_changed()

    def load_codeplug(self, codeplug: Codeplug):
        """Load channels from codeplug"""
        self.codeplug = codeplug
        self.populate_contact_dropdown()
        self.populate_group_list_dropdown()
        self.populate_encryption_dropdown()
        self.refresh_table()

    def populate_contact_dropdown(self):
        """Populate contact dropdown with contacts from codeplug"""
        self.detail_contact.blockSignals(True)
        self.detail_contact.clear()

        if not self.codeplug:
            self.detail_contact.addItem("None", 0)
            self.detail_contact.blockSignals(False)
            return

        # Add "None" option
        self.detail_contact.addItem("None", 0)

        # Add all contacts sorted by index
        contacts = sorted(self.codeplug.get_active_contacts(), key=lambda c: c.index)
        for contact in contacts:
            # Format: "Index: Name (Type) [DMR ID]"
            contact_label = f"{contact.index}: {contact.name} ({contact.contact_type.name}) [{contact.dmr_id}]"
            self.detail_contact.addItem(contact_label, contact.index)

        self.detail_contact.blockSignals(False)

    def populate_group_list_dropdown(self):
        """Populate group list dropdown with group lists from codeplug"""
        self.detail_group_list.blockSignals(True)
        self.detail_group_list.clear()

        if not self.codeplug:
            self.detail_group_list.addItem("None", 0)
            self.detail_group_list.blockSignals(False)
            return

        # Add "None" option
        self.detail_group_list.addItem("None", 0)

        # Add all group lists sorted by index
        group_lists = sorted(self.codeplug.get_active_group_lists(), key=lambda g: g.index)
        for group_list in group_lists:
            # Format: "Index: Name [X contacts]"
            contact_count = len(group_list.contacts) if group_list.contacts else 0
            group_label = f"{group_list.index}: {group_list.name} [{contact_count} contacts]"
            self.detail_group_list.addItem(group_label, group_list.index)

        self.detail_group_list.blockSignals(False)

    def populate_encryption_dropdown(self):
        """Populate encryption dropdown with encryption keys from codeplug"""
        self.detail_encrypt.blockSignals(True)
        self.detail_encrypt.clear()

        if not self.codeplug:
            self.detail_encrypt.addItem("None", 0)
            self.detail_encrypt.blockSignals(False)
            return

        # Add "None" option
        self.detail_encrypt.addItem("None", 0)

        # Add all encryption keys sorted by index
        keys = sorted(self.codeplug.get_active_encryption_keys(), key=lambda k: k.index)
        for key in keys:
            # Format: "Index: Alias (Type)"
            key_label = f"{key.index + 1}: {key.alias} ({key.enc_type.name.replace('_', '-')})"
            self.detail_encrypt.addItem(key_label, key.index)

        self.detail_encrypt.blockSignals(False)

    def refresh_table(self):
        """Refresh table from codeplug data"""
        if not self.codeplug:
            return

        self.table.blockSignals(True)  # Prevent triggering itemChanged
        self.table.setRowCount(0)

        channels = sorted(self.codeplug.get_active_channels(), key=lambda c: c.index)

        for row, channel in enumerate(channels):
            self.table.insertRow(row)
            self.populate_row(row, channel)

        self.table.blockSignals(False)

    def populate_row(self, row: int, channel: Channel):
        """Populate a table row with channel data"""
        # Index (read-only)
        item_index = QTableWidgetItem(str(channel.index + 1))
        item_index.setFlags(item_index.flags() & ~Qt.ItemIsEditable)
        item_index.setBackground(QColor(240, 240, 240))
        self.table.setItem(row, 0, item_index)

        # Name
        self.table.setItem(row, 1, QTableWidgetItem(channel.name))

        # RX Frequency
        self.table.setItem(row, 2, QTableWidgetItem(f"{channel.rx_freq:.5f}"))

        # TX Frequency
        self.table.setItem(row, 3, QTableWidgetItem(f"{channel.tx_freq:.5f}"))

        # Mode
        mode_str = "Digital" if channel.is_digital() else "Analog"
        item_mode = QTableWidgetItem(mode_str)
        self.table.setItem(row, 4, item_mode)

        # Power
        power_str = "High" if channel.power == PowerLevel.HIGH else "Low"
        self.table.setItem(row, 5, QTableWidgetItem(power_str))

        # Scan
        scan_str = "Add" if channel.scan == ScanMode.ADD else "Remove"
        self.table.setItem(row, 6, QTableWidgetItem(scan_str))

        # Color Code (DMR only)
        if channel.is_digital():
            self.table.setItem(row, 7, QTableWidgetItem(str(channel.dmr_color_code)))
            self.table.setItem(row, 8, QTableWidgetItem(str(channel.dmr_time_slot + 1)))
        else:
            item_cc = QTableWidgetItem("")
            item_cc.setFlags(item_cc.flags() & ~Qt.ItemIsEditable)
            item_cc.setBackground(QColor(240, 240, 240))
            self.table.setItem(row, 7, item_cc)

            item_slot = QTableWidgetItem("")
            item_slot.setFlags(item_slot.flags() & ~Qt.ItemIsEditable)
            item_slot.setBackground(QColor(240, 240, 240))
            self.table.setItem(row, 8, item_slot)

    def on_item_changed(self, item: QTableWidgetItem):
        """Handle cell editing"""
        if not self.codeplug:
            return

        row = item.row()
        col = item.column()

        # Get channel index from first column
        index_item = self.table.item(row, 0)
        if not index_item:
            return

        channel_index = int(index_item.text()) - 1
        channel = self.codeplug.get_channel(channel_index)

        if not channel:
            return

        try:
            # Update channel based on column
            if col == 1:  # Name
                channel.name = item.text()[:16]  # Max 16 chars
            elif col == 2:  # RX Freq
                channel.rx_freq = float(item.text())
            elif col == 3:  # TX Freq
                channel.tx_freq = float(item.text())
            elif col == 4:  # Mode
                mode_str = item.text().lower()
                if "digital" in mode_str or "dmr" in mode_str:
                    channel.mode = ChannelMode.DIGITAL
                else:
                    channel.mode = ChannelMode.ANALOG
            elif col == 5:  # Power
                power_str = item.text().lower()
                channel.power = PowerLevel.HIGH if "high" in power_str else PowerLevel.LOW
            elif col == 6:  # Scan
                scan_str = item.text().lower()
                channel.scan = ScanMode.ADD if "add" in scan_str else ScanMode.REMOVE
            elif col == 7 and channel.is_digital():  # Color Code
                channel.dmr_color_code = int(item.text())
            elif col == 8 and channel.is_digital():  # Time Slot
                channel.dmr_time_slot = int(item.text()) - 1  # 0-indexed

            self.data_modified.emit()

        except (ValueError, AttributeError) as e:
            QMessageBox.warning(self, "Invalid Value", f"Invalid value entered: {e}")
            self.refresh_table()  # Restore original value

    def on_rows_reordered(self):
        """Handle rows reordered via drag and drop"""
        if not self.codeplug:
            return

        # Get the current order of channels from the table
        reordered_channels = []
        for row in range(self.table.rowCount()):
            index_item = self.table.item(row, 0)
            if index_item:
                # Get the channel by its current index
                channel_index = int(index_item.text()) - 1
                channel = self.codeplug.get_channel(channel_index)
                if channel:
                    reordered_channels.append(channel)

        # Update channel indices to match their new positions
        for new_index, channel in enumerate(reordered_channels):
            channel.index = new_index

        # Replace the codeplug's channel list with the reordered list
        self.codeplug.channels = reordered_channels

        # Refresh the table to show updated indices
        self.refresh_table()

        # Emit data modified signal
        self.data_modified.emit()

    def on_copy_channel(self, row: int):
        """Handle channel copy (Ctrl+C)"""
        if not self.codeplug or row < 0:
            return

        # Get the channel at this row
        index_item = self.table.item(row, 0)
        if not index_item:
            return

        channel_index = int(index_item.text()) - 1
        channel = self.codeplug.get_channel(channel_index)

        if channel:
            # Make a deep copy of the channel
            self.copied_channel = copy.deepcopy(channel)
            # Show feedback in status bar if available
            if hasattr(self.window(), 'status_bar'):
                self.window().status_bar.showMessage(f"Copied channel: {channel.name}", 2000)

    def on_paste_channel(self, row: int):
        """Handle channel paste (Ctrl+V)"""
        if not self.codeplug or not self.copied_channel:
            if not self.copied_channel:
                QMessageBox.information(self, "Paste", "No channel copied. Use Ctrl+C to copy a channel first.")
            return

        # Find next available index
        existing_indices = [ch.index for ch in self.codeplug.channels]
        next_index = 0
        while next_index in existing_indices and next_index < 1024:
            next_index += 1

        if next_index >= 1024:
            QMessageBox.warning(self, "Warning", "Maximum channels reached (1024)")
            return

        # Create new channel from copied data
        new_channel = copy.deepcopy(self.copied_channel)
        new_channel.index = next_index
        new_channel.name = f"{self.copied_channel.name} Copy"

        # Add to codeplug
        self.codeplug.add_channel(new_channel)

        # If a row is selected, reorder to insert after it
        if row >= 0:
            # Get all channels
            channels = list(self.codeplug.channels)

            # Remove the newly added channel from its current position
            channels.remove(new_channel)

            # Insert it after the selected row
            insert_position = row + 1

            # Make sure insert position is valid
            if insert_position > len(channels):
                insert_position = len(channels)

            channels.insert(insert_position, new_channel)

            # Update indices to match new order
            for idx, channel in enumerate(channels):
                channel.index = idx

            # Replace channel list
            self.codeplug.channels = channels

        # Refresh table
        self.refresh_table()

        # Select the newly pasted channel
        if row >= 0:
            self.table.selectRow(row + 1)
        else:
            self.table.selectRow(self.table.rowCount() - 1)

        self.data_modified.emit()

    def on_delete_channel(self, row: int):
        """Handle channel delete (Delete key)"""
        if not self.codeplug or row < 0:
            return

        # Get the channel at this row
        index_item = self.table.item(row, 0)
        if not index_item:
            return

        channel_index = int(index_item.text()) - 1
        channel = self.codeplug.get_channel(channel_index)

        if channel:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete channel '{channel.name}'?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.codeplug.channels.remove(channel)

                # Update indices for remaining channels
                for idx, ch in enumerate(sorted(self.codeplug.channels, key=lambda c: c.index)):
                    ch.index = idx

                self.refresh_table()
                self.data_modified.emit()

    def add_channel(self):
        """Add a new channel"""
        if not self.codeplug:
            QMessageBox.warning(self, "Warning", "No codeplug loaded")
            return

        # Find next available index
        existing_indices = [ch.index for ch in self.codeplug.channels]
        next_index = 0
        while next_index in existing_indices and next_index < 1024:
            next_index += 1

        if next_index >= 1024:
            QMessageBox.warning(self, "Warning", "Maximum channels reached (1024)")
            return

        # Create new channel
        new_channel = Channel(
            index=next_index,
            name=f"CH-{next_index + 1}",
            rx_freq=433.500,
            tx_freq=433.500,
            mode=ChannelMode.ANALOG,
            power=PowerLevel.HIGH,
            scan=ScanMode.ADD,
            enabled=True
        )

        self.codeplug.add_channel(new_channel)
        self.refresh_table()
        self.data_modified.emit()

    def delete_channel(self):
        """Delete selected channel"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "No channel selected")
            return

        index_item = self.table.item(current_row, 0)
        channel_index = int(index_item.text()) - 1
        channel = self.codeplug.get_channel(channel_index)

        if channel:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete channel '{channel.name}'?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.codeplug.channels.remove(channel)
                self.refresh_table()
                self.data_modified.emit()

    def save_to_codeplug(self, codeplug: Codeplug):
        """Save current table state to codeplug (already saved via on_item_changed)"""
        # Data is already saved to self.codeplug via on_item_changed
        pass

    # CSV Helper Methods
    def _get_contact_name(self, index: int) -> str:
        """Get contact name by index"""
        if not self.codeplug or index <= 0:
            return 'None'
        contact = self.codeplug.get_contact(index - 1)
        return contact.name if contact else 'None'

    def _get_group_list_name(self, index: int) -> str:
        """Get group list name by index"""
        if not self.codeplug or index <= 0:
            return 'None'
        group_list = self.codeplug.get_group_list(index - 1)
        return group_list.name if group_list else 'None'

    def _get_encryption_name(self, index: int) -> str:
        """Get encryption key alias by index"""
        if not self.codeplug or index <= 0:
            return 'None'
        encrypt_key = self.codeplug.get_encryption_key(index - 1)
        return encrypt_key.alias if encrypt_key else 'None'

    def _get_dropdown_label(self, dropdown_values, value: int) -> str:
        """Get label from dropdown values list by value"""
        for label, val in dropdown_values:
            if val == value:
                return label
        return ''

    def _get_tot_label(self, tot_value: int) -> str:
        """Get TOT label from value"""
        from rt4d_codeplug.dropdowns import TOT_VALUES
        if tot_value == 0:
            return 'Off'
        for label, val in TOT_VALUES:
            if val == tot_value:
                return label
        return f"{tot_value}s"

    def _find_contact_index(self, name: str) -> int:
        """Find contact index by name"""
        if not self.codeplug or not name or name == 'None':
            return 0
        for contact in self.codeplug.contacts:
            if contact.name == name:
                return contact.index + 1
        return 0

    def _find_group_list_index(self, name: str) -> int:
        """Find group list index by name"""
        if not self.codeplug or not name or name == 'None':
            return 0
        for group_list in self.codeplug.group_lists:
            if group_list.name == name:
                return group_list.index + 1
        return 0

    def _find_encryption_index(self, alias: str) -> int:
        """Find encryption key index by alias"""
        if not self.codeplug or not alias or alias == 'None':
            return 0
        for encrypt_key in self.codeplug.encryption_keys:
            if encrypt_key.alias == alias:
                return encrypt_key.index + 1
        return 0

    def _find_dropdown_value(self, dropdown_values, label: str) -> int:
        """Find value from dropdown by label"""
        for lbl, val in dropdown_values:
            if lbl == label:
                return val
        return 0

    def _parse_tot_value(self, tot_str: str) -> int:
        """Parse TOT string to value"""
        from rt4d_codeplug.dropdowns import TOT_VALUES
        if not tot_str or tot_str == 'Off':
            return 0
        for label, val in TOT_VALUES:
            if label == tot_str:
                return val
        # Try parsing as number with 's' suffix
        if tot_str.endswith('s'):
            try:
                return int(tot_str[:-1])
            except ValueError:
                return 0
        return 0

    def on_import_csv_clicked(self):
        """Handle Import CSV button click"""
        if not self.codeplug:
            QMessageBox.warning(self, "Warning", "No codeplug loaded")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            self.import_csv(file_path)
            QMessageBox.information(self, "Success", "CSV imported successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import CSV:\n{e}")

    def on_export_csv_clicked(self):
        """Handle Export CSV button click"""
        if not self.codeplug:
            QMessageBox.warning(self, "Warning", "No codeplug loaded")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            self.export_csv(file_path)
            QMessageBox.information(self, "Success", f"Exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export CSV:\n{e}")

    def import_csv(self, file_path: str):
        """Import channels from CSV in RT-4D CPS format"""
        if not self.codeplug:
            raise ValueError("No codeplug loaded")

        from rt4d_codeplug.dropdowns import (
            TOT_VALUES, TX_PRIORITY_VALUES, DMR_MODE_VALUES, DMR_MONITOR_VALUES,
            BANDWIDTH_VALUES, TAIL_TONE_VALUES, SCRAMBLER_VALUES, CTDCS_SELECT_VALUES,
            ANALOG_MODULATION_VALUES
        )
        from rt4d_codeplug import AnalogModulation

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    # Parse channel number
                    index = int(row.get('Channel Number', 0)) - 1
                    if index < 0 or index >= 1024:
                        print(f"Warning: Invalid channel number {index + 1}, skipping")
                        continue

                    # Check if channel exists
                    channel = self.codeplug.get_channel(index)
                    if not channel:
                        channel = Channel(index=index, enabled=True)
                        self.codeplug.add_channel(channel)

                    # Common fields
                    channel.name = row.get('Channel Name', '')[:16]
                    channel.rx_freq = float(row.get('Rx Frequency', 0))
                    channel.tx_freq = float(row.get('Tx Frequency', 0))

                    # Channel type
                    channel_type = row.get('Channel Type', 'Analog')
                    channel.mode = ChannelMode.DIGITAL if channel_type == 'Digital' else ChannelMode.ANALOG

                    # Power
                    power_str = row.get('Power', 'High')
                    channel.power = PowerLevel.HIGH if power_str == 'High' else PowerLevel.LOW

                    # Scan
                    scan_str = row.get('Scan Add', 'Add')
                    channel.scan = ScanMode.ADD if scan_str == 'Add' else ScanMode.REMOVE

                    if channel.is_digital():
                        # Digital-specific fields
                        tg_list = row.get('TG List', 'None')
                        channel.group_list_index = self._find_group_list_index(tg_list)

                        contact = row.get('Contact', 'None')
                        channel.contact_index = self._find_contact_index(contact)

                        dmr_encrypt = row.get('DMR Enrcypt', 'None')  # Note: typo in original format
                        channel.encrypt_index = self._find_encryption_index(dmr_encrypt)

                        dmr_mode = row.get('DMR Mode', 'Dual-slot off')
                        channel.dmr_mode = self._find_dropdown_value(DMR_MODE_VALUES, dmr_mode)

                        timeslot_str = row.get('Timeslot', '1')
                        channel.dmr_time_slot = int(timeslot_str) - 1 if timeslot_str else 0

                        colour_code_str = row.get('Colour Code', '1')
                        channel.dmr_color_code = int(colour_code_str) if colour_code_str else 1

                        dmr_politely_tx = row.get('DMR Politely TX', 'No Restriction')
                        channel.tx_priority = self._find_dropdown_value(TX_PRIORITY_VALUES, dmr_politely_tx)

                        dmr_tot = row.get('DMR TOT', 'Off')
                        channel.tot = self._parse_tot_value(dmr_tot)

                        promiscuos_mode = row.get('Promiscuos Mode', 'Off')
                        channel.dmr_monitor = self._find_dropdown_value(DMR_MONITOR_VALUES, promiscuos_mode)

                        channel_id_str = row.get('Channel ID', '0')
                        channel.dmr_id = int(channel_id_str) if channel_id_str else 0

                        id_select = row.get('ID Select', 'Radio ID')
                        channel.use_radio_id = (id_select == 'Radio ID')

                    else:
                        # Analog-specific fields
                        channel.rx_ctcss = row.get('RX TONE', None) or None
                        channel.tx_ctcss = row.get('TX TONE', None) or None

                        bandwidth_str = row.get('Bandwidth (kHz)', '25')
                        channel.bandwidth = 1 if bandwidth_str == '12.5' else 0

                        busy_lock = row.get('Busy Lock', 'No Restriction')
                        channel.tx_priority_analog = self._find_dropdown_value(TX_PRIORITY_VALUES, busy_lock)

                        ana_tot = row.get('ANA TOT', 'Off')
                        channel.tot_analog = self._parse_tot_value(ana_tot)

                        tail_tone = row.get('Tail Tone', 'Off')
                        channel.tail_tone = self._find_dropdown_value(TAIL_TONE_VALUES, tail_tone)

                        scrambler = row.get('Scrambler', 'Off')
                        channel.scramble = self._find_dropdown_value(SCRAMBLER_VALUES, scrambler)

                        dcs_type = row.get('DCS Type', 'Normal Sub-tone')
                        channel.ctdcs_select = self._find_dropdown_value(CTDCS_SELECT_VALUES, dcs_type)

                        mute_code_1_str = row.get('ANA Mute Code 1', '')
                        channel.encrypted_code_1 = int(mute_code_1_str, 16) if mute_code_1_str else 0

                        mute_code_2_str = row.get('ANA Mute Code 2', '')
                        channel.encrypted_code_2 = int(mute_code_2_str, 16) if mute_code_2_str else 0

                        mute_code_3_str = row.get('ANA Mute Code 3', '')
                        channel.encrypted_code_3 = int(mute_code_3_str, 16) if mute_code_3_str else 0

                        am_fm_rx = row.get('AM_FM RX', 'FM')
                        channel.analog_modulation = AnalogModulation(self._find_dropdown_value(ANALOG_MODULATION_VALUES, am_fm_rx))

                except (ValueError, KeyError) as e:
                    print(f"Warning: Skipping invalid row at channel {row.get('Channel Number', '?')}: {e}")
                    continue

        self.refresh_table()
        self.data_modified.emit()

    def export_csv(self, file_path: str):
        """Export channels to CSV in RT-4D CPS format"""
        if not self.codeplug:
            raise ValueError("No codeplug loaded")

        from rt4d_codeplug.dropdowns import (
            TOT_VALUES, TX_PRIORITY_VALUES, DMR_MODE_VALUES, DMR_MONITOR_VALUES,
            BANDWIDTH_VALUES, TAIL_TONE_VALUES, SCRAMBLER_VALUES, CTDCS_SELECT_VALUES,
            ANALOG_MODULATION_VALUES
        )

        channels = sorted(self.codeplug.get_active_channels(), key=lambda c: c.index)

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write header matching RT-4D CPS format
            writer.writerow([
                'Channel Number', 'Rx Frequency', 'Tx Frequency', 'Channel Type', 'Power', 'Scan Add',
                'Channel Name', 'TG List', 'Contact', 'DMR Enrcypt', 'DMR Mode', 'Timeslot', 'Colour Code',
                'DMR Politely TX', 'DMR TOT', 'Promiscuos Mode', 'Channel ID', 'ID Select',
                'RX TONE', 'TX TONE', 'Bandwidth (kHz)', 'Busy Lock', 'ANA TOT', 'Tail Tone', 'Scrambler',
                'DCS Type', 'ANA Mute Code 1', 'ANA Mute Code 2', 'ANA Mute Code 3', 'AM_FM RX'
            ])

            for ch in channels:
                # Common fields
                channel_num = ch.index + 1
                rx_freq = f"{ch.rx_freq:.5f}"
                tx_freq = f"{ch.tx_freq:.5f}"
                channel_type = 'Digital' if ch.is_digital() else 'Analog'
                power = 'High' if ch.power == PowerLevel.HIGH else 'Low'
                scan_add = 'Add' if ch.scan == ScanMode.ADD else 'Remove'
                channel_name = ch.name

                # Digital-specific fields
                if ch.is_digital():
                    tg_list = self._get_group_list_name(ch.group_list_index) if ch.group_list_index > 0 else 'None'
                    contact = self._get_contact_name(ch.contact_index) if ch.contact_index > 0 else 'None'
                    dmr_encrypt = self._get_encryption_name(ch.encrypt_index) if ch.encrypt_index > 0 else 'None'
                    dmr_mode = self._get_dropdown_label(DMR_MODE_VALUES, ch.dmr_mode)
                    timeslot = ch.dmr_time_slot + 1
                    colour_code = ch.dmr_color_code
                    dmr_politely_tx = self._get_dropdown_label(TX_PRIORITY_VALUES, ch.tx_priority)
                    dmr_tot = self._get_tot_label(ch.tot)
                    promiscuos_mode = self._get_dropdown_label(DMR_MONITOR_VALUES, ch.dmr_monitor)
                    channel_id = ch.dmr_id
                    id_select = 'Radio ID' if ch.use_radio_id else 'Channel ID'
                    rx_tone = ''
                    tx_tone = ''
                    bandwidth = ''
                    busy_lock = ''
                    ana_tot = ''
                    tail_tone = ''
                    scrambler = ''
                    dcs_type = ''
                    mute_code_1 = ''
                    mute_code_2 = ''
                    mute_code_3 = ''
                    am_fm_rx = ''
                else:
                    # Analog-specific fields
                    tg_list = ''
                    contact = ''
                    dmr_encrypt = ''
                    dmr_mode = ''
                    timeslot = ''
                    colour_code = ''
                    dmr_politely_tx = ''
                    dmr_tot = ''
                    promiscuos_mode = ''
                    channel_id = ''
                    id_select = ''
                    rx_tone = ch.rx_ctcss or ''
                    tx_tone = ch.tx_ctcss or ''
                    bandwidth = '12.5' if ch.bandwidth == 1 else '25'
                    busy_lock = self._get_dropdown_label(TX_PRIORITY_VALUES, ch.tx_priority_analog)
                    ana_tot = self._get_tot_label(ch.tot_analog)
                    tail_tone = self._get_dropdown_label(TAIL_TONE_VALUES, ch.tail_tone)
                    scrambler = self._get_dropdown_label(SCRAMBLER_VALUES, ch.scramble)
                    dcs_type = self._get_dropdown_label(CTDCS_SELECT_VALUES, ch.ctdcs_select)
                    mute_code_1 = f"{ch.encrypted_code_1:08X}" if ch.encrypted_code_1 else ''
                    mute_code_2 = f"{ch.encrypted_code_2:08X}" if ch.encrypted_code_2 else ''
                    mute_code_3 = f"{ch.encrypted_code_3:08X}" if ch.encrypted_code_3 else ''
                    am_fm_rx = self._get_dropdown_label(ANALOG_MODULATION_VALUES, ch.analog_modulation.value)

                writer.writerow([
                    channel_num, rx_freq, tx_freq, channel_type, power, scan_add,
                    channel_name, tg_list, contact, dmr_encrypt, dmr_mode, timeslot, colour_code,
                    dmr_politely_tx, dmr_tot, promiscuos_mode, channel_id, id_select,
                    rx_tone, tx_tone, bandwidth, busy_lock, ana_tot, tail_tone, scrambler,
                    dcs_type, mute_code_1, mute_code_2, mute_code_3, am_fm_rx
                ])
