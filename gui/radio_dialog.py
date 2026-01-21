"""Radio Backup and Flash Dialogs"""

import platform
import serial.tools.list_ports
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QFileDialog, QProgressBar, QMessageBox,
    QCheckBox, QGroupBox
)
from PySide6.QtCore import Qt, QThread, Signal

from rt4d_codeplug import Codeplug, CodeplugParser, CodeplugSerializer
from rt4d_uart import RT4DUART
from rt4d_codeplug.constants import SPI_REGIONS
from rt4d_codeplug.utils import detect_settings_bank


class RadioWorker(QThread):
    """Worker thread for radio operations"""
    progress = Signal(int, str)  # percent, message
    finished = Signal(bool, str)  # success, message

    def __init__(self, operation: str, port: str, file_path: Optional[str] = None,
                 regions: Optional[list] = None, codeplug: Optional[Codeplug] = None):
        super().__init__()
        self.operation = operation
        self.port = port
        self.file_path = file_path
        self.regions = regions
        self.codeplug = codeplug

    def run(self):
        """Execute radio operation"""
        try:
            uart = RT4DUART()
            uart.open(self.port)

            if uart.is_bootloader_mode():
                self.finished.emit(False, "Radio is in bootloader mode, not normal mode!")
                uart.close()
                return

            uart.command_notify()

            if self.operation == "backup":
                self.backup(uart)
            elif self.operation == "flash":
                self.flash(uart)

            uart.command_close()
            uart.close()

        except Exception as e:
            self.finished.emit(False, str(e))

    def backup(self, uart: RT4DUART):
        """Backup from radio"""
        from rt4d_codeplug.constants import TOTAL_SIZE, OFFSET_CFG, OFFSET_CHANNELS, OFFSET_CONTACTS
        from rt4d_codeplug.constants import OFFSET_GROUPLISTS, OFFSET_ENCRYPT, OFFSET_ZONES, OFFSET_FM
        from rt4d_codeplug.constants import SIZE_CFG, SIZE_CHANNELS, SIZE_CONTACTS, SIZE_GROUPLISTS
        from rt4d_codeplug.constants import SIZE_ENCRYPT, SIZE_ZONES, SIZE_FM

        # Full backup
        if not self.regions:
            def progress_callback(current, total):
                # Map to 10-90% range
                percent = int((current / total) * 80) + 10
                self.progress.emit(percent, f"Reading SPI flash: {current}/{total} KB")

            success = uart.read_spi_dump(self.file_path, progress_callback)
            if success:
                self.progress.emit(100, "Complete")
                self.finished.emit(True, f"Backup saved to {self.file_path}")
            else:
                self.finished.emit(False, "Failed to read SPI flash")
            return

        # Selective backup
        codeplug_data = bytearray(b'\xff' * TOTAL_SIZE)

        # Detect which bank contains active settings (beta41+ dual-bank support)
        settings_bank_addr = detect_settings_bank(uart)
        self.progress.emit(5, f"Detected settings at bank 0x{settings_bank_addr:06X}")

        region_map = {
            'main_settings': (OFFSET_CFG, SIZE_CFG, settings_bank_addr),
            'channels': (OFFSET_CHANNELS, SIZE_CHANNELS, 0x004000),
            'contacts': (OFFSET_CONTACTS, SIZE_CONTACTS, 0x05C000),
            'groups': (OFFSET_GROUPLISTS, SIZE_GROUPLISTS, 0x07C000),
            'dmr_keys': (OFFSET_ENCRYPT, SIZE_ENCRYPT, 0x082000),
            'zones': (OFFSET_ZONES, SIZE_ZONES, 0x01C000),
            'fm_settings': (OFFSET_FM, SIZE_FM, 0x0D6000),
        }

        total_regions = len(self.regions)
        for i, region_name in enumerate(self.regions):
            percent = int((i / total_regions) * 80) + 10
            self.progress.emit(percent, f"Reading {region_name}...")

            if region_name not in region_map:
                continue

            file_offset, size, spi_address = region_map[region_name]
            region_data = uart.read_spi_region(spi_address, size)

            if region_data is None:
                self.finished.emit(False, f"Failed to read {region_name}")
                return

            codeplug_data[file_offset:file_offset + size] = region_data

        # Write to file
        self.progress.emit(90, "Writing file...")
        with open(self.file_path, 'wb') as f:
            f.write(codeplug_data)

        self.finished.emit(True, f"Backup saved to {self.file_path}")

    def flash(self, uart: RT4DUART):
        """Flash to radio"""
        data = CodeplugSerializer.serialize(self.codeplug)

        regions_to_flash = self.regions or ["main_settings", "channels", "contacts", "groups", "dmr_keys", "zones"]
        total_regions = len(regions_to_flash)

        for i, region_name in enumerate(regions_to_flash):
            percent = int((i / total_regions) * 80) + 10
            self.progress.emit(percent, f"Flashing {region_name}...")

            if region_name not in SPI_REGIONS:
                continue

            # Extract appropriate data based on region
            if region_name == "channels":
                region_data = data[0x1000:0xD000]
            elif region_name == "contacts":
                region_data = data[0xD000:0x1D000]
            elif region_name == "groups":
                region_data = data[0x1D000:0x20000]
            elif region_name == "dmr_keys":
                region_data = data[0x20000:0x23000]
            elif region_name == "zones":
                region_data = data[0x23000:0x43000]
            elif region_name == "main_settings":
                region_data = data[0x0:0x1000]
            else:
                continue

            if not uart.write_spi_region(region_data, region_name):
                self.finished.emit(False, f"Failed to flash {region_name}")
                return

        self.finished.emit(True, "Flashing complete!")


