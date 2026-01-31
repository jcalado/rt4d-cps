"""Zone Widget for managing radio zones"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QSplitter, QLabel,
    QGroupBox, QInputDialog, QLineEdit, QSizePolicy
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

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "Name", "Channels"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

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

        self.btn_move_zone_up = QPushButton("Move Up ↑")
        self.btn_move_zone_up.clicked.connect(self.move_zone_up)
        button_layout.addWidget(self.btn_move_zone_up)

        self.btn_move_zone_down = QPushButton("Move Down ↓")
        self.btn_move_zone_down.clicked.connect(self.move_zone_down)
        button_layout.addWidget(self.btn_move_zone_down)

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

        # Filter for available channels
        available_filter_layout = QHBoxLayout()
        available_filter_layout.addWidget(QLabel("Filter:"))
        self.available_filter = QLineEdit()
        self.available_filter.setPlaceholderText("Search by name or position...")
        self.available_filter.textChanged.connect(self.refresh_details)
        available_filter_layout.addWidget(self.available_filter)
        self.btn_clear_available_filter = QPushButton("Clear")
        self.btn_clear_available_filter.clicked.connect(lambda: self.available_filter.clear())
        available_filter_layout.addWidget(self.btn_clear_available_filter)
        available_layout.addLayout(available_filter_layout)

        self.available_list = QTableWidget()
        self.available_list.setColumnCount(3)
        self.available_list.setHorizontalHeaderLabels(["Pos", "Name", "TS"])
        self.available_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.available_list.verticalHeader().setVisible(False)
        self.available_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.available_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Configure column widths
        available_header = self.available_list.horizontalHeader()
        available_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Pos
        available_header.setSectionResizeMode(1, QHeaderView.Stretch)           # Name
        available_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # TS
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

        # Filter for selected channels
        selected_filter_layout = QHBoxLayout()
        selected_filter_layout.addWidget(QLabel("Filter:"))
        self.selected_filter = QLineEdit()
        self.selected_filter.setPlaceholderText("Search by name or position...")
        self.selected_filter.textChanged.connect(self.refresh_details)
        selected_filter_layout.addWidget(self.selected_filter)
        self.btn_clear_selected_filter = QPushButton("Clear")
        self.btn_clear_selected_filter.clicked.connect(lambda: self.selected_filter.clear())
        selected_filter_layout.addWidget(self.btn_clear_selected_filter)
        selected_layout.addLayout(selected_filter_layout)

        self.selected_list = QTableWidget()
        self.selected_list.setColumnCount(3)
        self.selected_list.setHorizontalHeaderLabels(["Pos", "Name", "TS"])
        self.selected_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.selected_list.verticalHeader().setVisible(False)
        self.selected_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.selected_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Configure column widths
        selected_header = self.selected_list.horizontalHeader()
        selected_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Pos
        selected_header.setSectionResizeMode(1, QHeaderView.Stretch)           # Name
        selected_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # TS
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
        left_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        right_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        splitter.setStretchFactor(0, 2)  # List takes 2/3
        splitter.setStretchFactor(1, 1)  # Details takes 1/3

    def load_codeplug(self, codeplug: Optional[Codeplug]):
        """Load codeplug data"""
        self.codeplug = codeplug
        self.current_zone = None
        self.refresh_table()
        self.refresh_details()

    def refresh_table(self):
        """Refresh zones table"""
        # Save current selection by UUID
        selected_zone_uuid = None
        if self.current_zone:
            selected_zone_uuid = self.current_zone.uuid

        # Block signals to prevent selection change during rebuild
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        if not self.codeplug:
            self.table.blockSignals(False)
            return

        # Get active zones (non-empty) in list order
        active_zones = [z for z in self.codeplug.zones if not z.is_empty()]

        row_to_select = None
        for row_num, zone in enumerate(active_zones):
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Display row+1 as index, store UUID in UserRole
            item = QTableWidgetItem(str(row_num + 1))
            item.setData(Qt.UserRole, zone.uuid)
            self.table.setItem(row, 0, item)

            # Name
            item = QTableWidgetItem(zone.name)
            self.table.setItem(row, 1, item)

            # Channel count - only count channels that still exist
            if self.codeplug:
                valid_count = sum(1 for uuid in zone.channels if self.codeplug.get_channel(uuid))
            else:
                valid_count = len(zone.channels)
            item = QTableWidgetItem(str(valid_count))
            self.table.setItem(row, 2, item)

            # Track which row to reselect
            if selected_zone_uuid is not None and zone.uuid == selected_zone_uuid:
                row_to_select = row

        # Restore signals
        self.table.blockSignals(False)

        # Restore selection if we had one
        if row_to_select is not None:
            self.table.selectRow(row_to_select)

    def refresh_details(self):
        """Refresh right panel details"""
        self.available_list.setRowCount(0)
        self.selected_list.setRowCount(0)

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

        # Get filter texts
        available_filter_text = self.available_filter.text().strip().lower()
        selected_filter_text = self.selected_filter.text().strip().lower()

        # Populate available channels (not in zone) - zone.channels now stores UUIDs
        active_channels = self.codeplug.get_active_channels()
        zone_channel_set = set(self.current_zone.channels)  # Set of channel UUIDs

        for channel in active_channels:
            if channel.uuid not in zone_channel_set:
                # Apply filter - match name or position
                if available_filter_text:
                    if available_filter_text not in channel.name.lower() and available_filter_text not in str(channel.position):
                        continue

                row = self.available_list.rowCount()
                self.available_list.insertRow(row)

                # Position column - store UUID in first column's UserRole
                pos_item = QTableWidgetItem(str(channel.position))
                pos_item.setData(Qt.UserRole, channel.uuid)
                self.available_list.setItem(row, 0, pos_item)

                # Name column
                name_item = QTableWidgetItem(channel.name)
                self.available_list.setItem(row, 1, name_item)

                # Timeslot column (only for DMR)
                if channel.is_digital():
                    ts_item = QTableWidgetItem(str(channel.dmr_time_slot + 1))
                else:
                    ts_item = QTableWidgetItem("")
                self.available_list.setItem(row, 2, ts_item)

        # Populate channels in zone (in order) - zone.channels is a list of UUIDs
        for channel_uuid in self.current_zone.channels:
            channel = self.codeplug.get_channel(channel_uuid)
            if channel:
                # Apply filter - match name or position
                if selected_filter_text:
                    if selected_filter_text not in channel.name.lower() and selected_filter_text not in str(channel.position):
                        continue

                row = self.selected_list.rowCount()
                self.selected_list.insertRow(row)

                # Position column - store UUID in first column's UserRole
                pos_item = QTableWidgetItem(str(channel.position))
                pos_item.setData(Qt.UserRole, channel.uuid)
                self.selected_list.setItem(row, 0, pos_item)

                # Name column
                name_item = QTableWidgetItem(channel.name)
                self.selected_list.setItem(row, 1, name_item)

                # Timeslot column (only for DMR)
                if channel.is_digital():
                    ts_item = QTableWidgetItem(str(channel.dmr_time_slot + 1))
                else:
                    ts_item = QTableWidgetItem("")
                self.selected_list.setItem(row, 2, ts_item)

    def on_selection_changed(self):
        """Handle zone selection change"""
        if not self.codeplug:
            return

        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.current_zone = None
            self.refresh_details()
            return

        zone_uuid = self.table.item(selected_rows[0].row(), 0).data(Qt.UserRole)
        self.current_zone = self.codeplug.get_zone(zone_uuid)
        self.refresh_details()

    def on_cell_double_clicked(self, row: int, col: int):
        """Handle double-click to edit zone name"""
        if col != 1:  # Only allow editing name column
            return

        zone_uuid = self.table.item(row, 0).data(Qt.UserRole)
        zone = self.codeplug.get_zone(zone_uuid)
        if not zone:
            return

        dialog = QInputDialog(self)
        dialog.setWindowTitle("Rename Zone")
        dialog.setLabelText("Zone name:")
        dialog.setTextValue(zone.name)
        line_edit = dialog.findChild(QLineEdit)
        if line_edit:
            line_edit.setMaxLength(16)
        if dialog.exec() != QInputDialog.Accepted:
            return
        new_name = dialog.textValue()

        if new_name and new_name != zone.name:
            zone.name = new_name
            self.refresh_table()
            self.refresh_details()
            self.data_modified.emit()

    def add_zone(self):
        """Add a new zone"""
        if not self.codeplug:
            return

        # Check max zones
        active_zones = [z for z in self.codeplug.zones if not z.is_empty()]
        if len(active_zones) >= 256:
            QMessageBox.warning(self, "Error", "Maximum number of zones (256) reached!")
            return

        # Prompt for name
        zone_num = len(active_zones) + 1
        dialog = QInputDialog(self)
        dialog.setWindowTitle("New Zone")
        dialog.setLabelText("Zone name:")
        dialog.setTextValue(f"Zone {zone_num}")
        line_edit = dialog.findChild(QLineEdit)
        if line_edit:
            line_edit.setMaxLength(16)
        if dialog.exec() != QInputDialog.Accepted:
            return
        name = dialog.textValue()

        if not name:
            return

        # Create zone (UUID is auto-generated, index is not set - calculated on save)
        zone = Zone(
            name=name,
            channels=[]
        )

        self.codeplug.add_zone(zone)
        self.refresh_table()
        self.data_modified.emit()

        # Select new zone by UUID
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.UserRole) == zone.uuid:
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

    def move_zone_up(self):
        """Move selected zone up in display order"""
        if not self.codeplug or not self.current_zone:
            return

        current_row = self.table.currentRow()
        if current_row <= 0:
            return

        # Get active zones in list order
        active_zones = [z for z in self.codeplug.zones if not z.is_empty()]

        # Find the index in the original zones list and swap positions
        zone_to_move = active_zones[current_row]
        zone_above = active_zones[current_row - 1]

        zones_list = list(self.codeplug.zones)
        idx_move = zones_list.index(zone_to_move)
        idx_above = zones_list.index(zone_above)

        # Swap in the original list
        zones_list[idx_move], zones_list[idx_above] = zones_list[idx_above], zones_list[idx_move]
        self.codeplug.zones = zones_list

        # Refresh and maintain selection
        self.refresh_table()
        self.table.selectRow(current_row - 1)
        self.data_modified.emit()

    def move_zone_down(self):
        """Move selected zone down in display order"""
        if not self.codeplug or not self.current_zone:
            return

        current_row = self.table.currentRow()
        active_zones = [z for z in self.codeplug.zones if not z.is_empty()]

        if current_row < 0 or current_row >= len(active_zones) - 1:
            return

        # Find the index in the original zones list and swap positions
        zone_to_move = active_zones[current_row]
        zone_below = active_zones[current_row + 1]

        zones_list = list(self.codeplug.zones)
        idx_move = zones_list.index(zone_to_move)
        idx_below = zones_list.index(zone_below)

        # Swap in the original list
        zones_list[idx_move], zones_list[idx_below] = zones_list[idx_below], zones_list[idx_move]
        self.codeplug.zones = zones_list

        # Refresh and maintain selection
        self.refresh_table()
        self.table.selectRow(current_row + 1)
        self.data_modified.emit()

    def add_channels_to_zone(self):
        """Add selected channels to zone"""
        if not self.current_zone:
            return

        selected_rows = self.available_list.selectionModel().selectedRows()
        if not selected_rows:
            return

        # Check if we'll exceed 200 channels
        current_count = len(self.current_zone.channels)
        new_count = current_count + len(selected_rows)
        if new_count > 200:
            QMessageBox.warning(
                self,
                "Too Many Channels",
                f"Cannot add {len(selected_rows)} channels.\n"
                f"Zone has {current_count} channels, maximum is 200."
            )
            return

        # Find the row of the last selected item to select the next one
        last_selected_row = max(row.row() for row in selected_rows)

        # Add channels by UUID (get from column 0)
        for row in selected_rows:
            pos_item = self.available_list.item(row.row(), 0)
            if pos_item:
                channel_uuid = pos_item.data(Qt.UserRole)
                self.current_zone.add_channel(channel_uuid)

        self.refresh_details()
        self.refresh_table()
        self.data_modified.emit()

        # Select the next available channel (if any)
        next_row = last_selected_row
        if next_row < self.available_list.rowCount():
            self.available_list.selectRow(next_row)
        elif self.available_list.rowCount() > 0:
            # If we were at the end, select the last remaining item
            self.available_list.selectRow(self.available_list.rowCount() - 1)

    def remove_channels_from_zone(self):
        """Remove selected channels from zone"""
        if not self.current_zone:
            return

        selected_rows = self.selected_list.selectionModel().selectedRows()
        if not selected_rows:
            return

        # Find the row of the last selected item
        last_selected_row = max(row.row() for row in selected_rows)

        # Remove channels by UUID (get from column 0)
        for row in selected_rows:
            pos_item = self.selected_list.item(row.row(), 0)
            if pos_item:
                channel_uuid = pos_item.data(Qt.UserRole)
                self.current_zone.remove_channel(channel_uuid)

        self.refresh_details()
        self.refresh_table()
        self.data_modified.emit()

        # Select the next channel in the zone list, or previous if we removed the last one
        if self.selected_list.rowCount() > 0:
            if last_selected_row < self.selected_list.rowCount():
                # Select the item now at the same position
                self.selected_list.selectRow(last_selected_row)
            else:
                # We removed the last item(s), select the new last item
                self.selected_list.selectRow(self.selected_list.rowCount() - 1)

    def move_channel_up(self):
        """Move selected channel up in order"""
        if not self.current_zone:
            return

        current_row = self.selected_list.currentRow()
        if current_row < 0:
            return

        # Get UUID of selected channel from UI
        pos_item = self.selected_list.item(current_row, 0)
        if not pos_item:
            return
        channel_uuid = pos_item.data(Qt.UserRole)

        # Find actual index in zone.channels
        try:
            actual_index = self.current_zone.channels.index(channel_uuid)
        except ValueError:
            return

        if actual_index <= 0:
            return  # Already at top

        # Swap in the actual list
        channels = self.current_zone.channels
        channels[actual_index], channels[actual_index - 1] = \
            channels[actual_index - 1], channels[actual_index]

        self.refresh_details()

        # Re-select the moved channel by finding its new row
        for row in range(self.selected_list.rowCount()):
            item = self.selected_list.item(row, 0)
            if item and item.data(Qt.UserRole) == channel_uuid:
                self.selected_list.selectRow(row)
                break

        self.data_modified.emit()

    def move_channel_down(self):
        """Move selected channel down in order"""
        if not self.current_zone:
            return

        current_row = self.selected_list.currentRow()
        if current_row < 0:
            return

        # Get UUID of selected channel from UI
        pos_item = self.selected_list.item(current_row, 0)
        if not pos_item:
            return
        channel_uuid = pos_item.data(Qt.UserRole)

        # Find actual index in zone.channels
        try:
            actual_index = self.current_zone.channels.index(channel_uuid)
        except ValueError:
            return

        if actual_index >= len(self.current_zone.channels) - 1:
            return  # Already at bottom

        # Swap in the actual list
        channels = self.current_zone.channels
        channels[actual_index], channels[actual_index + 1] = \
            channels[actual_index + 1], channels[actual_index]

        self.refresh_details()

        # Re-select the moved channel by finding its new row
        for row in range(self.selected_list.rowCount()):
            item = self.selected_list.item(row, 0)
            if item and item.data(Qt.UserRole) == channel_uuid:
                self.selected_list.selectRow(row)
                break

        self.data_modified.emit()
