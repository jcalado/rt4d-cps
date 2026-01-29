"""Message Radio Dialog for reading/writing messages to radio"""

import platform
import serial
import serial.tools.list_ports
from typing import Optional, List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QProgressBar, QMessageBox, QCheckBox, QGroupBox
)
from PySide6.QtCore import QThread, Signal

from rt4d_codeplug.models import Message, MessageStore, MessageType
from rt4d_codeplug.messages import MessageParser, MessageSerializer
from rt4d_codeplug.constants import MESSAGE_REGIONS
from . import theme as _theme
from rt4d_uart import RT4DUART


class MessageWorker(QThread):
    """Worker thread for message radio operations"""
    progress = Signal(int, str)  # percent, message
    finished = Signal(bool, str, object)  # success, message, result

    def __init__(self, operation: str, port: str, regions: List[str] = None,
                 messages: List[Message] = None, region_name: str = None):
        super().__init__()
        self.operation = operation
        self.port = port
        self.regions = regions or ["presets", "drafts", "inbox", "outbox"]
        self.messages = messages
        self.region_name = region_name

    def run(self):
        """Execute radio operation"""
        uart = RT4DUART()
        try:
            uart.open(self.port)

            if uart.is_bootloader_mode():
                self.finished.emit(False, "Radio is in bootloader mode!", None)
                return

            uart.command_notify()

            if self.operation == "read":
                self.read_messages(uart)
            elif self.operation == "write":
                self.write_messages(uart)

            uart.command_close()

        except serial.SerialException as e:
            self.finished.emit(False, f"Could not open {self.port}. Check the COM port and ensure the radio is connected.\n\n{e}", None)
        except Exception as e:
            self.finished.emit(False, str(e), None)
        finally:
            try:
                uart.close()
            except Exception:
                pass

    def read_messages(self, uart: RT4DUART):
        """Read messages from radio"""
        store = MessageStore()

        total_regions = len(self.regions)
        for i, region_name in enumerate(self.regions):
            base_percent = int((i / total_regions) * 90)
            self.progress.emit(base_percent, f"Reading {region_name}...")

            region_info = MESSAGE_REGIONS.get(region_name)
            if not region_info:
                continue

            msg_type = {
                "presets": MessageType.PRESET,
                "drafts": MessageType.DRAFT,
                "inbox": MessageType.INBOX,
                "outbox": MessageType.OUTBOX
            }.get(region_name, MessageType.PRESET)

            def progress_cb(current, total):
                region_percent = int((current / total) * (90 / total_regions))
                self.progress.emit(base_percent + region_percent, f"Reading {region_name}...")

            data = uart.read_messages(region_name, progress_cb)
            if data is None:
                self.finished.emit(False, f"Failed to read {region_name}", None)
                return

            messages = MessageParser.parse_region(data, msg_type, region_info["count"])

            if region_name == "presets":
                store.presets = messages
            elif region_name == "drafts":
                store.drafts = messages
            elif region_name == "inbox":
                store.inbox = messages
            elif region_name == "outbox":
                store.outbox = messages

        self.progress.emit(100, "Complete")
        self.finished.emit(True, "Messages read successfully", store)

    def write_messages(self, uart: RT4DUART):
        """Write messages to radio"""
        if not self.messages or not self.region_name:
            self.finished.emit(False, "No messages to write", None)
            return

        region_info = MESSAGE_REGIONS.get(self.region_name)
        if not region_info:
            self.finished.emit(False, f"Unknown region: {self.region_name}", None)
            return

        self.progress.emit(10, f"Serializing {self.region_name}...")

        # Serialize messages
        data = MessageSerializer.serialize_region(self.messages, region_info["count"])

        def progress_cb(current, total):
            percent = int((current / total) * 80) + 10
            self.progress.emit(percent, f"Writing {self.region_name}...")

        self.progress.emit(20, f"Writing {self.region_name}...")

        # Note: Writing messages may not work with current implementation
        # The region IDs for message areas need verification
        success = uart.write_messages(self.region_name, data, progress_cb)

        if success:
            self.progress.emit(100, "Complete")
            self.finished.emit(True, f"{self.region_name} written successfully", None)
        else:
            self.finished.emit(False, f"Failed to write {self.region_name}", None)


