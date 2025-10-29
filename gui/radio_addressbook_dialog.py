"""Radio Address Book Upload Dialog"""

import serial.tools.list_ports
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QProgressBar, QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt, QThread, Signal

from rt4d_uart import RT4DUART
from rt4d_codeplug.global_contacts import GlobalContactDatabase, GlobalContactCSVParser


class AddressBookWriteThread(QThread):
    """Worker thread for writing address book to radio"""

    progress_updated = Signal(int, int)  # current_block, total_blocks
    write_finished = Signal(bool, str)  # success, message
    log_message = Signal(str)

    def __init__(self, port_name: str, baudrate: int, database: GlobalContactDatabase):
        super().__init__()
        self.port_name = port_name
        self.baudrate = baudrate
        self.database = database

    def run(self):
        """Execute write operation in background thread"""
        uart = RT4DUART()

        try:
            # Open serial port
            self.log_message.emit(f"Opening {self.port_name} at {self.baudrate} baud...")
            uart.open(self.port_name, self.baudrate)

            # Send notify command
            self.log_message.emit("Connecting to radio...")
            if not uart.command_notify():
                self.write_finished.emit(False, "Failed to connect to radio. Is it in normal mode?")
                uart.close()
                return

            # Export database to radio format
            self.log_message.emit(f"Preparing {len(self.database):,} contacts for upload...")
            data = GlobalContactCSVParser.export_for_radio(self.database)
            self.log_message.emit(f"Data size: {len(data):,} bytes")

            # Write address book
            def progress_callback(current, total):
                self.progress_updated.emit(current, total)
                percentage = (current / total) * 100
                self.log_message.emit(f"Block {current}/{total} ({percentage:.1f}%)")

            self.log_message.emit("Writing address book to radio...")
            success = uart.command_write_addressbook(data, progress_callback)

            # Close connection
            self.log_message.emit("Closing connection...")
            uart.command_close()
            uart.close()

            if success:
                self.write_finished.emit(True, f"Successfully wrote {len(self.database):,} contacts to radio!")
            else:
                self.write_finished.emit(False, "Write operation failed. Check logs for details.")

        except Exception as e:
            self.write_finished.emit(False, f"Error: {str(e)}")
            try:
                uart.close()
            except:
                pass


class RadioAddressBookDialog(QDialog):
    """Dialog for writing address book to radio"""

    def __init__(self, parent, database: GlobalContactDatabase):
        super().__init__(parent)
        self.database = database
        self.write_thread = None
        self.init_ui()

    def init_ui(self):
        """Initialize user interface"""
        self.setWindowTitle("Write Address Book to Radio")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel(f"<b>Upload {len(self.database):,} contacts to radio</b>")
        layout.addWidget(title)

        # Port selection
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Serial Port:"))
        self.port_combo = QComboBox()
        self.refresh_ports()
        port_layout.addWidget(self.port_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(refresh_btn)
        layout.addLayout(port_layout)

        # Baud rate selection
        baud_layout = QHBoxLayout()
        baud_layout.addWidget(QLabel("Baud Rate:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["115200", "256000"])
        self.baud_combo.setCurrentIndex(0)
        baud_layout.addWidget(self.baud_combo)
        baud_layout.addStretch()
        layout.addLayout(baud_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Log output
        log_label = QLabel("Log:")
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        layout.addWidget(self.log_text)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.write_btn = QPushButton("Write to Radio")
        self.write_btn.clicked.connect(self.on_write)
        self.write_btn.setStyleSheet("font-weight: bold;")
        button_layout.addWidget(self.write_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def refresh_ports(self):
        """Refresh available serial ports"""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()

        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)

        if self.port_combo.count() == 0:
            self.port_combo.addItem("No ports found", None)

    def log(self, message: str):
        """Add message to log"""
        self.log_text.append(message)

    def on_write(self):
        """Start write operation"""
        port_name = self.port_combo.currentData()
        if not port_name:
            QMessageBox.warning(self, "Error", "Please select a valid serial port.")
            return

        baudrate = int(self.baud_combo.currentText())

        # Confirm operation
        reply = QMessageBox.question(
            self,
            "Confirm Write",
            f"Write {len(self.database):,} contacts to radio via {port_name}?\n\n"
            f"This will overwrite the existing address book on the radio.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Disable UI during write
        self.write_btn.setEnabled(False)
        self.port_combo.setEnabled(False)
        self.baud_combo.setEnabled(False)
        self.close_btn.setEnabled(False)

        # Clear log
        self.log_text.clear()
        self.progress_bar.setValue(0)

        # Start write thread
        self.write_thread = AddressBookWriteThread(port_name, baudrate, self.database)
        self.write_thread.progress_updated.connect(self.on_progress_updated)
        self.write_thread.write_finished.connect(self.on_write_finished)
        self.write_thread.log_message.connect(self.log)
        self.write_thread.start()

    def on_progress_updated(self, current: int, total: int):
        """Update progress bar"""
        percentage = int((current / total) * 100)
        self.progress_bar.setValue(percentage)

    def on_write_finished(self, success: bool, message: str):
        """Handle write completion"""
        # Re-enable UI
        self.write_btn.setEnabled(True)
        self.port_combo.setEnabled(True)
        self.baud_combo.setEnabled(True)
        self.close_btn.setEnabled(True)

        # Show result
        self.log(message)

        if success:
            QMessageBox.information(self, "Success", message)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", message)