class RadioBackupDialog(QDialog):
    """Dialog for backing up from radio"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.backup_file: Optional[Path] = None
        self.worker: Optional[RadioWorker] = None
        self.was_full_backup: bool = False
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Backup from Radio")
        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout()
        self.setLayout(layout)

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

        # File selection
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Save to:"))
        self.file_label = QLabel("(not selected)")
        file_layout.addWidget(self.file_label)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(btn_browse)
        layout.addLayout(file_layout)

        # Region selection
        region_group = QGroupBox("Regions to Backup")
        region_layout = QVBoxLayout()

        self.check_full = QCheckBox("Full Backup (entire 4MB SPI flash)")
        self.check_full.setChecked(False)
        self.check_full.toggled.connect(self.on_full_backup_toggled)
        region_layout.addWidget(self.check_full)

        self.check_settings = QCheckBox("Main Settings")
        self.check_settings.setChecked(True)
        region_layout.addWidget(self.check_settings)

        self.check_channels = QCheckBox("Channels")
        self.check_channels.setChecked(True)
        region_layout.addWidget(self.check_channels)

        self.check_contacts = QCheckBox("Contacts")
        self.check_contacts.setChecked(True)
        region_layout.addWidget(self.check_contacts)

        self.check_groups = QCheckBox("RX Groups (Group Lists)")
        self.check_groups.setChecked(True)
        region_layout.addWidget(self.check_groups)

        self.check_encryption = QCheckBox("Encryption Keys")
        self.check_encryption.setChecked(True)
        region_layout.addWidget(self.check_encryption)

        self.check_zones = QCheckBox("Zones")
        self.check_zones.setChecked(True)
        region_layout.addWidget(self.check_zones)

        region_group.setLayout(region_layout)
        layout.addWidget(region_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.btn_backup = QPushButton("Start Backup")
        self.btn_backup.clicked.connect(self.start_backup)
        button_layout.addWidget(self.btn_backup)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)

        layout.addLayout(button_layout)

    def refresh_ports(self):
        """Refresh available serial ports"""
        self.port_combo.clear()
        ports = list(serial.tools.list_ports.comports())

        # On Linux, prioritize USB ports at the top of the list
        if platform.system() == "Linux":
            usb_ports = [p for p in ports if "USB" in p.device.upper() or "USB" in p.description.upper()]
            other_ports = [p for p in ports if p not in usb_ports]
            ports = usb_ports + other_ports

        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)

    def browse_file(self):
        """Browse for save file"""
        # Show only .bin for full backup, .4rdmf for selective backup
        if self.check_full.isChecked():
            file_filter = "Binary Files (*.bin);;All Files (*)"
        else:
            file_filter = "RT-4D Codeplug (*.4rdmf);;Binary Files (*.bin);;All Files (*)"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Backup",
            "",
            file_filter
        )
        if file_path:
            self.backup_file = Path(file_path)
            self.file_label.setText(self.backup_file.name)

    def on_full_backup_toggled(self, checked: bool):
        """Handle full backup toggle"""
        self.check_settings.setEnabled(not checked)
        self.check_channels.setEnabled(not checked)
        self.check_contacts.setEnabled(not checked)
        self.check_groups.setEnabled(not checked)
        self.check_encryption.setEnabled(not checked)
        self.check_zones.setEnabled(not checked)

    def start_backup(self):
        """Start backup operation"""
        if not self.backup_file:
            QMessageBox.warning(self, "Error", "Please select a file to save to")
            return

        port = self.port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "Error", "No serial port selected")
            return

        # Determine regions
        regions = None
        self.was_full_backup = self.check_full.isChecked()
        if not self.was_full_backup:
            regions = []
            if self.check_settings.isChecked():
                regions.append("main_settings")
            if self.check_channels.isChecked():
                regions.append("channels")
            if self.check_contacts.isChecked():
                regions.append("contacts")
            if self.check_groups.isChecked():
                regions.append("groups")
            if self.check_encryption.isChecked():
                regions.append("dmr_keys")
            if self.check_zones.isChecked():
                regions.append("zones")

        # Start worker thread
        self.worker = RadioWorker("backup", port, str(self.backup_file), regions)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_backup.setEnabled(False)
        self.status_label.setText("Connecting to radio...")

        self.worker.start()

    def on_progress(self, percent: int, message: str):
        """Handle progress update"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def on_finished(self, success: bool, message: str):
        """Handle completion"""
        self.progress_bar.setValue(100 if success else 0)
        self.status_label.setText(message)
        self.btn_backup.setEnabled(True)

        if success:
            QMessageBox.information(self, "Success", message)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", message)

    def get_backup_file(self) -> Optional[Path]:
        """Get the backup file path"""
        return self.backup_file

    def is_full_backup(self) -> bool:
        """Check if this was a full SPI backup"""
        return self.was_full_backup


