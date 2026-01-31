"""Channel Table Widget with drag-and-drop support"""

import csv
import copy
import logging
from typing import Optional

# Debug logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox, QMessageBox, QSplitter, QGroupBox, QFormLayout,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QLabel, QScrollArea,
    QFileDialog, QCompleter, QSizePolicy, QStyledItemDelegate
)
from PySide6.QtCore import Qt, Signal, QRegularExpression, QStringListModel
from PySide6.QtGui import QColor, QDropEvent, QKeyEvent, QKeySequence, QRegularExpressionValidator

from rt4d_codeplug import Codeplug, Channel, ChannelMode, PowerLevel, ScanMode
from rt4d_codeplug.dropdowns import (
    TOT_VALUES, TX_PRIORITY_VALUES, ALARM_VALUES, SCRAMBLER_VALUES,
    CTCSS_DCS_VALUES, BANDWIDTH_VALUES, CTDCS_SELECT_VALUES, TAIL_TONE_VALUES,
    DMR_MONITOR_VALUES, DMR_MODE_VALUES, ANALOG_MODULATION_VALUES, RX_TX_VALUES
)
from .options_dialog import OptionsDialog


class DraggableTableWidget(QTableWidget):
    """Table widget that supports drag-and-drop reordering"""

    rows_reordered = Signal(int, int)  # source_row, target_row
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
        if source_row == target_row:
            event.ignore()
            return

        # Accept the event
        event.accept()

        # Emit signal with source and target rows BEFORE moving
        # The handler will update positions, which triggers refresh
        self.rows_reordered.emit(source_row, target_row)

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


class NameColumnDelegate(QStyledItemDelegate):
    """Delegate that enforces a max character length on the name column editor."""

    def __init__(self, max_length=16, parent=None):
        super().__init__(parent)
        self._max_length = max_length

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setMaxLength(self._max_length)
        return editor


