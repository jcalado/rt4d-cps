"""Group List Widget for managing DMR RX Groups"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QSplitter, QLabel, QListWidget, QListWidgetItem,
    QGroupBox
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

        left_layout.addWidget(QLabel("<b>Group Lists</b>"))

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "Name", "Contacts"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        # Resize columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.table.itemSelectionChanged.connect(self.on_selection_changed)
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

        self.available_list = QListWidget()
        self.available_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
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

        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
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
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

    def load_codeplug(self, codeplug: Codeplug):
        """Load group lists from codeplug"""
        self.codeplug = codeplug
        self.refresh_table()
        self.refresh_available_contacts()

    def refresh_table(self):
        """Refresh group lists table"""
        if not self.codeplug:
            return

        self.table.setRowCount(0)
        group_lists = sorted(self.codeplug.get_active_group_lists(), key=lambda g: g.index)
        palette = self.table.palette()
        readonly_bg = palette.alternateBase().color()

        for row, gl in enumerate(group_lists):
            self.table.insertRow(row)

            # Index
            item_index = QTableWidgetItem(str(gl.index + 1))
            item_index.setBackground(readonly_bg)
            self.table.setItem(row, 0, item_index)

            # Name
            self.table.setItem(row, 1, QTableWidgetItem(gl.name))

            # Contact count
            self.table.setItem(row, 2, QTableWidgetItem(str(len(gl.contacts))))

    def refresh_available_contacts(self):
        """Refresh available contacts list"""
        if not self.codeplug:
            return

        self.available_list.clear()
        contacts = sorted(self.codeplug.get_active_contacts(), key=lambda c: c.index)

        for contact in contacts:
            # Only show GROUP contacts
            if contact.contact_type.name == "GROUP":
                item = QListWidgetItem(f"{contact.name} (ID: {contact.dmr_id})")
                item.setData(Qt.UserRole, contact.index)
                self.available_list.addItem(item)

    def on_selection_changed(self):
        """Handle group list selection"""
        current_row = self.table.currentRow()
        if current_row < 0:
            self.current_group_list = None
            self.details_label.setText("<b>Select a group list</b>")
            self.selected_list.clear()
            self.btn_add_contact.setEnabled(False)
            self.btn_remove_contact.setEnabled(False)
            return

        # Get selected group list
        index_item = self.table.item(current_row, 0)
        gl_index = int(index_item.text()) - 1
        self.current_group_list = self.codeplug.get_group_list(gl_index)

        if self.current_group_list:
            self.details_label.setText(f"<b>{self.current_group_list.name}</b>")
            self.refresh_selected_contacts()
            self.btn_add_contact.setEnabled(True)
            self.btn_remove_contact.setEnabled(True)

    def refresh_selected_contacts(self):
        """Refresh selected contacts list"""
        self.selected_list.clear()

        if not self.current_group_list:
            return

        for contact_idx in self.current_group_list.contacts:
            contact = self.codeplug.get_contact(contact_idx)
            if contact:
                item = QListWidgetItem(f"{contact.name} (ID: {contact.dmr_id})")
                item.setData(Qt.UserRole, contact.index)
                self.selected_list.addItem(item)

    def add_contact_to_group(self):
        """Add selected contacts to current group list"""
        if not self.current_group_list:
            return

        selected_items = self.available_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select contacts to add")
            return

        for item in selected_items:
            contact_idx = item.data(Qt.UserRole)
            if contact_idx not in self.current_group_list.contacts:
                if len(self.current_group_list.contacts) < 128:
                    self.current_group_list.add_contact(contact_idx)
                else:
                    QMessageBox.warning(self, "Warning", "Maximum 128 contacts per group list")
                    break

        self.refresh_selected_contacts()
        self.refresh_table()
        self.data_modified.emit()

    def remove_contact_from_group(self):
        """Remove selected contacts from current group list"""
        if not self.current_group_list:
            return

        selected_items = self.selected_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select contacts to remove")
            return

        for item in selected_items:
            contact_idx = item.data(Qt.UserRole)
            self.current_group_list.remove_contact(contact_idx)

        self.refresh_selected_contacts()
        self.refresh_table()
        self.data_modified.emit()

    def add_group_list(self):
        """Add a new group list"""
        if not self.codeplug:
            QMessageBox.warning(self, "Warning", "No codeplug loaded")
            return

        # Find next available index
        existing_indices = [gl.index for gl in self.codeplug.group_lists]
        next_index = max(existing_indices, default=-1) + 1
        while next_index in existing_indices and next_index < 32:
            next_index += 1

        if next_index >= 32:
            QMessageBox.warning(self, "Warning", "Maximum group lists reached (32)")
            return

        # Create new group list
        new_gl = GroupList(
            index=next_index,
            name=f"Group {next_index + 1}"
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
        gl_index = int(index_item.text()) - 1
        group_list = self.codeplug.get_group_list(gl_index)

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
                self.selected_list.clear()
                self.current_group_list = None
                self.data_modified.emit()