class MessageRadioDialog(QDialog):
    """Dialog for reading/writing messages from/to radio"""

    def __init__(self, parent=None, operation: str = "read",
                 messages: List[Message] = None, region: str = None):
        super().__init__(parent)
        self.operation = operation
        self.messages = messages
        self.region = region
        self.worker: Optional[MessageWorker] = None
        self.result_store: Optional[MessageStore] = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        if self.operation == "read":
            self.setWindowTitle("Read Messages from Radio")
        else:
            self.setWindowTitle("Write Messages to Radio")

        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Warning for write operation
        if self.operation == "write":
            warning = QLabel("Note: Writing messages to radio may not be fully supported yet.")
            warning.setStyleSheet(f"color: {_theme.error_color()}; font-weight: bold;")
            warning.setWordWrap(True)
            layout.addWidget(warning)

        # Port selection
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Serial Port:"))
        self.port_combo = QComboBox()
        self.refresh_ports()
        port_layout.addWidget(self.port_combo)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_ports)
        port_layout.addWidget(btn_refresh)
        layout.addLayout(port_layout)

        # Region selection (only for read operation)
        if self.operation == "read":
            region_group = QGroupBox("Regions to Read")
            region_layout = QVBoxLayout()

            self.check_presets = QCheckBox("Presets (16 quick messages)")
            self.check_presets.setChecked(True)
            region_layout.addWidget(self.check_presets)

            self.check_drafts = QCheckBox("Drafts (256 draft messages)")
            self.check_drafts.setChecked(True)
            region_layout.addWidget(self.check_drafts)

            self.check_inbox = QCheckBox("Inbox (256 received messages)")
            self.check_inbox.setChecked(True)
            region_layout.addWidget(self.check_inbox)

            self.check_outbox = QCheckBox("Outbox (256 sent messages)")
            self.check_outbox.setChecked(True)
            region_layout.addWidget(self.check_outbox)

            region_group.setLayout(region_layout)
            layout.addWidget(region_group)
        else:
            # Write operation info
            info = QLabel(f"Writing {len(self.messages)} preset message(s) to radio.")
            layout.addWidget(info)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.btn_start = QPushButton("Start" if self.operation == "read" else "Write")
        self.btn_start.clicked.connect(self.start_operation)
        button_layout.addWidget(self.btn_start)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)

        layout.addLayout(button_layout)

    def refresh_ports(self):
        """Refresh available serial ports"""
        self.port_combo.clear()
        ports = list(serial.tools.list_ports.comports())

        # On Linux, prioritize USB ports
        if platform.system() == "Linux":
            usb_ports = [p for p in ports if "USB" in p.device.upper() or "USB" in p.description.upper()]
            other_ports = [p for p in ports if p not in usb_ports]
            ports = usb_ports + other_ports

        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)

    def start_operation(self):
        """Start the read/write operation"""
        port = self.port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "Error", "No serial port selected")
            return

        if self.operation == "read":
            regions = []
            if self.check_presets.isChecked():
                regions.append("presets")
            if self.check_drafts.isChecked():
                regions.append("drafts")
            if self.check_inbox.isChecked():
                regions.append("inbox")
            if self.check_outbox.isChecked():
                regions.append("outbox")

            if not regions:
                QMessageBox.warning(self, "Error", "No regions selected")
                return

            self.worker = MessageWorker("read", port, regions=regions)
        else:
            # Confirm write
            reply = QMessageBox.question(
                self, "Confirm Write",
                "Are you sure you want to write messages to the radio?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            self.worker = MessageWorker(
                "write", port,
                messages=self.messages,
                region_name=self.region
            )

        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_start.setEnabled(False)
        self.status_label.setText("Connecting to radio...")

        self.worker.start()

    def on_progress(self, percent: int, message: str):
        """Handle progress update"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def on_finished(self, success: bool, message: str, result):
        """Handle completion"""
        self.progress_bar.setValue(100 if success else 0)
        self.status_label.setText(message)
        self.btn_start.setEnabled(True)

        if success:
            if isinstance(result, MessageStore):
                self.result_store = result
            self.accept()
        else:
            QMessageBox.critical(self, "Error", message)

    def get_message_store(self) -> Optional[MessageStore]:
        """Get the result message store (for read operations)"""
        return self.result_store