class ChannelTableWidget(QWidget):
    """Widget for displaying and editing channels"""

    data_modified = Signal()

    # Frequency constants
    FREQ_MULTIPLIER = 100000  # 10 Hz units
    DEFAULT_RX_FREQ_MHZ = 433.500  # Default UHF frequency for new channels

    @staticmethod
    def _freq_to_mhz(freq_int: int) -> float:
        """Convert internal frequency (10 Hz units) to MHz for display."""
        return freq_int / ChannelTableWidget.FREQ_MULTIPLIER

    @staticmethod
    def _mhz_to_freq(freq_mhz: float) -> int:
        """Convert MHz to internal frequency (10 Hz units)."""
        return round(freq_mhz * ChannelTableWidget.FREQ_MULTIPLIER)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.codeplug: Optional[Codeplug] = None
        self.copied_channel: Optional[Channel] = None
        self._tx_manually_edited: bool = False  # Track if TX was manually edited
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
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Pos", "Name", "RX Freq", "TX Freq", "Mode", "Power",
            "Scan", "Color Code", "Time Slot", "TX Tone"
        ])

        # Configure table
        self.table.setItemDelegateForColumn(1, NameColumnDelegate(16, self.table))
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)

        # Resize columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Index
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Name
        for i in range(2, 10):
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

        # Reorder/Sort buttons
        reorder_layout = QHBoxLayout()

        self.btn_move_up = QPushButton("Move Up")
        self.btn_move_up.clicked.connect(self.move_channel_up)
        reorder_layout.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton("Move Down")
        self.btn_move_down.clicked.connect(self.move_channel_down)
        reorder_layout.addWidget(self.btn_move_down)

        reorder_layout.addStretch()

        # Filter input
        filter_label = QLabel("Filter:")
        reorder_layout.addWidget(filter_label)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Search by name...")
        self.filter_input.setMaximumWidth(150)
        self.filter_input.textChanged.connect(self.on_filter_changed)
        reorder_layout.addWidget(self.filter_input)

        self.btn_clear_filter = QPushButton("Clear")
        self.btn_clear_filter.clicked.connect(self.clear_filter)
        reorder_layout.addWidget(self.btn_clear_filter)

        reorder_layout.addStretch()

        self.btn_sort_name = QPushButton("Sort: Name")
        self.btn_sort_name.clicked.connect(self.sort_by_name)
        reorder_layout.addWidget(self.btn_sort_name)

        self.btn_sort_rx = QPushButton("Sort: RX Freq")
        self.btn_sort_rx.clicked.connect(self.sort_by_rx_freq)
        reorder_layout.addWidget(self.btn_sort_rx)

        self.btn_sort_tx = QPushButton("Sort: TX Freq")
        self.btn_sort_tx.clicked.connect(self.sort_by_tx_freq)
        reorder_layout.addWidget(self.btn_sort_tx)

        left_layout.addLayout(reorder_layout)

        # Right side: Details panel
        self.details_panel = self.create_details_panel()

        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(self.details_panel)
        left_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.details_panel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        splitter.setStretchFactor(0, 6)  # Table takes 6/11
        splitter.setStretchFactor(1, 5)  # Details takes 5/11

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
        self.detail_rx_freq.valueChanged.connect(self.on_rx_freq_changed)
        basic_layout.addRow("RX Frequency:", self.detail_rx_freq)

        self.detail_tx_freq = QDoubleSpinBox()
        self.detail_tx_freq.setRange(0, 1000)
        self.detail_tx_freq.setDecimals(5)
        self.detail_tx_freq.setSuffix(" MHz")
        self.detail_tx_freq.valueChanged.connect(self.on_tx_freq_changed)
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

        self.detail_rx_tx = QComboBox()
        for label, value in RX_TX_VALUES:
            self.detail_rx_tx.addItem(label, value)
        self.detail_rx_tx.currentIndexChanged.connect(self.on_detail_changed)
        basic_layout.addRow("RX/TX Permission:", self.detail_rx_tx)

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
        dmr_layout.addRow("DCDM:", self.detail_dmr_mode)

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
        self.detail_tot.setEditable(True)
        self.detail_tot.setInsertPolicy(QComboBox.NoInsert)
        for label, value in TOT_VALUES:
            self.detail_tot.addItem(label, value)
        # Add completer for type-to-filter
        tot_labels = [label for label, _ in TOT_VALUES]
        tot_completer = QCompleter(tot_labels)
        tot_completer.setCaseSensitivity(Qt.CaseInsensitive)
        tot_completer.setFilterMode(Qt.MatchContains)
        self.detail_tot.setCompleter(tot_completer)
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
        self.detail_rx_ctcss.setEditable(True)
        self.detail_rx_ctcss.setInsertPolicy(QComboBox.NoInsert)  # Don't allow custom values
        for value in CTCSS_DCS_VALUES:
            self.detail_rx_ctcss.addItem(value)
        # Add completer for type-to-filter
        rx_completer = QCompleter(CTCSS_DCS_VALUES)
        rx_completer.setCaseSensitivity(Qt.CaseInsensitive)
        rx_completer.setFilterMode(Qt.MatchContains)
        self.detail_rx_ctcss.setCompleter(rx_completer)
        self.detail_rx_ctcss.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("RX CTCSS/DCS:", self.detail_rx_ctcss)

        self.detail_tx_ctcss = QComboBox()
        self.detail_tx_ctcss.setEditable(True)
        self.detail_tx_ctcss.setInsertPolicy(QComboBox.NoInsert)  # Don't allow custom values
        for value in CTCSS_DCS_VALUES:
            self.detail_tx_ctcss.addItem(value)
        # Add completer for type-to-filter
        tx_completer = QCompleter(CTCSS_DCS_VALUES)
        tx_completer.setCaseSensitivity(Qt.CaseInsensitive)
        tx_completer.setFilterMode(Qt.MatchContains)
        self.detail_tx_ctcss.setCompleter(tx_completer)
        self.detail_tx_ctcss.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("TX CTCSS/DCS:", self.detail_tx_ctcss)

        self.detail_scramble = QComboBox()
        for label, value in SCRAMBLER_VALUES:
            self.detail_scramble.addItem(label, value)
        self.detail_scramble.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("Scrambler:", self.detail_scramble)

        self.detail_modulation = QComboBox()
        for label, value in ANALOG_MODULATION_VALUES:
            self.detail_modulation.addItem(label, value)
        self.detail_modulation.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("Modulation:", self.detail_modulation)

        self.detail_bandwidth = QComboBox()
        for label, value in BANDWIDTH_VALUES:
            self.detail_bandwidth.addItem(label, value)
        self.detail_bandwidth.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("Bandwidth:", self.detail_bandwidth)

        self.detail_tx_priority_analog = QComboBox()
        for label, value in TX_PRIORITY_VALUES:
            self.detail_tx_priority_analog.addItem(label, value)
        self.detail_tx_priority_analog.currentIndexChanged.connect(self.on_detail_changed)
        analog_layout.addRow("TX Priority:", self.detail_tx_priority_analog)

        self.detail_tot_analog = QComboBox()
        self.detail_tot_analog.setEditable(True)
        self.detail_tot_analog.setInsertPolicy(QComboBox.NoInsert)
        for label, value in TOT_VALUES:
            self.detail_tot_analog.addItem(label, value)
        # Add completer for type-to-filter
        tot_analog_labels = [label for label, _ in TOT_VALUES]
        tot_analog_completer = QCompleter(tot_analog_labels)
        tot_analog_completer.setCaseSensitivity(Qt.CaseInsensitive)
        tot_analog_completer.setFilterMode(Qt.MatchContains)
        self.detail_tot_analog.setCompleter(tot_analog_completer)
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

        self.detail_mute_code = QLineEdit()
        self.detail_mute_code.setPlaceholderText("00000000")
        self.detail_mute_code.setMaxLength(8)
        self.detail_mute_code.setValidator(hex_validator)
        self.detail_mute_code.textChanged.connect(self.on_detail_changed)
        analog_layout.addRow("Mute Code:", self.detail_mute_code)

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
        self.dmr_group.setEnabled(enabled)
        self.analog_group.setEnabled(enabled)

    def on_selection_changed(self):
        """Handle table selection change"""
        current_row = self.table.currentRow()
        logger.debug(f"on_selection_changed: current_row={current_row}")
        if current_row < 0:
            self.set_details_enabled(False)
            return

        # Get selected channel by UUID
        index_item = self.table.item(current_row, 0)
        if not index_item:
            logger.debug("on_selection_changed: no index_item, returning")
            return

        channel_uuid = index_item.data(Qt.UserRole)
        channel = self.codeplug.get_channel(channel_uuid)
        logger.debug(f"on_selection_changed: uuid={channel_uuid[:8]}..., channel found={channel is not None}")

        if channel:
            logger.debug(f"on_selection_changed: loading details - name={channel.name}, rx={channel.rx_freq}, tx={channel.tx_freq}")
            self.load_channel_details(channel)
            self.set_details_enabled(True)

    def reload_current_channel_details(self):
        """Reload details for currently displayed channel (useful after dropdown refresh)"""
        current_row = self.table.currentRow()
        if current_row < 0 or not self.codeplug:
            return

        # Get selected channel by UUID
        index_item = self.table.item(current_row, 0)
        if not index_item:
            return

        channel_uuid = index_item.data(Qt.UserRole)
        channel = self.codeplug.get_channel(channel_uuid)

        if channel:
            self.load_channel_details(channel)

    def load_channel_details(self, channel: Channel):
        """Load channel data into details panel"""
        logger.debug(f"load_channel_details: CALLED with name={channel.name}, rx={channel.rx_freq}, tx={channel.tx_freq}")
        # Block signals while loading
        self.detail_name.blockSignals(True)
        self.detail_rx_freq.blockSignals(True)
        self.detail_tx_freq.blockSignals(True)
        self.detail_mode.blockSignals(True)
        self.detail_power.blockSignals(True)
        self.detail_scan.blockSignals(True)
        self.detail_rx_tx.blockSignals(True)
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
        self.detail_modulation.blockSignals(True)
        self.detail_bandwidth.blockSignals(True)
        self.detail_tx_priority_analog.blockSignals(True)
        self.detail_tot_analog.blockSignals(True)
        self.detail_ctdcs_select.blockSignals(True)
        self.detail_tail_tone.blockSignals(True)
        self.detail_mute_code.blockSignals(True)

        # Load basic settings
        self.detail_name.setText(channel.name)
        self.detail_rx_freq.setValue(self._freq_to_mhz(channel.rx_freq))
        self.detail_tx_freq.setValue(self._freq_to_mhz(channel.tx_freq))
        self.detail_mode.setCurrentIndex(1 if channel.is_digital() else 0)
        self.detail_power.setCurrentIndex(0 if channel.power == PowerLevel.HIGH else 1)
        self.detail_scan.setCurrentIndex(0 if channel.scan == ScanMode.ADD else 1)
        # RX/TX Permission - find index by value
        for i in range(self.detail_rx_tx.count()):
            if self.detail_rx_tx.itemData(i) == channel.rx_tx:
                self.detail_rx_tx.setCurrentIndex(i)
                break

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
        # Contact - find dropdown index by contact_uuid value
        contact_found = False
        for i in range(self.detail_contact.count()):
            if self.detail_contact.itemData(i) == channel.contact_uuid:
                self.detail_contact.setCurrentIndex(i)
                contact_found = True
                break
        if not contact_found:
            self.detail_contact.setCurrentIndex(0)  # Default to "None"
        # Group List - find dropdown index by group_list_uuid value
        group_list_found = False
        for i in range(self.detail_group_list.count()):
            if self.detail_group_list.itemData(i) == channel.group_list_uuid:
                self.detail_group_list.setCurrentIndex(i)
                group_list_found = True
                break
        if not group_list_found:
            self.detail_group_list.setCurrentIndex(0)  # Default to "None"
        # Encryption - find dropdown index by encrypt_uuid value
        encrypt_found = False
        for i in range(self.detail_encrypt.count()):
            if self.detail_encrypt.itemData(i) == channel.encrypt_uuid:
                self.detail_encrypt.setCurrentIndex(i)
                encrypt_found = True
                break
        if not encrypt_found:
            self.detail_encrypt.setCurrentIndex(0)  # Default to "None"
        # DMR Busy Lock - find index by value
        for i in range(self.detail_tx_priority.count()):
            if self.detail_tx_priority.itemData(i) == channel.dmr_busy_lock:
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
        # Modulation (FM/AM/SSB)
        for i in range(self.detail_modulation.count()):
            if self.detail_modulation.itemData(i) == channel.analog_modulation.value:
                self.detail_modulation.setCurrentIndex(i)
                break
        # Bandwidth
        for i in range(self.detail_bandwidth.count()):
            if self.detail_bandwidth.itemData(i) == channel.bandwidth:
                self.detail_bandwidth.setCurrentIndex(i)
                break
        # Analog Busy Lock
        for i in range(self.detail_tx_priority_analog.count()):
            if self.detail_tx_priority_analog.itemData(i) == channel.ana_busy_lock:
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
        self.detail_mute_code.setText(f"{channel.mute_code:08X}")

        # Show/hide groups based on mode
        self.dmr_group.setVisible(channel.is_digital())
        self.analog_group.setVisible(channel.is_analog())

        # Reset auto-shift tracking for newly loaded channel
        self._tx_manually_edited = False

        # Unblock signals
        self.detail_name.blockSignals(False)
        self.detail_rx_freq.blockSignals(False)
        self.detail_tx_freq.blockSignals(False)
        self.detail_mode.blockSignals(False)
        self.detail_power.blockSignals(False)
        self.detail_scan.blockSignals(False)
        self.detail_rx_tx.blockSignals(False)
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
        self.detail_modulation.blockSignals(False)
        self.detail_bandwidth.blockSignals(False)
        self.detail_tx_priority_analog.blockSignals(False)
        self.detail_tot_analog.blockSignals(False)
        self.detail_ctdcs_select.blockSignals(False)
        self.detail_tail_tone.blockSignals(False)
        self.detail_mute_code.blockSignals(False)

    def on_mode_changed(self):
        """Handle mode change - preserve all basic settings during mode switch"""
        logger.debug("on_mode_changed: STARTING")

        # Get current channel - read values from channel object (not UI) since
        # table cell edits update the channel but not the details panel
        current_row = self.table.currentRow()
        if current_row < 0 or not self.codeplug:
            logger.debug("on_mode_changed: no row or codeplug, returning")
            return

        index_item = self.table.item(current_row, 0)
        if not index_item:
            logger.debug("on_mode_changed: no index_item, returning")
            return

        channel_uuid = index_item.data(Qt.UserRole)
        channel = self.codeplug.get_channel(channel_uuid)
        if not channel:
            logger.debug("on_mode_changed: channel not found, returning")
            return

        # Capture values from CHANNEL OBJECT (authoritative source)
        # This ensures we preserve table cell edits that didn't update the details panel
        name = channel.name
        rx_freq = channel.rx_freq
        tx_freq = channel.tx_freq
        power = channel.power
        scan = channel.scan
        logger.debug(f"on_mode_changed: captured from channel - name={name}, rx={rx_freq}, tx={tx_freq}")

        # Show/hide groups based on mode
        is_digital = self.detail_mode.currentIndex() == 1
        logger.debug(f"on_mode_changed: switching to {'Digital' if is_digital else 'Analog'}")
        self.dmr_group.setVisible(is_digital)
        self.analog_group.setVisible(not is_digital)

        # Restore all basic settings to the UI from the channel object
        self.detail_name.blockSignals(True)
        self.detail_rx_freq.blockSignals(True)
        self.detail_tx_freq.blockSignals(True)
        self.detail_power.blockSignals(True)
        self.detail_scan.blockSignals(True)

        self.detail_name.setText(name)
        self.detail_rx_freq.setValue(self._freq_to_mhz(rx_freq))
        self.detail_tx_freq.setValue(self._freq_to_mhz(tx_freq))
        self.detail_power.setCurrentIndex(0 if power == PowerLevel.HIGH else 1)
        self.detail_scan.setCurrentIndex(0 if scan == ScanMode.ADD else 1)

        self.detail_name.blockSignals(False)
        self.detail_rx_freq.blockSignals(False)
        self.detail_tx_freq.blockSignals(False)
        self.detail_power.blockSignals(False)
        self.detail_scan.blockSignals(False)

        logger.debug(f"on_mode_changed: after restore - name={self.detail_name.text()}, rx={self.detail_rx_freq.value()}, tx={self.detail_tx_freq.value()}")
        logger.debug("on_mode_changed: calling on_detail_changed")
        self.on_detail_changed()
        logger.debug("on_mode_changed: FINISHED")

    def on_rx_freq_changed(self):
        """Handle RX frequency change - auto-update TX if not manually edited"""
        # Check if auto-shift should update TX
        if not self._tx_manually_edited:
            new_rx = self.detail_rx_freq.value()
            new_tx = OptionsDialog.calculate_tx_freq(new_rx)

            # Only update if TX would actually change (auto-shift is enabled and in range)
            if abs(new_tx - new_rx) > 0.0001:  # Shift was applied
                self.detail_tx_freq.blockSignals(True)
                self.detail_tx_freq.setValue(new_tx)
                self.detail_tx_freq.blockSignals(False)

        self.on_detail_changed()

    def on_tx_freq_changed(self):
        """Handle TX frequency change - mark as manually edited"""
        self._tx_manually_edited = True
        self.on_detail_changed()

    def on_detail_changed(self):
        """Handle detail field changes"""
        current_row = self.table.currentRow()
        logger.debug(f"on_detail_changed: current_row={current_row}, codeplug={self.codeplug is not None}")
        if current_row < 0 or not self.codeplug:
            logger.debug("on_detail_changed: early return (no row or codeplug)")
            return

        # Get channel by UUID
        index_item = self.table.item(current_row, 0)
        if not index_item:
            logger.debug("on_detail_changed: no index_item, returning")
            return

        channel_uuid = index_item.data(Qt.UserRole)
        channel = self.codeplug.get_channel(channel_uuid)
        logger.debug(f"on_detail_changed: uuid={channel_uuid[:8]}..., channel found={channel is not None}")

        if not channel:
            logger.debug("on_detail_changed: channel not found, returning")
            return

        # Log UI values before saving
        ui_name = self.detail_name.text()[:16]
        ui_rx = self.detail_rx_freq.value()
        ui_tx = self.detail_tx_freq.value()
        logger.debug(f"on_detail_changed: UI values - name={ui_name}, rx={ui_rx}, tx={ui_tx}")
        logger.debug(f"on_detail_changed: channel BEFORE - name={channel.name}, rx={channel.rx_freq}, tx={channel.tx_freq}")

        # Update channel from details
        channel.name = self.detail_name.text()[:16]
        channel.rx_freq = self._mhz_to_freq(self.detail_rx_freq.value())
        channel.tx_freq = self._mhz_to_freq(self.detail_tx_freq.value())
        logger.debug(f"on_detail_changed: channel AFTER - name={channel.name}, rx={channel.rx_freq}, tx={channel.tx_freq}")
        channel.mode = ChannelMode.DIGITAL if self.detail_mode.currentIndex() == 1 else ChannelMode.ANALOG
        channel.power = PowerLevel.HIGH if self.detail_power.currentIndex() == 0 else PowerLevel.LOW
        channel.scan = ScanMode.ADD if self.detail_scan.currentIndex() == 0 else ScanMode.REMOVE
        channel.rx_tx = self.detail_rx_tx.currentData()

        # DMR settings
        channel.dmr_time_slot = self.detail_time_slot.currentIndex()
        channel.dmr_color_code = self.detail_color_code.value()
        channel.dmr_mode = self.detail_dmr_mode.currentData()
        channel.dmr_monitor = self.detail_dmr_monitor.currentData()
        channel.contact_uuid = self.detail_contact.currentData() if self.detail_contact.currentData() is not None else ""
        channel.group_list_uuid = self.detail_group_list.currentData() if self.detail_group_list.currentData() is not None else ""
        channel.encrypt_uuid = self.detail_encrypt.currentData() if self.detail_encrypt.currentData() is not None else ""
        channel.dmr_busy_lock = self.detail_tx_priority.currentData()
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
        # Modulation (FM/AM/SSB)
        from rt4d_codeplug import AnalogModulation
        modulation_value = self.detail_modulation.currentData()
        channel.analog_modulation = AnalogModulation(modulation_value) if modulation_value is not None else AnalogModulation.FM
        channel.bandwidth = self.detail_bandwidth.currentData()
        channel.ana_busy_lock = self.detail_tx_priority_analog.currentData()
        channel.tot_analog = self.detail_tot_analog.currentData()
        channel.ctdcs_select = self.detail_ctdcs_select.currentData()
        channel.tail_tone = self.detail_tail_tone.currentData()
        # Encrypted codes - parse as hex integers
        try:
            channel.mute_code = int(self.detail_mute_code.text() or "0", 16)
        except ValueError:
            channel.mute_code = 0

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
            self.detail_contact.addItem("None", "")
            self.detail_contact.blockSignals(False)
            return

        # Add "None" option (empty UUID)
        self.detail_contact.addItem("None", "")

        # Add all contacts sorted by index (for display order)
        contacts = sorted(self.codeplug.get_active_contacts(), key=lambda c: c.index)
        for contact in contacts:
            # Format: "Index: Name (Type) [DMR ID]" - display index for user, store UUID
            contact_label = f"{contact.index}: {contact.name} ({contact.contact_type.name}) [{contact.dmr_id}]"
            self.detail_contact.addItem(contact_label, contact.uuid)

        self.detail_contact.blockSignals(False)

    def populate_group_list_dropdown(self):
        """Populate group list dropdown with group lists from codeplug"""
        self.detail_group_list.blockSignals(True)
        self.detail_group_list.clear()

        if not self.codeplug:
            self.detail_group_list.addItem("None", "")
            self.detail_group_list.blockSignals(False)
            return

        # Add "None" option (empty UUID)
        self.detail_group_list.addItem("None", "")

        # Add all group lists sorted by index (for display order)
        group_lists = sorted(self.codeplug.get_active_group_lists(), key=lambda g: g.index)
        for group_list in group_lists:
            # Format: "Index: Name [X contacts]" - display index for user, store UUID
            contact_count = len(group_list.contacts) if group_list.contacts else 0
            group_label = f"{group_list.index}: {group_list.name} [{contact_count} contacts]"
            self.detail_group_list.addItem(group_label, group_list.uuid)

        self.detail_group_list.blockSignals(False)

    def populate_encryption_dropdown(self):
        """Populate encryption dropdown with encryption keys from codeplug"""
        self.detail_encrypt.blockSignals(True)
        self.detail_encrypt.clear()

        if not self.codeplug:
            self.detail_encrypt.addItem("None", "")
            self.detail_encrypt.blockSignals(False)
            return

        # Add "None" option (empty UUID)
        self.detail_encrypt.addItem("None", "")

        # Add all encryption keys sorted by index (for display order)
        keys = sorted(self.codeplug.get_active_encryption_keys(), key=lambda k: k.index)
        for key in keys:
            # Format: "Index: Alias (Type)" - display index for user, store UUID
            key_label = f"{key.index + 1}: {key.alias} ({key.enc_type.name.replace('_', '-')})"
            self.detail_encrypt.addItem(key_label, key.uuid)

        self.detail_encrypt.blockSignals(False)

    def refresh_table(self):
        """Refresh table from codeplug data"""
        if not self.codeplug:
            return

        self.table.blockSignals(True)  # Prevent triggering itemChanged
        self.table.setRowCount(0)

        # Always display channels sorted by position
        channels = self.codeplug.get_channels_sorted_by_position()

        # Apply filter if set
        filter_text = self.filter_input.text().strip().lower()
        if filter_text:
            channels = [ch for ch in channels if filter_text in ch.name.lower()]

        for row, channel in enumerate(channels):
            self.table.insertRow(row)
            self.populate_row(row, channel)

        self.table.blockSignals(False)

    def on_filter_changed(self):
        """Handle filter input text change"""
        self.refresh_table()

    def clear_filter(self):
        """Clear the filter input"""
        self.filter_input.clear()

    def populate_row(self, row: int, channel: Channel):
        """Populate a table row with channel data"""
        palette = self.table.palette()
        readonly_bg = palette.alternateBase().color()

        # Position (editable) - display the channel's memory position, store UUID
        item_position = QTableWidgetItem(str(channel.position))
        item_position.setData(Qt.UserRole, channel.uuid)  # Store UUID for lookup
        self.table.setItem(row, 0, item_position)

        # Name
        self.table.setItem(row, 1, QTableWidgetItem(channel.name))

        # RX Frequency
        self.table.setItem(row, 2, QTableWidgetItem(f"{self._freq_to_mhz(channel.rx_freq):.5f}"))

        # TX Frequency
        self.table.setItem(row, 3, QTableWidgetItem(f"{self._freq_to_mhz(channel.tx_freq):.5f}"))

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

            # TX Tone - empty for digital
            item_tone = QTableWidgetItem("")
            item_tone.setFlags(item_tone.flags() & ~Qt.ItemIsEditable)
            item_tone.setBackground(readonly_bg)
            self.table.setItem(row, 9, item_tone)
        else:
            item_cc = QTableWidgetItem("")
            item_cc.setFlags(item_cc.flags() & ~Qt.ItemIsEditable)
            item_cc.setBackground(readonly_bg)
            self.table.setItem(row, 7, item_cc)

            item_slot = QTableWidgetItem("")
            item_slot.setFlags(item_slot.flags() & ~Qt.ItemIsEditable)
            item_slot.setBackground(readonly_bg)
            self.table.setItem(row, 8, item_slot)

            # TX Tone - show CTCSS/DCS for analog
            tx_tone_str = channel.tx_ctcss if channel.tx_ctcss else "None"
            item_tone = QTableWidgetItem(tx_tone_str)
            item_tone.setFlags(item_tone.flags() & ~Qt.ItemIsEditable)  # Read-only in table
            self.table.setItem(row, 9, item_tone)

    def on_item_changed(self, item: QTableWidgetItem):
        """Handle cell editing"""
        if not self.codeplug:
            return

        row = item.row()
        col = item.column()

        # Get channel by UUID from first column
        index_item = self.table.item(row, 0)
        if not index_item:
            return

        channel_uuid = index_item.data(Qt.UserRole)
        channel = self.codeplug.get_channel(channel_uuid)

        if not channel:
            return

        try:
            # Update channel based on column
            if col == 0:  # Position
                new_position = int(item.text())
                if new_position < 1 or new_position > 1024:
                    raise ValueError("Position must be 1-1024")
                # Check for duplicate positions
                for ch in self.codeplug.channels:
                    if ch.uuid != channel.uuid and ch.position == new_position:
                        raise ValueError(f"Position {new_position} already used by '{ch.name}'")
                channel.position = new_position
                # Re-sort and refresh table since position changed
                self.refresh_table()
            elif col == 1:  # Name
                channel.name = item.text()[:16]  # Max 16 chars
            elif col == 2:  # RX Freq
                channel.rx_freq = self._mhz_to_freq(float(item.text()))
            elif col == 3:  # TX Freq
                channel.tx_freq = self._mhz_to_freq(float(item.text()))
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

            # Sync the details panel with the updated channel data
            # This ensures the details panel reflects table cell edits
            if row == self.table.currentRow():
                self.load_channel_details(channel)

            self.data_modified.emit()

        except (ValueError, AttributeError) as e:
            QMessageBox.warning(self, "Invalid Value", f"Invalid value entered: {e}")
            self.refresh_table()  # Restore original value

    def on_rows_reordered(self, source_row: int, target_row: int):
        """Handle rows reordered via drag and drop - swap positions"""
        if not self.codeplug:
            return

        channels = self.codeplug.get_channels_sorted_by_position()

        if source_row >= len(channels) or target_row > len(channels):
            return

        dragged = channels[source_row]
        old_pos = dragged.position

        # Determine target position
        if target_row < len(channels):
            target = channels[target_row]
            new_pos = target.position
        else:
            # Dropped at end
            max_pos = max(ch.position for ch in channels)
            new_pos = max_pos + 1

        if new_pos == old_pos:
            return  # No change needed

        # For adjacent positions (diff of 1), do a simple swap
        # This ensures symmetric behavior for both directions
        if abs(new_pos - old_pos) == 1:
            # Find the channel at the target position and swap
            for ch in channels:
                if ch.position == new_pos and ch.uuid != dragged.uuid:
                    ch.position = old_pos
                    break
            dragged.position = new_pos
            self.refresh_table()
            self.data_modified.emit()
            return

        # Get all used positions excluding the dragged channel
        used = self.codeplug.get_used_positions() - {old_pos}

        # If target position is occupied, shift channels to make room
        if new_pos in used:
            # Find channels that need to shift (from new_pos onwards)
            # Shift until we find a gap or reach max position
            channels_to_shift = [
                ch for ch in channels
                if ch.position >= new_pos and ch.uuid != dragged.uuid
            ]
            channels_to_shift.sort(key=lambda c: c.position)

            # Find the first gap after new_pos, or use max+1
            shift_end = new_pos
            for ch in channels_to_shift:
                if ch.position == shift_end:
                    shift_end += 1
                else:
                    break  # Found a gap

            # Check if we'd exceed max position
            if shift_end > 1024:
                QMessageBox.warning(self, "No Space", "Cannot shift - would exceed max position")
                return

            # Shift channels (work backwards to avoid collisions)
            for ch in reversed(channels_to_shift):
                if ch.position >= new_pos and ch.position < shift_end:
                    ch.position += 1

        # Set dragged channel to target position
        dragged.position = new_pos

        self.refresh_table()
        self.data_modified.emit()

    def on_copy_channel(self, row: int):
        """Handle channel copy (Ctrl+C)"""
        if not self.codeplug or row < 0:
            return

        # Get the channel at this row by UUID
        index_item = self.table.item(row, 0)
        if not index_item:
            return

        channel_uuid = index_item.data(Qt.UserRole)
        channel = self.codeplug.get_channel(channel_uuid)

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

        if len(self.codeplug.channels) >= 1024:
            QMessageBox.warning(self, "Warning", "Maximum channels reached (1024)")
            return

        # Get selected channel's position (or 0 if none)
        selected_pos = 0
        if row >= 0:
            index_item = self.table.item(row, 0)
            if index_item:
                channel_uuid = index_item.data(Qt.UserRole)
                selected_channel = self.codeplug.get_channel(channel_uuid)
                if selected_channel:
                    selected_pos = selected_channel.position

        # Find next free position after selection
        used = self.codeplug.get_used_positions()
        new_pos = selected_pos + 1 if selected_pos > 0 else 1

        while new_pos in used and new_pos <= 1024:
            new_pos += 1

        if new_pos > 1024:
            QMessageBox.warning(self, "Error", "No free channel positions")
            return

        # Create new channel from copied data with a new UUID and position
        from uuid import uuid4
        new_channel = copy.deepcopy(self.copied_channel)
        new_channel.uuid = str(uuid4())  # Generate new UUID for the copy
        new_channel.position = new_pos
        new_channel.name = f"{self.copied_channel.name} Copy"[:16]

        self.codeplug.add_channel(new_channel)

        # Refresh table
        self.refresh_table()

        # Select the newly pasted channel (find its row in the sorted table)
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.data(Qt.UserRole) == new_channel.uuid:
                self.table.selectRow(i)
                break

        self.data_modified.emit()

    def on_delete_channel(self, row: int):
        """Handle channel delete (Delete key)"""
        if not self.codeplug or row < 0:
            return

        # Get the channel at this row by UUID
        index_item = self.table.item(row, 0)
        if not index_item:
            return

        channel_uuid = index_item.data(Qt.UserRole)
        channel = self.codeplug.get_channel(channel_uuid)

        if channel:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete channel '{channel.name}'?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.codeplug.channels.remove(channel)
                # DO NOT modify indices - they are recalculated on save
                self.refresh_table()
                self.data_modified.emit()

    def add_channel(self):
        """Add a new channel after the selected position"""
        if not self.codeplug:
            QMessageBox.warning(self, "Warning", "No codeplug loaded")
            return

        if len(self.codeplug.channels) >= 1024:
            QMessageBox.warning(self, "Warning", "Maximum channels reached (1024)")
            return

        # Get selected channel's position (or 0 if none)
        selected_pos = 0
        current_row = self.table.currentRow()
        if current_row >= 0:
            index_item = self.table.item(current_row, 0)
            if index_item:
                channel_uuid = index_item.data(Qt.UserRole)
                selected_channel = self.codeplug.get_channel(channel_uuid)
                if selected_channel:
                    selected_pos = selected_channel.position

        # Find next free position after selection
        used = self.codeplug.get_used_positions()
        new_pos = selected_pos + 1 if selected_pos > 0 else 1

        while new_pos in used and new_pos <= 1024:
            new_pos += 1

        if new_pos > 1024:
            QMessageBox.warning(self, "Error", "No free channel positions")
            return

        # Default frequencies - calculate TX using auto-shift if enabled
        rx_freq_mhz = self.DEFAULT_RX_FREQ_MHZ
        tx_freq_mhz = OptionsDialog.calculate_tx_freq(rx_freq_mhz)

        # Create new channel with assigned position
        new_channel = Channel(
            position=new_pos,
            name=f"CH-{new_pos}",
            rx_freq=self._mhz_to_freq(rx_freq_mhz),
            tx_freq=self._mhz_to_freq(tx_freq_mhz),
            mode=ChannelMode.ANALOG,
            power=PowerLevel.HIGH,
            scan=ScanMode.ADD,
        )

        self.codeplug.add_channel(new_channel)
        self.refresh_table()

        # Select the newly added channel
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.data(Qt.UserRole) == new_channel.uuid:
                self.table.selectRow(i)
                break

        self.data_modified.emit()

    def delete_channel(self):
        """Delete selected channel"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "No channel selected")
            return

        index_item = self.table.item(current_row, 0)
        channel_uuid = index_item.data(Qt.UserRole)
        channel = self.codeplug.get_channel(channel_uuid)

        if channel:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete channel '{channel.name}'?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.codeplug.channels.remove(channel)
                # DO NOT modify indices - they are recalculated on save
                self.refresh_table()
                self.data_modified.emit()

    def save_to_codeplug(self, codeplug: Codeplug):
        """Save current table state to codeplug (already saved via on_item_changed)"""
        # Data is already saved to self.codeplug via on_item_changed
        pass

    # CSV Helper Methods
    def _get_contact_name_by_uuid(self, uuid: str) -> str:
        """Get contact name by UUID"""
        if not self.codeplug or not uuid:
            return 'None'
        contact = self.codeplug.get_contact(uuid)
        return contact.name if contact else 'None'

    def _get_group_list_name_by_uuid(self, uuid: str) -> str:
        """Get group list name by UUID"""
        if not self.codeplug or not uuid:
            return 'None'
        group_list = self.codeplug.get_group_list(uuid)
        return group_list.name if group_list else 'None'

    def _get_encryption_name_by_uuid(self, uuid: str) -> str:
        """Get encryption key alias by UUID"""
        if not self.codeplug or not uuid:
            return 'None'
        encrypt_key = self.codeplug.get_encryption_key(uuid)
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

    def _find_contact_uuid(self, name: str) -> str:
        """Find contact UUID by name"""
        if not self.codeplug or not name or name == 'None':
            return ""
        for contact in self.codeplug.contacts:
            if contact.name == name:
                return contact.uuid
        return ""

    def _find_group_list_uuid(self, name: str) -> str:
        """Find group list UUID by name"""
        if not self.codeplug or not name or name == 'None':
            return ""
        for group_list in self.codeplug.group_lists:
            if group_list.name == name:
                return group_list.uuid
        return ""

    def _find_encryption_uuid(self, alias: str) -> str:
        """Find encryption key UUID by alias"""
        if not self.codeplug or not alias or alias == 'None':
            return ""
        for encrypt_key in self.codeplug.encryption_keys:
            if encrypt_key.alias == alias:
                return encrypt_key.uuid
        return ""

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
                    # Parse channel number as position
                    position = int(row.get('Channel Number', 0))
                    if position < 1 or position > 1024:
                        print(f"Warning: Invalid channel position {position}, skipping")
                        continue

                    # Check if channel exists at this position (for update) or create new
                    channel = self.codeplug.get_channel_by_position(position)
                    if not channel:
                        # New channel with specified position
                        channel = Channel(position=position)
                        self.codeplug.add_channel(channel)
                    else:
                        # Update existing channel at this position
                        pass

                    # Common fields
                    channel.name = row.get('Channel Name', '')[:16]
                    channel.rx_freq = self._mhz_to_freq(float(row.get('Rx Frequency', 0)))
                    channel.tx_freq = self._mhz_to_freq(float(row.get('Tx Frequency', 0)))

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
                        # Digital-specific fields - use UUID-based lookups
                        tg_list = row.get('TG List', 'None')
                        channel.group_list_uuid = self._find_group_list_uuid(tg_list)

                        contact = row.get('Contact', 'None')
                        channel.contact_uuid = self._find_contact_uuid(contact)

                        dmr_encrypt = row.get('DMR Enrcypt', 'None')  # Note: typo in original format
                        channel.encrypt_uuid = self._find_encryption_uuid(dmr_encrypt)

                        dmr_mode = row.get('DCDM', 'Off')
                        channel.dmr_mode = self._find_dropdown_value(DMR_MODE_VALUES, dmr_mode)

                        timeslot_str = row.get('Timeslot', '1')
                        channel.dmr_time_slot = int(timeslot_str) - 1 if timeslot_str else 0

                        colour_code_str = row.get('Colour Code', '1')
                        channel.dmr_color_code = int(colour_code_str) if colour_code_str else 1

                        dmr_politely_tx = row.get('DMR Politely TX', 'No Restriction')
                        channel.dmr_busy_lock = self._find_dropdown_value(TX_PRIORITY_VALUES, dmr_politely_tx)

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
                        channel.ana_busy_lock = self._find_dropdown_value(TX_PRIORITY_VALUES, busy_lock)

                        ana_tot = row.get('ANA TOT', 'Off')
                        channel.tot_analog = self._parse_tot_value(ana_tot)

                        tail_tone = row.get('Tail Tone', 'Off')
                        channel.tail_tone = self._find_dropdown_value(TAIL_TONE_VALUES, tail_tone)

                        scrambler = row.get('Scrambler', 'Off')
                        channel.scramble = self._find_dropdown_value(SCRAMBLER_VALUES, scrambler)

                        dcs_type = row.get('DCS Type', 'Normal Sub-tone')
                        channel.ctdcs_select = self._find_dropdown_value(CTDCS_SELECT_VALUES, dcs_type)

                        mute_code_str = row.get('ANA Mute Code', '')
                        channel.mute_code = int(mute_code_str, 16) if mute_code_str else 0

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

        # Export channels in list order (this is the order shown in the UI)
        channels = self.codeplug.get_active_channels()

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
                # Common fields - use channel position as channel number
                channel_num = ch.position
                rx_freq = f"{self._freq_to_mhz(ch.rx_freq):.5f}"
                tx_freq = f"{self._freq_to_mhz(ch.tx_freq):.5f}"
                channel_type = 'Digital' if ch.is_digital() else 'Analog'
                power = 'High' if ch.power == PowerLevel.HIGH else 'Low'
                scan_add = 'Add' if ch.scan == ScanMode.ADD else 'Remove'
                channel_name = ch.name

                # Digital-specific fields - use UUID-based lookups
                if ch.is_digital():
                    tg_list = self._get_group_list_name_by_uuid(ch.group_list_uuid) if ch.group_list_uuid else 'None'
                    contact = self._get_contact_name_by_uuid(ch.contact_uuid) if ch.contact_uuid else 'None'
                    dmr_encrypt = self._get_encryption_name_by_uuid(ch.encrypt_uuid) if ch.encrypt_uuid else 'None'
                    dmr_mode = self._get_dropdown_label(DMR_MODE_VALUES, ch.dmr_mode)
                    timeslot = ch.dmr_time_slot + 1
                    colour_code = ch.dmr_color_code
                    dmr_politely_tx = self._get_dropdown_label(TX_PRIORITY_VALUES, ch.dmr_busy_lock)
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
                    mute_code = ''
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
                    busy_lock = self._get_dropdown_label(TX_PRIORITY_VALUES, ch.ana_busy_lock)
                    ana_tot = self._get_tot_label(ch.tot_analog)
                    tail_tone = self._get_dropdown_label(TAIL_TONE_VALUES, ch.tail_tone)
                    scrambler = self._get_dropdown_label(SCRAMBLER_VALUES, ch.scramble)
                    dcs_type = self._get_dropdown_label(CTDCS_SELECT_VALUES, ch.ctdcs_select)
                    mute_code = f"{ch.mute_code:08X}" if ch.mute_code else ''
                    am_fm_rx = self._get_dropdown_label(ANALOG_MODULATION_VALUES, ch.analog_modulation.value)

                writer.writerow([
                    channel_num, rx_freq, tx_freq, channel_type, power, scan_add,
                    channel_name, tg_list, contact, dmr_encrypt, dmr_mode, timeslot, colour_code,
                    dmr_politely_tx, dmr_tot, promiscuos_mode, channel_id, id_select,
                    rx_tone, tx_tone, bandwidth, busy_lock, ana_tot, tail_tone, scrambler,
                    dcs_type, mute_code, 0, 0, am_fm_rx
                ])

    def move_channel_up(self):
        """Move selected channel up (swap positions with previous)"""
        current_row = self.table.currentRow()
        if current_row <= 0 or not self.codeplug:
            return

        # Get channels sorted by position (matches table display)
        channels = self.codeplug.get_channels_sorted_by_position()
        if current_row >= len(channels):
            return

        current_channel = channels[current_row]
        prev_channel = channels[current_row - 1]

        # Swap positions
        current_channel.position, prev_channel.position = prev_channel.position, current_channel.position

        self.refresh_table()
        self.table.selectRow(current_row - 1)
        self.data_modified.emit()

    def move_channel_down(self):
        """Move selected channel down (swap positions with next)"""
        current_row = self.table.currentRow()
        if current_row < 0 or not self.codeplug:
            return

        # Get channels sorted by position (matches table display)
        channels = self.codeplug.get_channels_sorted_by_position()
        if current_row >= len(channels) - 1:
            return

        current_channel = channels[current_row]
        next_channel = channels[current_row + 1]

        # Swap positions
        current_channel.position, next_channel.position = next_channel.position, current_channel.position

        self.refresh_table()
        self.table.selectRow(current_row + 1)
        self.data_modified.emit()

    def sort_by_name(self):
        """Sort channels alphabetically by name - reassigns positions"""
        if not self.codeplug:
            return
        # Sort and reassign consecutive positions starting from 1
        channels = sorted(self.codeplug.get_active_channels(), key=lambda ch: ch.name.lower())
        for i, ch in enumerate(channels):
            ch.position = i + 1
        self.refresh_table()
        self.data_modified.emit()

    def sort_by_rx_freq(self):
        """Sort channels by RX frequency - reassigns positions"""
        if not self.codeplug:
            return
        # Sort and reassign consecutive positions starting from 1
        channels = sorted(self.codeplug.get_active_channels(), key=lambda ch: ch.rx_freq)
        for i, ch in enumerate(channels):
            ch.position = i + 1
        self.refresh_table()
        self.data_modified.emit()

    def sort_by_tx_freq(self):
        """Sort channels by TX frequency - reassigns positions"""
        if not self.codeplug:
            return
        # Sort and reassign consecutive positions starting from 1
        channels = sorted(self.codeplug.get_active_channels(), key=lambda ch: ch.tx_freq)
        for i, ch in enumerate(channels):
            ch.position = i + 1
        self.refresh_table()
        self.data_modified.emit()
