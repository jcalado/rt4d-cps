"""Contact Widget for managing DMR contacts"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QSplitter, QLabel, QLineEdit, QSpinBox, QComboBox,
    QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from rt4d_codeplug import Codeplug, Contact, ContactType


class ContactWidget(QWidget):
    """Widget for displaying and editing DMR contacts"""

    data_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.codeplug: Optional[Codeplug] = None
        self.current_contact: Optional[Contact] = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        layout = QHBoxLayout()
        self.setLayout(layout)

        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left side: Contacts table
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        left_layout.addWidget(QLabel("<b>DMR Contacts</b>"))

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["#", "Name", "Type", "DMR ID"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        # Resize columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Contact")
        self.btn_add.clicked.connect(self.add_contact)
        button_layout.addWidget(self.btn_add)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self.delete_contact)
        button_layout.addWidget(self.btn_delete)

        button_layout.addStretch()
        left_layout.addLayout(button_layout)

        # Right side: Contact details
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        self.details_label = QLabel("<b>Select a contact</b>")
        self.details_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.details_label)

        # Details group
        details_group = QGroupBox("Contact Details")
        details_layout = QFormLayout()

        self.edit_name = QLineEdit()
        self.edit_name.setMaxLength(16)
        self.edit_name.textChanged.connect(self.on_detail_changed)
        self.edit_name.setEnabled(False)
        details_layout.addRow("Name:", self.edit_name)

        self.combo_type = QComboBox()
        self.combo_type.addItem("Private Call", ContactType.PRIVATE.value)
        self.combo_type.addItem("Group Call", ContactType.GROUP.value)
        self.combo_type.addItem("All Call", ContactType.ALL_CALL.value)
        self.combo_type.currentIndexChanged.connect(self.on_detail_changed)
        self.combo_type.setEnabled(False)
        details_layout.addRow("Type:", self.combo_type)

        self.spin_dmr_id = QSpinBox()
        self.spin_dmr_id.setRange(1, 16777215)
        self.spin_dmr_id.valueChanged.connect(self.on_detail_changed)
        self.spin_dmr_id.setEnabled(False)
        details_layout.addRow("DMR ID:", self.spin_dmr_id)

        details_group.setLayout(details_layout)
        right_layout.addWidget(details_group)

        right_layout.addStretch()

        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

    def load_codeplug(self, codeplug: Codeplug):
        """Load contacts from codeplug"""
        self.codeplug = codeplug
        self.refresh_table()

    def refresh_table(self):
        """Refresh contacts table"""
        if not self.codeplug:
            return

        self.table.setRowCount(0)
        contacts = sorted(self.codeplug.get_active_contacts(), key=lambda c: c.index)
        palette = self.table.palette()
        readonly_bg = palette.alternateBase().color()

        for row, contact in enumerate(contacts):
            self.table.insertRow(row)

            # Check if this is the protected first contact
            is_protected = (contact.index == 1)

            # Index
            item_index = QTableWidgetItem(str(contact.index))
            item_index.setBackground(readonly_bg)
            self.table.setItem(row, 0, item_index)

            # Name
            item_name = QTableWidgetItem(contact.name)
            if is_protected:
                item_name.setBackground(readonly_bg)
            self.table.setItem(row, 1, item_name)

            # Type
            type_name = contact.contact_type.name.replace("_", " ").title()
            item_type = QTableWidgetItem(type_name)
            if is_protected:
                item_type.setBackground(readonly_bg)
            self.table.setItem(row, 2, item_type)

            # DMR ID
            item_id = QTableWidgetItem(str(contact.dmr_id))
            if is_protected:
                item_id.setBackground(readonly_bg)
            self.table.setItem(row, 3, item_id)

    def on_selection_changed(self):
        """Handle contact selection"""
        current_row = self.table.currentRow()
        if current_row < 0:
            self.current_contact = None
            self.details_label.setText("<b>Select a contact</b>")
            self.edit_name.setEnabled(False)
            self.combo_type.setEnabled(False)
            self.spin_dmr_id.setEnabled(False)
            return

        # Get selected contact
        index_item = self.table.item(current_row, 0)
        contact_index = int(index_item.text())
        self.current_contact = self.codeplug.get_contact(contact_index)

        if self.current_contact:
            self.details_label.setText(f"<b>{self.current_contact.name}</b>")
            self.load_contact_details()
            # Protect the first contact (All call) from editing
            is_protected = (contact_index == 1)
            self.edit_name.setEnabled(not is_protected)
            self.combo_type.setEnabled(not is_protected)
            self.spin_dmr_id.setEnabled(not is_protected)
            if is_protected:
                self.details_label.setText(f"<b>{self.current_contact.name}</b> (Protected)")

    def load_contact_details(self):
        """Load contact details into form"""
        if not self.current_contact:
            return

        # Block signals while loading
        self.edit_name.blockSignals(True)
        self.combo_type.blockSignals(True)
        self.spin_dmr_id.blockSignals(True)

        # Load values
        self.edit_name.setText(self.current_contact.name)

        # Set contact type
        for i in range(self.combo_type.count()):
            if self.combo_type.itemData(i) == self.current_contact.contact_type.value:
                self.combo_type.setCurrentIndex(i)
                break

        self.spin_dmr_id.setValue(self.current_contact.dmr_id)

        # Unblock signals
        self.edit_name.blockSignals(False)
        self.combo_type.blockSignals(False)
        self.spin_dmr_id.blockSignals(False)

    def on_detail_changed(self):
        """Handle detail changes"""
        if not self.current_contact:
            return

        # Save changes
        self.current_contact.name = self.edit_name.text()

        # Update contact type
        type_value = self.combo_type.currentData()
        if type_value == ContactType.PRIVATE.value:
            self.current_contact.contact_type = ContactType.PRIVATE
        elif type_value == ContactType.GROUP.value:
            self.current_contact.contact_type = ContactType.GROUP
        elif type_value == ContactType.ALL_CALL.value:
            self.current_contact.contact_type = ContactType.ALL_CALL

        self.current_contact.dmr_id = self.spin_dmr_id.value()

        # Update table
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.item(current_row, 1).setText(self.current_contact.name)
            type_name = self.current_contact.contact_type.name.replace("_", " ").title()
            self.table.item(current_row, 2).setText(type_name)
            self.table.item(current_row, 3).setText(str(self.current_contact.dmr_id))

        self.details_label.setText(f"<b>{self.current_contact.name}</b>")
        self.data_modified.emit()

    def add_contact(self):
        """Add a new contact"""
        if not self.codeplug:
            QMessageBox.warning(self, "Warning", "No codeplug loaded")
            return

        # Find next available index
        from rt4d_codeplug.constants import MAX_CONTACTS
        existing_indices = [c.index for c in self.codeplug.contacts]
        next_index = max(existing_indices, default=-1) + 1
        while next_index in existing_indices and next_index < MAX_CONTACTS:
            next_index += 1

        if next_index >= MAX_CONTACTS:
            QMessageBox.warning(self, "Warning", f"Maximum contacts reached ({MAX_CONTACTS})")
            return

        # Create new contact
        new_contact = Contact(
            index=next_index,
            name=f"Contact {next_index}",
            contact_type=ContactType.GROUP,
            dmr_id=1
        )

        self.codeplug.add_contact(new_contact)
        self.refresh_table()
        self.data_modified.emit()

    def delete_contact(self):
        """Delete selected contact"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "No contact selected")
            return

        index_item = self.table.item(current_row, 0)
        contact_index = int(index_item.text())

        # Protect the first contact (All call) from deletion
        if contact_index == 1:
            QMessageBox.warning(
                self,
                "Cannot Delete",
                "The first contact (All call) cannot be deleted."
            )
            return

        contact = self.codeplug.get_contact(contact_index)

        if contact:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete contact '{contact.name}'?\n\n"
                f"Warning: This may break references in channels and group lists!",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.codeplug.contacts.remove(contact)
                self.refresh_table()
                self.current_contact = None
                self.edit_name.clear()
                self.spin_dmr_id.setValue(1)
                self.data_modified.emit()

    def save_to_codeplug(self, codeplug: Codeplug):
        """Save contacts to codeplug (already saved via references)"""
        # Contacts are already part of codeplug.contacts list
        # This method is here for consistency with other widgets
        pass
