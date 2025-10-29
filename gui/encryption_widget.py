"""Encryption Widget for managing encryption keys"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QSplitter, QLabel, QLineEdit, QComboBox,
    QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from rt4d_codeplug import Codeplug, EncryptionKey, EncryptionType


class EncryptionWidget(QWidget):
    """Widget for displaying and editing encryption keys"""

    data_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.codeplug: Optional[Codeplug] = None
        self.current_key: Optional[EncryptionKey] = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        layout = QHBoxLayout()
        self.setLayout(layout)

        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left side: Encryption keys table
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        left_layout.addWidget(QLabel("<b>Encryption Keys</b>"))

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["No.", "Key Alias", "Type", "Key Value"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Resize columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()
        self.btn_init = QPushButton("Initialize 256 Keys")
        self.btn_init.clicked.connect(self.initialize_keys)
        button_layout.addWidget(self.btn_init)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self.delete_key)
        button_layout.addWidget(self.btn_delete)

        button_layout.addStretch()
        left_layout.addLayout(button_layout)

        # Right side: Key details
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        self.details_label = QLabel("<b>Select a key</b>")
        self.details_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.details_label)

        # Details group
        details_group = QGroupBox("Key Details")
        details_layout = QFormLayout()

        self.edit_alias = QLineEdit()
        self.edit_alias.setMaxLength(14)
        self.edit_alias.textChanged.connect(self.on_detail_changed)
        self.edit_alias.setEnabled(False)
        details_layout.addRow("Key Alias:", self.edit_alias)

        self.combo_type = QComboBox()
        self.combo_type.addItem("ARC", EncryptionType.ARC.value)
        self.combo_type.addItem("AES-128", EncryptionType.AES_128.value)
        self.combo_type.addItem("AES-256", EncryptionType.AES_256.value)
        self.combo_type.currentIndexChanged.connect(self.on_type_changed)
        self.combo_type.setEnabled(False)
        details_layout.addRow("Type:", self.combo_type)

        self.edit_value = QLineEdit()
        self.edit_value.textChanged.connect(self.on_detail_changed)
        self.edit_value.setEnabled(False)
        self.edit_value.setPlaceholderText("Enter hex value (uppercase)")
        details_layout.addRow("Key Value:", self.edit_value)

        self.label_length = QLabel()
        details_layout.addRow("Length:", self.label_length)

        details_group.setLayout(details_layout)
        right_layout.addWidget(details_group)

        # Help text
        help_text = QLabel(
            "<i>Key value lengths:</i><br>"
            "• ARC: 10 hex characters (5 bytes)<br>"
            "• AES-128: 32 hex characters (16 bytes)<br>"
            "• AES-256: 64 hex characters (32 bytes)"
        )
        help_text.setWordWrap(True)
        right_layout.addWidget(help_text)

        right_layout.addStretch()

        # Add to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

    def load_codeplug(self, codeplug: Codeplug):
        """Load encryption keys from codeplug"""
        self.codeplug = codeplug
        self.refresh_table()

    def refresh_table(self):
        """Refresh encryption keys table"""
        if not self.codeplug:
            return

        self.table.setRowCount(0)
        keys = sorted(self.codeplug.get_active_encryption_keys(), key=lambda k: k.index)

        for row, key in enumerate(keys):
            self.table.insertRow(row)

            # Alternate row colors (like CPS)
            if row % 2 == 0:
                bg_color = QColor(255, 250, 205)  # LemonChiffon
            else:
                bg_color = QColor(255, 255, 255)  # White

            # No. (1-based)
            item_index = QTableWidgetItem(str(key.index + 1))
            item_index.setBackground(bg_color)
            self.table.setItem(row, 0, item_index)

            # Key Alias
            item_alias = QTableWidgetItem(key.alias)
            item_alias.setBackground(bg_color)
            self.table.setItem(row, 1, item_alias)

            # Type
            type_name = self.get_type_name(key.enc_type)
            item_type = QTableWidgetItem(type_name)
            item_type.setBackground(bg_color)
            self.table.setItem(row, 2, item_type)

            # Key Value
            item_value = QTableWidgetItem(key.value)
            item_value.setBackground(bg_color)
            self.table.setItem(row, 3, item_value)

    def get_type_name(self, enc_type: EncryptionType) -> str:
        """Get display name for encryption type"""
        if enc_type == EncryptionType.ARC:
            return "ARC"
        elif enc_type == EncryptionType.AES_128:
            return "AES-128"
        elif enc_type == EncryptionType.AES_256:
            return "AES-256"
        return "Unknown"

    def on_selection_changed(self):
        """Handle key selection"""
        current_row = self.table.currentRow()
        if current_row < 0:
            self.current_key = None
            self.details_label.setText("<b>Select a key</b>")
            self.edit_alias.setEnabled(False)
            self.combo_type.setEnabled(False)
            self.edit_value.setEnabled(False)
            self.label_length.setText("")
            return

        # Get selected key
        index_item = self.table.item(current_row, 0)
        key_index = int(index_item.text()) - 1
        self.current_key = self.codeplug.get_encryption_key(key_index)

        if self.current_key:
            self.details_label.setText(f"<b>{self.current_key.alias}</b>")
            self.load_key_details()
            self.edit_alias.setEnabled(True)
            self.combo_type.setEnabled(True)
            self.edit_value.setEnabled(True)

    def load_key_details(self):
        """Load key details into form"""
        if not self.current_key:
            return

        # Block signals while loading
        self.edit_alias.blockSignals(True)
        self.combo_type.blockSignals(True)
        self.edit_value.blockSignals(True)

        # Load values
        self.edit_alias.setText(self.current_key.alias)

        # Set encryption type
        for i in range(self.combo_type.count()):
            if self.combo_type.itemData(i) == self.current_key.enc_type.value:
                self.combo_type.setCurrentIndex(i)
                break

        self.edit_value.setText(self.current_key.value)
        self.update_length_info()

        # Unblock signals
        self.edit_alias.blockSignals(False)
        self.combo_type.blockSignals(False)
        self.edit_value.blockSignals(False)

    def update_length_info(self):
        """Update length info label"""
        if not self.current_key:
            self.label_length.setText("")
            return

        current_len = len(self.edit_value.text())
        max_len = self.current_key.get_expected_length()

        if current_len == max_len:
            color = "green"
        elif current_len > max_len:
            color = "red"
        else:
            color = "orange"

        self.label_length.setText(
            f'<span style="color: {color};">{current_len} / {max_len} characters</span>'
        )

    def on_type_changed(self):
        """Handle encryption type change"""
        if not self.current_key:
            return

        # Update encryption type
        type_value = self.combo_type.currentData()
        if type_value == EncryptionType.ARC.value:
            self.current_key.enc_type = EncryptionType.ARC
            self.edit_value.setMaxLength(10)
        elif type_value == EncryptionType.AES_128.value:
            self.current_key.enc_type = EncryptionType.AES_128
            self.edit_value.setMaxLength(32)
        elif type_value == EncryptionType.AES_256.value:
            self.current_key.enc_type = EncryptionType.AES_256
            self.edit_value.setMaxLength(64)

        # Trim value if needed
        max_len = self.current_key.get_expected_length()
        if len(self.current_key.value) > max_len:
            self.current_key.value = self.current_key.value[:max_len]
            self.edit_value.setText(self.current_key.value)

        self.update_length_info()
        self.on_detail_changed()

    def on_detail_changed(self):
        """Handle detail changes"""
        if not self.current_key:
            return

        # Validate hex input
        value_text = self.edit_value.text().upper()
        # Remove non-hex characters
        value_text = ''.join(c for c in value_text if c in '0123456789ABCDEF')

        # Update if cleaned
        if value_text != self.edit_value.text():
            self.edit_value.blockSignals(True)
            self.edit_value.setText(value_text)
            self.edit_value.blockSignals(False)

        # Save changes
        self.current_key.alias = self.edit_alias.text()
        self.current_key.value = value_text

        self.update_length_info()

        # Update table
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.item(current_row, 1).setText(self.current_key.alias)
            self.table.item(current_row, 2).setText(self.get_type_name(self.current_key.enc_type))
            self.table.item(current_row, 3).setText(self.current_key.value)

        self.details_label.setText(f"<b>{self.current_key.alias}</b>")
        self.data_modified.emit()

    def initialize_keys(self):
        """Initialize 256 encryption keys with default values"""
        if not self.codeplug:
            QMessageBox.warning(self, "Warning", "No codeplug loaded")
            return

        reply = QMessageBox.question(
            self,
            "Initialize Keys",
            "This will initialize 256 encryption keys with default values.\n"
            "Any existing keys will be replaced. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        # Clear existing keys
        self.codeplug.encryption_keys.clear()

        # Create 256 keys with default values
        for i in range(256):
            key = EncryptionKey(
                index=i,
                alias=f"Key Alias {i + 1}",
                enc_type=EncryptionType.ARC,
                value=f"{i + 1:010X}"  # Hex value 0000000001 to 0000000100
            )
            self.codeplug.add_encryption_key(key)

        self.refresh_table()
        self.data_modified.emit()

        QMessageBox.information(self, "Success", "Initialized 256 encryption keys")

    def delete_key(self):
        """Delete selected encryption key"""
        if not self.current_key:
            QMessageBox.warning(self, "Warning", "No key selected")
            return

        reply = QMessageBox.question(
            self,
            "Delete Key",
            f"Delete encryption key '{self.current_key.alias}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.codeplug.encryption_keys.remove(self.current_key)
            self.current_key = None
            self.refresh_table()
            self.data_modified.emit()
