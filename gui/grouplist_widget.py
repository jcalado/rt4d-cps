"""Group List Widget for managing DMR RX Groups"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QSplitter, QLabel, QLineEdit,
    QGroupBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from rt4d_codeplug import Codeplug, GroupList


class GroupListWidget(QWidget):
    """Widget for displaying and editing group lists"""

    data_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.codeplug: Optional[Codeplug] = None
        self.current_group_list: Optional[GroupList] = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left side: Group lists table
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "Name", "Contacts"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.verticalHeader().setVisible(False)

        # Resize columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.itemChanged.connect(self.on_item_changed)
        left_layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Group List")
        self.btn_add.clicked.connect(self.add_group_list)
        button_layout.addWidget(self.btn_add)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self.delete_group_list)
        button_layout.addWidget(self.btn_delete)

        button_layout.addStretch()
        left_layout.addLayout(button_layout)

        # Right side: Contact management
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        self.details_label = QLabel("<b>Select a group list</b>")
        self.details_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.details_label)

        # Available contacts group
        available_group = QGroupBox("Available Contacts")
        available_layout = QVBoxLayout()

        # Filter for available contacts
        available_filter_layout = QHBoxLayout()
        available_filter_layout.addWidget(QLabel("Filter:"))
        self.available_filter = QLineEdit()
        self.available_filter.setPlaceholderText("Search by name or DMR ID...")
        self.available_filter.textChanged.connect(self.refresh_available_contacts)
        available_filter_layout.addWidget(self.available_filter)
        self.btn_clear_available_filter = QPushButton("Clear")
        self.btn_clear_available_filter.clicked.connect(lambda: self.available_filter.clear())
        available_filter_layout.addWidget(self.btn_clear_available_filter)
        available_layout.addLayout(available_filter_layout)

        self.available_list = QTableWidget()
        self.available_list.setColumnCount(2)
        self.available_list.setHorizontalHeaderLabels(["Name", "DMR ID"])
        self.available_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.available_list.verticalHeader().setVisible(False)
        self.available_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.available_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Configure column widths
        available_header = self.available_list.horizontalHeader()
        available_header.setSectionResizeMode(0, QHeaderView.Stretch)       # Name
        available_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # DMR ID
        available_layout.addWidget(self.available_list)

        self.btn_add_contact = QPushButton("Add to Group →")
        self.btn_add_contact.clicked.connect(self.add_contact_to_group)
        self.btn_add_contact.setEnabled(False)
        available_layout.addWidget(self.btn_add_contact)

        available_group.setLayout(available_layout)
        right_layout.addWidget(available_group)

        # Selected contacts group
        selected_group = QGroupBox("Contacts in Group")
        selected_layout = QVBoxLayout()

        # Filter for selected contacts
        selected_filter_layout = QHBoxLayout()
        selected_filter_layout.addWidget(QLabel("Filter:"))
        self.selected_filter = QLineEdit()
        self.selected_filter.setPlaceholderText("Search by name or DMR ID...")
        self.selected_filter.textChanged.connect(self.refresh_selected_contacts)
        selected_filter_layout.addWidget(self.selected_filter)
        self.btn_clear_selected_filter = QPushButton("Clear")
        self.btn_clear_selected_filter.clicked.connect(lambda: self.selected_filter.clear())
        selected_filter_layout.addWidget(self.btn_clear_selected_filter)
        selected_layout.addLayout(selected_filter_layout)

        self.selected_list = QTableWidget()
        self.selected_list.setColumnCount(2)
        self.selected_list.setHorizontalHeaderLabels(["Name", "DMR ID"])
        self.selected_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.selected_list.verticalHeader().setVisible(False)
        self.selected_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.selected_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Configure column widths
        selected_header = self.selected_list.horizontalHeader()
        selected_header.setSectionResizeMode(0, QHeaderView.Stretch)       # Name
        selected_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # DMR ID
        selected_layout.addWidget(self.selected_list)

        self.btn_remove_contact = QPushButton("← Remove from Group")
        self.btn_remove_contact.clicked.connect(self.remove_contact_from_group)
        self.btn_remove_contact.setEnabled(False)
        selected_layout.addWidget(self.btn_remove_contact)

        selected_group.setLayout(selected_layout)
        right_layout.addWidget(selected_group)

        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        left_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        right_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        splitter.setStretchFactor(0, 2)  # List takes 2/3
        splitter.setStretchFactor(1, 1)  # Details takes 1/3

    def load_codeplug(self, codeplug: Codeplug):
        """Load group lists from codeplug"""
        self.codeplug = codeplug
        self.refresh_table()
        self.refresh_available_contacts()

    def refresh_table(self):
        """Refresh group lists table"""
        if not self.codeplug:
            return

        # Block signals while refreshing to avoid triggering itemChanged
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        group_lists = self.codeplug.get_active_group_lists()
        palette = self.table.palette()
        readonly_bg = palette.alternateBase().color()

        for row, gl in enumerate(group_lists):
            self.table.insertRow(row)

            # Index (read-only) - display row+1, store UUID in UserRole
            item_index = QTableWidgetItem(str(row + 1))
            item_index.setBackground(readonly_bg)
            item_index.setFlags(item_index.flags() & ~Qt.ItemIsEditable)
            item_index.setData(Qt.UserRole, gl.uuid)
            self.table.setItem(row, 0, item_index)

            # Name (editable)
            item_name = QTableWidgetItem(gl.name)
            self.table.setItem(row, 1, item_name)

            # Contact count (read-only)
            item_count = QTableWidgetItem(str(len(gl.contacts)))
            item_count.setFlags(item_count.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, item_count)

        self.table.blockSignals(False)

    def refresh_available_contacts(self):
        """Refresh available contacts list"""
        if not self.codeplug:
            return

        self.available_list.setRowCount(0)
        contacts = self.codeplug.get_active_contacts()

        # Get UUIDs of contacts already in the current group
        contacts_in_group = set()
        if self.current_group_list:
            contacts_in_group = set(self.current_group_list.contacts)  # Now stores UUIDs

        # Get filter text
        filter_text = self.available_filter.text().strip().lower()

        for contact in contacts:
            # Only show GROUP contacts that aren't already in the selected group
            if contact.contact_type.name == "GROUP" and contact.uuid not in contacts_in_group:
                # Apply filter - match name or DMR ID
                if filter_text:
                    if filter_text not in contact.name.lower() and filter_text not in str(contact.dmr_id):
                        continue

                row = self.available_list.rowCount()
                self.available_list.insertRow(row)

                # Name column - store UUID in first column's UserRole
                name_item = QTableWidgetItem(contact.name)
                name_item.setData(Qt.UserRole, contact.uuid)
                self.available_list.setItem(row, 0, name_item)

                # DMR ID column
                dmr_id_item = QTableWidgetItem(str(contact.dmr_id))
                self.available_list.setItem(row, 1, dmr_id_item)

    def on_selection_changed(self):
        """Handle group list selection"""
        current_row = self.table.currentRow()
        if current_row < 0:
            self.current_group_list = None
            self.details_label.setText("<b>Select a group list</b>")
            self.selected_list.setRowCount(0)
            self.btn_add_contact.setEnabled(False)
            self.btn_remove_contact.setEnabled(False)
            return

        # Get selected group list by UUID
        index_item = self.table.item(current_row, 0)
        gl_uuid = index_item.data(Qt.UserRole)
        self.current_group_list = self.codeplug.get_group_list(gl_uuid)

        if self.current_group_list:
            self.details_label.setText(f"<b>{self.current_group_list.name}</b>")
            self.refresh_selected_contacts()
            self.refresh_available_contacts()
            self.btn_add_contact.setEnabled(True)
            self.btn_remove_contact.setEnabled(True)

    def on_item_changed(self, item: QTableWidgetItem):
        """Handle table item changes (name editing)"""
        if not self.codeplug or item.column() != 1:  # Only handle Name column
            return

        # Get the group list by UUID
        row = item.row()
        index_item = self.table.item(row, 0)
        if not index_item:
            return

        gl_uuid = index_item.data(Qt.UserRole)
        group_list = self.codeplug.get_group_list(gl_uuid)

        if group_list:
            new_name = item.text().strip()
            if new_name and new_name != group_list.name:
                group_list.name = new_name
                # Update details label if this is the currently selected group list
                if self.current_group_list and self.current_group_list.uuid == gl_uuid:
                    self.details_label.setText(f"<b>{group_list.name}</b>")
                self.data_modified.emit()

    def refresh_selected_contacts(self):
        """Refresh selected contacts list"""
        self.selected_list.setRowCount(0)

        if not self.current_group_list:
            return

        # Get filter text
        filter_text = self.selected_filter.text().strip().lower()

        # contacts is now a list of UUIDs
        for contact_uuid in self.current_group_list.contacts:
            contact = self.codeplug.get_contact(contact_uuid)
            if contact:
                # Apply filter - match name or DMR ID
                if filter_text:
                    if filter_text not in contact.name.lower() and filter_text not in str(contact.dmr_id):
                        continue

                row = self.selected_list.rowCount()
                self.selected_list.insertRow(row)

                # Name column - store UUID in first column's UserRole
                name_item = QTableWidgetItem(contact.name)
                name_item.setData(Qt.UserRole, contact.uuid)
                self.selected_list.setItem(row, 0, name_item)

                # DMR ID column
                dmr_id_item = QTableWidgetItem(str(contact.dmr_id))
                self.selected_list.setItem(row, 1, dmr_id_item)

    def add_contact_to_group(self):
        """Add selected contacts to current group list"""
        if not self.current_group_list:
            return

        selected_rows = self.available_list.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "Please select contacts to add")
            return

        for row in selected_rows:
            name_item = self.available_list.item(row.row(), 0)
            if name_item:
                contact_uuid = name_item.data(Qt.UserRole)
                if contact_uuid not in self.current_group_list.contacts:
                    if len(self.current_group_list.contacts) < 128:
                        self.current_group_list.add_contact(contact_uuid)
                    else:
                        QMessageBox.warning(self, "Warning", "Maximum 128 contacts per group list")
                        break

        self.refresh_selected_contacts()
        self.refresh_available_contacts()
        self.refresh_table()
        self.data_modified.emit()

    def remove_contact_from_group(self):
        """Remove selected contacts from current group list"""
        if not self.current_group_list:
            return

        selected_rows = self.selected_list.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "Please select contacts to remove")
            return

        for row in selected_rows:
            name_item = self.selected_list.item(row.row(), 0)
            if name_item:
                contact_uuid = name_item.data(Qt.UserRole)
                self.current_group_list.remove_contact(contact_uuid)

        self.refresh_selected_contacts()
        self.refresh_available_contacts()
        self.refresh_table()
        self.data_modified.emit()

    def add_group_list(self):
        """Add a new group list"""
        if not self.codeplug:
            QMessageBox.warning(self, "Warning", "No codeplug loaded")
            return

        # Check max group lists
        active_group_lists = self.codeplug.get_active_group_lists()
        if len(active_group_lists) >= 32:
            QMessageBox.warning(self, "Warning", "Maximum group lists reached (32)")
            return

        # Create new group list (UUID is auto-generated, index calculated on save)
        group_num = len(active_group_lists) + 1
        new_gl = GroupList(
            name=f"Group {group_num}"
        )

        self.codeplug.add_group_list(new_gl)
        self.refresh_table()
        self.data_modified.emit()

    def delete_group_list(self):
        """Delete selected group list"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "No group list selected")
            return

        index_item = self.table.item(current_row, 0)
        gl_uuid = index_item.data(Qt.UserRole)
        group_list = self.codeplug.get_group_list(gl_uuid)

        if group_list:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete group list '{group_list.name}'?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.codeplug.group_lists.remove(group_list)
                self.refresh_table()
                self.selected_list.setRowCount(0)
                self.current_group_list = None
                self.data_modified.emit()
