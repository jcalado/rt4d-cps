"""Main Window for RT-4D Editor GUI"""

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QFileDialog, QMessageBox, QStatusBar, QToolBar, QStyle
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt, QSize

from rt4d_codeplug import Codeplug, CodeplugParser, CodeplugSerializer
from .channel_table import ChannelTableWidget
from .contact_widget import ContactWidget
from .grouplist_widget import GroupListWidget
from .zone_widget import ZoneWidget
from .encryption_widget import EncryptionWidget
from .dtmf_widget import DTMFWidget
from .settings_dialog import SettingsWidget
from .addressbook_widget import AddressBookWidget


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.codeplug: Optional[Codeplug] = None
        self.current_file: Optional[Path] = None
        self.modified = False

        self.init_ui()
        self.update_title()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("RT-4D Editor")
        self.setGeometry(100, 100, 1000, 700)

        # Create menu bar
        self.create_menus()

        # Create toolbar
        self.create_toolbar()

        # Create tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Channel tab
        self.channel_widget = ChannelTableWidget()
        self.channel_widget.data_modified.connect(self.on_data_modified)
        self.tabs.addTab(self.channel_widget, "Channels")

        # Contacts tab
        self.contact_widget = ContactWidget()
        self.contact_widget.data_modified.connect(self.on_data_modified)
        self.contact_widget.data_modified.connect(self.on_contacts_modified)
        self.tabs.addTab(self.contact_widget, "Contacts")

        # Group Lists tab
        self.grouplist_widget = GroupListWidget()
        self.grouplist_widget.data_modified.connect(self.on_data_modified)
        self.grouplist_widget.data_modified.connect(self.on_grouplists_modified)
        self.tabs.addTab(self.grouplist_widget, "Group Lists")

        # Zones tab
        self.zone_widget = ZoneWidget()
        self.zone_widget.data_modified.connect(self.on_data_modified)
        self.tabs.addTab(self.zone_widget, "Zones")

        # Encryption tab
        self.encryption_widget = EncryptionWidget()
        self.encryption_widget.data_modified.connect(self.on_data_modified)
        self.encryption_widget.data_modified.connect(self.on_encryption_modified)
        self.tabs.addTab(self.encryption_widget, "Encryption")

        # DTMF tab
        self.dtmf_widget = DTMFWidget()
        self.dtmf_widget.settings_changed.connect(self.on_data_modified)
        self.tabs.addTab(self.dtmf_widget, "DTMF")

        # Address Book tab
        self.addressbook_widget = AddressBookWidget()
        self.addressbook_widget.modified.connect(self.on_data_modified)
        self.tabs.addTab(self.addressbook_widget, "Address Book")

        # Settings tab
        self.settings_widget = SettingsWidget()
        self.settings_widget.data_modified.connect(self.on_data_modified)
        self.tabs.addTab(self.settings_widget, "Settings")

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("No file loaded")

    def create_menus(self):
        """Create menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        # Open action with icon
        self.action_open = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
            "&Open...", self
        )
        self.action_open.setShortcut("Ctrl+O")
        self.action_open.setToolTip("Open codeplug file (Ctrl+O)")
        self.action_open.setStatusTip("Open a .4rdmf codeplug file")
        self.action_open.triggered.connect(self.open_file)
        file_menu.addAction(self.action_open)

        # Save action with icon
        self.action_save = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
            "&Save", self
        )
        self.action_save.setShortcut("Ctrl+S")
        self.action_save.setToolTip("Save codeplug file (Ctrl+S)")
        self.action_save.setStatusTip("Save changes to the current file")
        self.action_save.setEnabled(False)
        self.action_save.triggered.connect(self.save_file)
        file_menu.addAction(self.action_save)

        self.action_save_as = QAction("Save &As...", self)
        self.action_save_as.setShortcut("Ctrl+Shift+S")
        self.action_save_as.setEnabled(False)
        self.action_save_as.triggered.connect(self.save_file_as)
        file_menu.addAction(self.action_save_as)

        file_menu.addSeparator()

        self.action_import_csv = QAction("&Import CSV...", self)
        self.action_import_csv.setEnabled(False)
        self.action_import_csv.triggered.connect(self.import_csv)
        file_menu.addAction(self.action_import_csv)

        self.action_export_csv = QAction("&Export CSV...", self)
        self.action_export_csv.setEnabled(False)
        self.action_export_csv.triggered.connect(self.export_csv)
        file_menu.addAction(self.action_export_csv)

        file_menu.addSeparator()

        self.action_exit = QAction("E&xit", self)
        self.action_exit.setShortcut("Ctrl+Q")
        self.action_exit.triggered.connect(self.close)
        file_menu.addAction(self.action_exit)

        # Radio menu
        radio_menu = menubar.addMenu("&Radio")

        # Backup action with icon (using download/save icon)
        self.action_backup = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown),
            "&Read from radio...", self
        )
        self.action_backup.setToolTip("Read codeplug from radio")
        self.action_backup.setStatusTip("Read codeplug data from connected radio via serial")
        self.action_backup.triggered.connect(self.backup_from_radio)
        radio_menu.addAction(self.action_backup)

        # Flash action with icon (using upload/apply icon)
        self.action_flash = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp),
            "&Write to Radio...", self
        )
        self.action_flash.setToolTip("Flash codeplug to radio")
        self.action_flash.setStatusTip("Write codeplug data to connected radio via serial")
        self.action_flash.setEnabled(False)
        self.action_flash.triggered.connect(self.flash_to_radio)
        radio_menu.addAction(self.action_flash)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        self.action_about = QAction("&About", self)
        self.action_about.triggered.connect(self.show_about)
        help_menu.addAction(self.action_about)

    def create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # Set larger icon size for better visibility
        icon_size = QSize(24, 24)
        toolbar.setIconSize(icon_size)

        self.addToolBar(toolbar)

        # File operations
        toolbar.addAction(self.action_open)
        toolbar.addAction(self.action_save)

        # Separator with some spacing
        toolbar.addSeparator()

        # Radio operations
        toolbar.addAction(self.action_backup)
        toolbar.addAction(self.action_flash)

    def open_file(self):
        """Open a .4rdmf file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Codeplug File",
            "",
            "RT-4D Codeplug (*.4rdmf);;All Files (*)"
        )

        if not file_path:
            return

        try:
            self.status_bar.showMessage(f"Loading {file_path}...")
            parser = CodeplugParser.from_file(file_path)
            self.codeplug = parser.parse()
            self.current_file = Path(file_path)
            self.modified = False

            # Update UI with loaded data
            self.channel_widget.load_codeplug(self.codeplug)
            self.contact_widget.load_codeplug(self.codeplug)
            self.grouplist_widget.load_codeplug(self.codeplug)
            self.zone_widget.load_codeplug(self.codeplug)
            self.encryption_widget.load_codeplug(self.codeplug)
            self.dtmf_widget.load_settings(self.codeplug.settings)
            self.settings_widget.load_settings(self.codeplug.settings)

            self.update_title()
            self.enable_actions(True)
            self.status_bar.showMessage(f"Loaded {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")
            self.status_bar.showMessage("Failed to load file")

    def save_file(self):
        """Save to current file"""
        if not self.current_file:
            self.save_file_as()
            return

        try:
            self.save_to_file(self.current_file)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")

    def save_file_as(self):
        """Save to a new file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Codeplug File",
            "",
            "RT-4D Codeplug (*.4rdmf);;All Files (*)"
        )

        if not file_path:
            return

        try:
            self.save_to_file(Path(file_path))
            self.current_file = Path(file_path)
            self.update_title()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")

    def save_to_file(self, file_path: Path):
        """Save codeplug to file"""
        self.status_bar.showMessage(f"Saving {file_path}...")

        # Get updated data from UI
        self.channel_widget.save_to_codeplug(self.codeplug)

        # Serialize and write
        data = CodeplugSerializer.serialize(self.codeplug)
        with open(file_path, 'wb') as f:
            f.write(data)

        self.modified = False
        self.update_title()
        self.status_bar.showMessage(f"Saved {file_path}")

    def import_csv(self):
        """Import channels from CSV"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            self.channel_widget.import_csv(file_path)
            self.on_data_modified()
            QMessageBox.information(self, "Success", "CSV imported successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import CSV:\n{e}")

    def export_csv(self):
        """Export channels to CSV"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            self.channel_widget.export_csv(file_path)
            QMessageBox.information(self, "Success", f"Exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export CSV:\n{e}")

    def backup_from_radio(self):
        """Backup codeplug from radio"""
        from .radio_dialog import RadioBackupDialog
        dialog = RadioBackupDialog(self)
        if dialog.exec():
            # If successful, load the backed up file (only for selective backups)
            file_path = dialog.get_backup_file()
            if file_path:
                # Don't try to load full SPI backups - they're raw binary dumps
                if dialog.is_full_backup():
                    self.status_bar.showMessage(f"Full SPI backup saved to {file_path.name}")
                else:
                    # Load selective backup as codeplug
                    parser = CodeplugParser.from_file(str(file_path))
                    self.codeplug = parser.parse()
                    self.current_file = file_path
                    self.modified = False
                    self.channel_widget.load_codeplug(self.codeplug)
                    self.contact_widget.load_codeplug(self.codeplug)
                    self.grouplist_widget.load_codeplug(self.codeplug)
                    self.zone_widget.load_codeplug(self.codeplug)
                    self.encryption_widget.load_codeplug(self.codeplug)
                    self.dtmf_widget.load_settings(self.codeplug.settings)
                    self.settings_widget.load_settings(self.codeplug.settings)
                    self.update_title()
                    self.enable_actions(True)
                    self.status_bar.showMessage(f"Loaded backup from radio")

    def flash_to_radio(self):
        """Flash codeplug to radio"""
        if not self.codeplug:
            QMessageBox.warning(self, "Warning", "No codeplug loaded")
            return

        # Save current UI state to codeplug
        self.channel_widget.save_to_codeplug(self.codeplug)

        from .radio_dialog import RadioFlashDialog
        dialog = RadioFlashDialog(self, self.codeplug)
        dialog.exec()

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About RT-4D Editor",
            "RT-4D Channel Editor & Flasher\n\n"
            "A desktop application for editing RT-4D radio codeplug files.\n\n"
            "Brought to you by: CS7BLE / Joel Calado\n"
            "https://www.jcalado.com"
        )

    def on_data_modified(self):
        """Handle data modification"""
        self.modified = True
        self.update_title()

    def on_contacts_modified(self):
        """Handle contacts modification - refresh channel dropdown"""
        self.channel_widget.populate_contact_dropdown()
        # Reload currently displayed channel to sync dropdown selection
        self.channel_widget.reload_current_channel_details()

    def on_grouplists_modified(self):
        """Handle group lists modification - refresh channel dropdown"""
        self.channel_widget.populate_group_list_dropdown()
        # Reload currently displayed channel to sync dropdown selection
        self.channel_widget.reload_current_channel_details()

    def on_encryption_modified(self):
        """Handle encryption keys modification - refresh channel dropdown"""
        self.channel_widget.populate_encryption_dropdown()
        # Reload currently displayed channel to sync dropdown selection
        self.channel_widget.reload_current_channel_details()

    def update_title(self):
        """Update window title"""
        title = "RT-4D Editor"
        if self.current_file:
            title += f" - {self.current_file.name}"
        if self.modified:
            title += " *"
        self.setWindowTitle(title)

    def enable_actions(self, enabled: bool):
        """Enable/disable actions that require a loaded codeplug"""
        self.action_save.setEnabled(enabled)
        self.action_save_as.setEnabled(enabled)
        self.action_import_csv.setEnabled(enabled)
        self.action_export_csv.setEnabled(enabled)
        self.action_flash.setEnabled(enabled)

    def closeEvent(self, event):
        """Handle window close"""
        if self.modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )

            if reply == QMessageBox.Save:
                self.save_file()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
