"""Message Widget for managing DMR SMS messages"""

from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QLabel, QTabWidget
)
from PySide6.QtCore import Qt, Signal

from rt4d_codeplug.models import Message, MessageStore, MessageType, CallType
from rt4d_codeplug.constants import (
    MAX_PRESET_MESSAGES, MAX_DRAFT_MESSAGES,
    MAX_INBOX_MESSAGES, MAX_OUTBOX_MESSAGES,
    MESSAGE_TEXT_MAX_LENGTH
)


class MessageListWidget(QWidget):
    """Widget for displaying and editing a single message type"""

    data_modified = Signal()

    def __init__(self, msg_type: MessageType, max_count: int, editable: bool = False, parent=None):
        super().__init__(parent)
        self.msg_type = msg_type
        self.max_count = max_count
        self.editable = editable
        self.messages: List[Message] = []
        self._loading = False  # Flag to prevent signals during load
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.table = QTableWidget()

        # Set columns based on message type
        # Presets and Drafts: just index and text
        # Inbox and Outbox: index, type, ID, time, message
        if self.msg_type in (MessageType.PRESET, MessageType.DRAFT):
            self.table.setColumnCount(2)
            self.table.setHorizontalHeaderLabels(["#", "Message"])
        else:
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["#", "Type", "ID", "Time", "Message"])

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)

        # Resize columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        if self.msg_type in (MessageType.PRESET, MessageType.DRAFT):
            header.setSectionResizeMode(1, QHeaderView.Stretch)
        else:
            # Inbox/Outbox: #, Type, ID, Time, Message
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.Stretch)

        # Connect cell change signal for editable tables
        if self.editable:
            self.table.cellChanged.connect(self.on_cell_changed)

        layout.addWidget(self.table)

        # Buttons (only for Presets)
        if self.editable:
            button_layout = QHBoxLayout()
            self.btn_add = QPushButton("Add Message")
            self.btn_add.clicked.connect(self.add_message)
            button_layout.addWidget(self.btn_add)

            self.btn_delete = QPushButton("Delete")
            self.btn_delete.clicked.connect(self.delete_message)
            button_layout.addWidget(self.btn_delete)

            button_layout.addStretch()
            layout.addLayout(button_layout)

    def load_messages(self, messages: List[Message]):
        """Load messages into the widget"""
        self.messages = messages
        self.refresh_table()

    def get_messages(self) -> List[Message]:
        """Get all messages from the widget"""
        return self.messages

    def refresh_table(self):
        """Refresh the message table"""
        self._loading = True
        self.table.setRowCount(0)
        palette = self.table.palette()
        readonly_bg = palette.alternateBase().color()

        for row, message in enumerate(self.messages):
            self.table.insertRow(row)

            # Index column (always read-only)
            item_index = QTableWidgetItem(str(message.index + 1))
            item_index.setBackground(readonly_bg)
            item_index.setFlags(item_index.flags() & ~Qt.ItemIsEditable)
            item_index.setData(Qt.UserRole, message.uuid)
            self.table.setItem(row, 0, item_index)

            if self.msg_type in (MessageType.PRESET, MessageType.DRAFT):
                # Message column
                item_msg = QTableWidgetItem(message.text)
                if not self.editable:
                    item_msg.setFlags(item_msg.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 1, item_msg)
            else:
                # Inbox/Outbox: Type, ID, Time, Message (all read-only)
                call_type_names = {
                    CallType.PRIVATE: "Private",
                    CallType.GROUP: "Group",
                    CallType.ALL_CALL: "All Call"
                }

                # Type
                item_type = QTableWidgetItem(call_type_names.get(message.call_type, "-"))
                item_type.setFlags(item_type.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 1, item_type)

                # ID (Contact ID)
                contact_str = str(message.contact_id) if message.contact_id > 0 else "-"
                item_id = QTableWidgetItem(contact_str)
                item_id.setFlags(item_id.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 2, item_id)

                # Time (Timestamp)
                ts_str = message.timestamp.strftime("%y-%m-%d %H:%M:%S") if message.timestamp else "-"
                item_time = QTableWidgetItem(ts_str)
                item_time.setFlags(item_time.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 3, item_time)

                # Message
                item_msg = QTableWidgetItem(message.text)
                item_msg.setFlags(item_msg.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 4, item_msg)

        self._loading = False

    def on_cell_changed(self, row: int, column: int):
        """Handle cell content changes"""
        if self._loading:
            return

        # Only handle message column changes for Presets
        if self.msg_type == MessageType.PRESET and column == 1:
            item = self.table.item(row, column)
            if item:
                text = item.text()

                # Enforce character limit (GBK byte length)
                try:
                    text_bytes = text.encode('gbk')
                    if len(text_bytes) > MESSAGE_TEXT_MAX_LENGTH:
                        text_bytes = text_bytes[:MESSAGE_TEXT_MAX_LENGTH]
                        text = text_bytes.decode('gbk', errors='ignore')
                        self._loading = True
                        item.setText(text)
                        self._loading = False
                except UnicodeEncodeError:
                    pass

                # Update message object
                index_item = self.table.item(row, 0)
                if index_item:
                    msg_uuid = index_item.data(Qt.UserRole)
                    for msg in self.messages:
                        if msg.uuid == msg_uuid:
                            msg.text = text
                            break

                self.data_modified.emit()

    def add_message(self):
        """Add a new message"""
        if len(self.messages) >= self.max_count:
            QMessageBox.warning(
                self, "Warning",
                f"Maximum messages reached ({self.max_count})"
            )
            return

        # Find next available index
        used_indices = {m.index for m in self.messages}
        next_index = 0
        for i in range(self.max_count):
            if i not in used_indices:
                next_index = i
                break

        new_message = Message(
            index=next_index,
            message_type=self.msg_type,
            text=""
        )

        self.messages.append(new_message)
        self.refresh_table()
        self.data_modified.emit()

        # Select the new message and start editing
        new_row = len(self.messages) - 1
        self.table.selectRow(new_row)
        self.table.editItem(self.table.item(new_row, 1))

    def delete_message(self):
        """Delete selected message"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "No message selected")
            return

        index_item = self.table.item(current_row, 0)
        msg_uuid = index_item.data(Qt.UserRole)

        for msg in self.messages:
            if msg.uuid == msg_uuid:
                reply = QMessageBox.question(
                    self,
                    "Confirm Delete",
                    f"Delete message #{msg.index + 1}?",
                    QMessageBox.Yes | QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    self.messages.remove(msg)
                    self.refresh_table()
                    self.data_modified.emit()
                break


class MessageWidget(QWidget):
    """Main widget for managing all message types"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.message_store = MessageStore()
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Info label
        info_label = QLabel(
            "Messages are stored on the radio's SPI flash, separate from the codeplug file. "
            "Use 'Read from Radio' to load messages, and 'Write Presets to Radio' to save preset messages."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(info_label)

        # Button bar
        button_layout = QHBoxLayout()

        self.btn_read = QPushButton("Read from Radio...")
        self.btn_read.clicked.connect(self.read_from_radio)
        button_layout.addWidget(self.btn_read)

        self.btn_write = QPushButton("Write Presets to Radio...")
        self.btn_write.clicked.connect(self.write_presets_to_radio)
        button_layout.addWidget(self.btn_write)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Sub-tabs for message types
        self.sub_tabs = QTabWidget()
        layout.addWidget(self.sub_tabs)

        # Presets tab (editable)
        self.presets_widget = MessageListWidget(
            MessageType.PRESET, MAX_PRESET_MESSAGES, editable=True
        )
        self.sub_tabs.addTab(self.presets_widget, "Presets")

        # Drafts tab (read-only)
        self.drafts_widget = MessageListWidget(
            MessageType.DRAFT, MAX_DRAFT_MESSAGES, editable=False
        )
        self.sub_tabs.addTab(self.drafts_widget, "Drafts")

        # Inbox tab (read-only)
        self.inbox_widget = MessageListWidget(
            MessageType.INBOX, MAX_INBOX_MESSAGES, editable=False
        )
        self.sub_tabs.addTab(self.inbox_widget, "Inbox")

        # Outbox tab (read-only)
        self.outbox_widget = MessageListWidget(
            MessageType.OUTBOX, MAX_OUTBOX_MESSAGES, editable=False
        )
        self.sub_tabs.addTab(self.outbox_widget, "Outbox")

    def load_message_store(self, store: MessageStore):
        """Load messages from a MessageStore"""
        self.message_store = store
        self.presets_widget.load_messages(store.presets)
        self.drafts_widget.load_messages(store.drafts)
        self.inbox_widget.load_messages(store.inbox)
        self.outbox_widget.load_messages(store.outbox)

    def get_message_store(self) -> MessageStore:
        """Get the current MessageStore"""
        self.message_store.presets = self.presets_widget.get_messages()
        self.message_store.drafts = self.drafts_widget.get_messages()
        self.message_store.inbox = self.inbox_widget.get_messages()
        self.message_store.outbox = self.outbox_widget.get_messages()
        return self.message_store

    def read_from_radio(self):
        """Open dialog to read messages from radio"""
        from .message_radio_dialog import MessageRadioDialog
        dialog = MessageRadioDialog(self, operation="read")
        if dialog.exec():
            store = dialog.get_message_store()
            if store:
                self.load_message_store(store)
                QMessageBox.information(
                    self, "Success",
                    f"Loaded {len(store.get_active_presets())} presets, "
                    f"{len(store.get_active_drafts())} drafts, "
                    f"{len(store.get_active_inbox())} inbox, "
                    f"{len(store.get_active_outbox())} outbox messages."
                )

    def write_presets_to_radio(self):
        """Open dialog to write preset messages to radio"""
        # Get current presets
        presets = self.presets_widget.get_messages()
        if not presets:
            QMessageBox.warning(
                self, "Warning",
                "No preset messages to write."
            )
            return

        from .message_radio_dialog import MessageRadioDialog
        dialog = MessageRadioDialog(
            self, operation="write",
            messages=presets, region="presets"
        )
        dialog.exec()
