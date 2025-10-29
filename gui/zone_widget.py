"""Zone Widget for managing radio zones"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QSplitter, QLabel, QListWidget, QListWidgetItem,
    QGroupBox, QInputDialog, QLineEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from rt4d_codeplug import Codeplug, Zone


class ZoneWidget(QWidget):
    """Widget for displaying and editing zones"""

    data_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.codeplug: Optional[Codeplug] = None
        self.current_zone: Optional[Zone] = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left side: Zones table
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        left_layout.addWidget(QLabel("<b>Zones</b>"))

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "Name", "Channels"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Resize columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        left_layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Zone")
        self.btn_add.clicked.connect(self.add_zone)
        button_layout.addWidget(self.btn_add)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self.delete_zone)
        button_layout.addWidget(self.btn_delete)

        button_layout.addStretch()
        left_layout.addLayout(button_layout)

        # Right side: Channel management
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        self.details_label = QLabel("<b>Select a zone</b>")
        self.details_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.details_label)

        # Available channels group
        available_group = QGroupBox("Available Channels")
        available_layout = QVBoxLayout()

        self.available_list = QListWidget()
        self.available_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        available_layout.addWidget(self.available_list)

        self.btn_add_channel = QPushButton("Add to Zone →")
        self.btn_add_channel.clicked.connect(self.add_channels_to_zone)
        self.btn_add_channel.setEnabled(False)
        available_layout.addWidget(self.btn_add_channel)

        available_group.setLayout(available_layout)
        right_layout.addWidget(available_group)

        # Selected channels group
        selected_group = QGroupBox("Channels in Zone")
        selected_layout = QVBoxLayout()

        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        selected_layout.addWidget(self.selected_list)

        btn_layout = QHBoxLayout()
        self.btn_remove_channel = QPushButton("← Remove from Zone")
        self.btn_remove_channel.clicked.connect(self.remove_channels_from_zone)
        self.btn_remove_channel.setEnabled(False)
        btn_layout.addWidget(self.btn_remove_channel)

        self.btn_move_up = QPushButton("Move Up ↑")
        self.btn_move_up.clicked.connect(self.move_channel_up)
        self.btn_move_up.setEnabled(False)
        btn_layout.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton("Move Down ↓")
        self.btn_move_down.clicked.connect(self.move_channel_down)
        self.btn_move_down.setEnabled(False)
        btn_layout.addWidget(self.btn_move_down)

        selected_layout.addLayout(btn_layout)

        selected_group.setLayout(selected_layout)
        right_layout.addWidget(selected_group)

        # Set splitter sizes
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])

    def load_codeplug(self, codeplug: Optional[Codeplug]):
        """Load codeplug data"""
        self.codeplug = codeplug
        self.current_zone = None
        self.refresh_table()
        self.refresh_details()

    def refresh_table(self):
        """Refresh zones table"""
        self.table.setRowCount(0)

        if not self.codeplug:
            return

        # Sort zones by index
        zones = sorted(self.codeplug.zones, key=lambda z: z.index)

        for zone in zones:
            if zone.is_empty():
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            # Index
            item = QTableWidgetItem(str(zone.index + 1))
            item.setData(Qt.UserRole, zone.index)
            self.table.setItem(row, 0, item)

            # Name
            item = QTableWidgetItem(zone.name)
            self.table.setItem(row, 1, item)

            # Channel count
            item = QTableWidgetItem(str(len(zone.channels)))
            self.table.setItem(row, 2, item)

    def refresh_details(self):
        """Refresh right panel details"""
        self.available_list.clear()
        self.selected_list.clear()

        if not self.current_zone or not self.codeplug:
            self.details_label.setText("<b>Select a zone</b>")
            self.btn_add_channel.setEnabled(False)
            self.btn_remove_channel.setEnabled(False)
            self.btn_move_up.setEnabled(False)
            self.btn_move_down.setEnabled(False)
            return

        self.details_label.setText(f"<b>Editing: {self.current_zone.name}</b>")
        self.btn_add_channel.setEnabled(True)
        self.btn_remove_channel.setEnabled(True)
        self.btn_move_up.setEnabled(True)
        self.btn_move_down.setEnabled(True)

        # Populate available channels (not in zone)
        active_channels = self.codeplug.get_active_channels()
        zone_channel_set = set(self.current_zone.channels)

        for channel in sorted(active_channels, key=lambda c: c.index):
            if channel.index not in zone_channel_set:
                item = QListWidgetItem(f"CH{channel.index + 1:03d}: {channel.name}")
                item.setData(Qt.UserRole, channel.index)
                self.available_list.addItem(item)

        # Populate channels in zone (in order)
        for channel_idx in self.current_zone.channels:
            channel = self.codeplug.get_channel(channel_idx)
            if channel:
                item = QListWidgetItem(f"CH{channel.index + 1:03d}: {channel.name}")
                item.setData(Qt.UserRole, channel.index)
                self.selected_list.addItem(item)

    def on_selection_changed(self):
        """Handle zone selection change"""
        if not self.codeplug:
            return

        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.current_zone = None
            self.refresh_details()
            return

        zone_index = self.table.item(selected_rows[0].row(), 0).data(Qt.UserRole)
        self.current_zone = self.codeplug.get_zone(zone_index)
        self.refresh_details()

    def on_cell_double_clicked(self, row: int, col: int):
        """Handle double-click to edit zone name"""
        if col != 1:  # Only allow editing name column
            return

        zone_index = self.table.item(row, 0).data(Qt.UserRole)
        zone = self.codeplug.get_zone(zone_index)
        if not zone:
            return

        new_name, ok = QInputDialog.getText(
            self,
            "Rename Zone",
            "Zone name:",
            QLineEdit.Normal,
            zone.name
        )

        if ok and new_name and new_name != zone.name:
            zone.name = new_name[:16]  # Max 16 chars
            self.refresh_table()
            self.refresh_details()
            self.data_modified.emit()

    def add_zone(self):
        """Add a new zone"""
        if not self.codeplug:
            return

        # Find first available zone index
        used_indices = {z.index for z in self.codeplug.zones}
        zone_index = None
        for i in range(256):
            if i not in used_indices:
                zone_index = i
                break

        if zone_index is None:
            QMessageBox.warning(self, "Error", "Maximum number of zones (256) reached!")
            return

        # Prompt for name
        name, ok = QInputDialog.getText(
            self,
            "New Zone",
            "Zone name:",
            QLineEdit.Normal,
            f"Zone {zone_index + 1}"
        )

        if not ok or not name:
            return

        # Create zone
        zone = Zone(
            index=zone_index,
            name=name[:16],
            channels=[]
        )

        self.codeplug.add_zone(zone)
        self.refresh_table()
        self.data_modified.emit()

        # Select new zone
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.UserRole) == zone_index:
                self.table.selectRow(row)
                break

    def delete_zone(self):
        """Delete selected zone"""
        if not self.current_zone:
            return

        reply = QMessageBox.question(
            self,
            "Delete Zone",
            f"Delete zone '{self.current_zone.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.codeplug.zones.remove(self.current_zone)
            self.current_zone = None
            self.refresh_table()
            self.refresh_details()
            self.data_modified.emit()

    def add_channels_to_zone(self):
        """Add selected channels to zone"""
        if not self.current_zone:
            return

        selected_items = self.available_list.selectedItems()
        if not selected_items:
            return

        # Check if we'll exceed 250 channels
        current_count = len(self.current_zone.channels)
        new_count = current_count + len(selected_items)
        if new_count > 250:
            QMessageBox.warning(
                self,
                "Too Many Channels",
                f"Cannot add {len(selected_items)} channels.\n"
                f"Zone has {current_count} channels, maximum is 250."
            )
            return

        # Add channels
        for item in selected_items:
            channel_idx = item.data(Qt.UserRole)
            self.current_zone.add_channel(channel_idx)

        self.refresh_details()
        self.refresh_table()
        self.data_modified.emit()

    def remove_channels_from_zone(self):
        """Remove selected channels from zone"""
        if not self.current_zone:
            return

        selected_items = self.selected_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            channel_idx = item.data(Qt.UserRole)
            self.current_zone.remove_channel(channel_idx)

        self.refresh_details()
        self.refresh_table()
        self.data_modified.emit()

    def move_channel_up(self):
        """Move selected channel up in order"""
        if not self.current_zone:
            return

        current_row = self.selected_list.currentRow()
        if current_row <= 0:
            return

        # Swap channels
        channels = self.current_zone.channels
        channels[current_row], channels[current_row - 1] = \
            channels[current_row - 1], channels[current_row]

        self.refresh_details()
        self.selected_list.setCurrentRow(current_row - 1)
        self.data_modified.emit()

    def move_channel_down(self):
        """Move selected channel down in order"""
        if not self.current_zone:
            return

        current_row = self.selected_list.currentRow()
        if current_row < 0 or current_row >= len(self.current_zone.channels) - 1:
            return

        # Swap channels
        channels = self.current_zone.channels
        channels[current_row], channels[current_row + 1] = \
            channels[current_row + 1], channels[current_row]

        self.refresh_details()
        self.selected_list.setCurrentRow(current_row + 1)
        self.data_modified.emit()