class RadioFlashDialog(QDialog):
    """Dialog for flashing to radio"""

    def __init__(self, parent=None, codeplug: Optional[Codeplug] = None):
        super().__init__(parent)
        self.codeplug = codeplug
        self.worker: Optional[RadioWorker] = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Flash to Radio")
        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Warning
        warning = QLabel("⚠️ Warning: This will overwrite data on your radio!")
        warning.setStyleSheet("color: red; font-weight: bold;")
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

        # Region selection
        region_group = QGroupBox("Regions to Flash")
        region_layout = QVBoxLayout()

        # Beta41+ layout control
        self.check_beta41 = QCheckBox("Use Beta41+ Layout (REFW)")
        self.check_beta41.setToolTip(
            "Enable this to write channels in the REFW Beta41+ layout.\n"
            "Only enable if your radio has REFW Beta41 or newer custom firmware installed.\n"
            "WARNING: Stock firmware does NOT support this layout!"
        )
        # Initialize from codeplug settings - if beta41+, lock the checkbox
        is_beta41 = self.codeplug and self.codeplug.settings and self.codeplug.settings.beta41
        if is_beta41:
            self.check_beta41.setChecked(True)
            self.check_beta41.setEnabled(False)
        region_layout.addWidget(self.check_beta41)

        # Info label for Beta41+ warning
        if is_beta41:
            self.label_beta41_info = QLabel(
                "Beta41+ codeplug detected - layout option locked."
            )
            self.label_beta41_info.setStyleSheet("color: #008800; font-size: 10px;")
        else:
            self.label_beta41_info = QLabel(
                "ℹ️  REFW Beta41+ layout is incompatible with stock firmware."
            )
            self.label_beta41_info.setStyleSheet("color: #0066cc; font-size: 10px;")
        self.label_beta41_info.setWordWrap(True)
        region_layout.addWidget(self.label_beta41_info)

        # Spacing after beta41 section
        region_layout.addSpacing(10)

        self.check_settings = QCheckBox("Main Settings")
        self.check_settings.setChecked(True)
        region_layout.addWidget(self.check_settings)

        self.check_channels = QCheckBox("Channels")
        self.check_channels.setChecked(True)
        region_layout.addWidget(self.check_channels)

        self.check_contacts = QCheckBox("Contacts")
        self.check_contacts.setChecked(True)
        region_layout.addWidget(self.check_contacts)

        self.check_groups = QCheckBox("RX Groups (Group Lists)")
        self.check_groups.setChecked(True)
        region_layout.addWidget(self.check_groups)

        self.check_encryption = QCheckBox("Encryption Keys")
        self.check_encryption.setChecked(True)
        region_layout.addWidget(self.check_encryption)

        self.check_zones = QCheckBox("Zones")
        self.check_zones.setChecked(True)
        region_layout.addWidget(self.check_zones)

        region_group.setLayout(region_layout)
        layout.addWidget(region_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.btn_flash = QPushButton("Start Flashing")
        self.btn_flash.clicked.connect(self.start_flash)
        button_layout.addWidget(self.btn_flash)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)

        layout.addLayout(button_layout)

    def refresh_ports(self):
        """Refresh available serial ports"""
        self.port_combo.clear()
        ports = list(serial.tools.list_ports.comports())

        # On Linux, prioritize USB ports at the top of the list
        if platform.system() == "Linux":
            usb_ports = [p for p in ports if "USB" in p.device.upper() or "USB" in p.description.upper()]
            other_ports = [p for p in ports if p not in usb_ports]
            ports = usb_ports + other_ports

        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)

    def start_flash(self):
        """Start flash operation"""
        port = self.port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "Error", "No serial port selected")
            return

        # Confirm
        reply = QMessageBox.question(
            self,
            "Confirm Flash",
            "Are you sure you want to flash to the radio?\n\n"
            "This will overwrite the radio's configuration!",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Apply beta41 layout setting from checkbox
        if self.codeplug and self.codeplug.settings:
            self.codeplug.settings.beta41 = self.check_beta41.isChecked()

        # Determine regions
        regions = []
        if self.check_settings.isChecked():
            regions.append("main_settings")
        if self.check_channels.isChecked():
            regions.append("channels")
        if self.check_contacts.isChecked():
            regions.append("contacts")
        if self.check_groups.isChecked():
            regions.append("groups")
        if self.check_encryption.isChecked():
            regions.append("dmr_keys")
        if self.check_zones.isChecked():
            regions.append("zones")

        # Start worker thread
        self.worker = RadioWorker("flash", port, None, regions, self.codeplug)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_flash.setEnabled(False)
        self.status_label.setText("Connecting to radio...")

        self.worker.start()

    def on_progress(self, percent: int, message: str):
        """Handle progress update"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def on_finished(self, success: bool, message: str):
        """Handle completion"""
        self.progress_bar.setValue(100 if success else 0)
        self.status_label.setText(message)
        self.btn_flash.setEnabled(True)

        if success:
            QMessageBox.information(self, "Success", message)
            self.accept()
        else:
            QMessageBox.critical(self, "Error", message)
