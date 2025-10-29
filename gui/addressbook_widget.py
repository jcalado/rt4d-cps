"""Address Book Widget - DMR User Database Manager"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox, QLabel, QLineEdit,
    QProgressDialog, QHeaderView, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from rt4d_codeplug.global_contacts import GlobalContactDatabase, GlobalContactCSVParser


class ImportWorker(QThread):
    """Background thread for importing CSV"""

    progress_update = Signal(str)  # Status message
    import_complete = Signal(object, str)  # database, message (None if error)

    def __init__(self, filename, max_contacts):
        super().__init__()
        self.filename = filename
        self.max_contacts = max_contacts

    def run(self):
        """Import CSV in background thread"""
        try:
            self.progress_update.emit("Parsing CSV file...")
            new_db = GlobalContactCSVParser.parse_csv(self.filename, max_contacts=self.max_contacts)

            if len(new_db) == 0:
                self.import_complete.emit(None, "No valid contacts found in CSV file.")
                return

            self.progress_update.emit(f"Sorting {len(new_db):,} contacts...")
            # Database is already sorted by parser

            self.import_complete.emit(new_db, f"Successfully imported {len(new_db):,} contacts!")

        except Exception as e:
            self.import_complete.emit(None, f"Import failed: {str(e)}")


class SearchWorker(QThread):
    """Background thread for searching contacts"""

    search_complete = Signal(list)  # Emits list of matching contacts

    def __init__(self, database, search_term, max_results):
        super().__init__()
        self.database = database
        self.search_term = search_term.lower()
        self.max_results = max_results
        self._cancelled = False

    def run(self):
        """Perform search in background thread"""
        matches = []

        for contact in self.database.contacts:
            if self._cancelled:
                return

            if contact.matches_search(self.search_term):
                matches.append(contact)

                if len(matches) >= self.max_results:
                    break

        if not self._cancelled:
            self.search_complete.emit(matches)

    def cancel(self):
        """Cancel the search"""
        self._cancelled = True


class AddressBookWidget(QWidget):
    """Widget for managing global DMR contacts (Address Book)"""

    # Signal emitted when address book is modified
    modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.database = GlobalContactDatabase()
        self.filtered_contacts = []  # For search results
        self.max_display_results = 1000  # Limit displayed results for performance

        # Search worker thread
        self.search_worker = None

        # Table population state
        self._populating = False
        self._populate_contacts = []
        self._populate_index = 0
        self._base_stats_text = "Contacts: 0"

        # Search debounce timer (wait 1s after user stops typing)
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(1000)  # 1 second
        self.search_timer.timeout.connect(self.perform_search)

        self.init_ui()

    def init_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)

        # Title and info
        title = QLabel("<b>Address Book - Global DMR Contacts</b>")
        layout.addWidget(title)

        info = QLabel(
            "Import DMR user databases (CSV) for caller ID lookup. "
            "The address book can be written directly to the radio."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by DMR ID, callsign, or name...")
        self.search_input.textChanged.connect(self.on_search)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Statistics
        self.stats_label = QLabel("Contacts: 0")
        layout.addWidget(self.stats_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "DMR ID", "Callsign", "Name", "City", "State", "Country", "Remarks"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()

        self.import_btn = QPushButton("Import CSV...")
        self.import_btn.clicked.connect(self.on_import_csv)
        button_layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export CSV...")
        self.export_btn.clicked.connect(self.on_export_csv)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.on_clear)
        self.clear_btn.setEnabled(False)
        button_layout.addWidget(self.clear_btn)

        button_layout.addStretch()

        self.write_radio_btn = QPushButton("Write to Radio...")
        self.write_radio_btn.clicked.connect(self.on_write_to_radio)
        self.write_radio_btn.setEnabled(False)
        self.write_radio_btn.setStyleSheet("font-weight: bold;")
        button_layout.addWidget(self.write_radio_btn)

        layout.addLayout(button_layout)

    def on_import_csv(self):
        """Import DMR user database from CSV"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import DMR User Database",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not filename:
            return

        # Disable import button during import
        self.import_btn.setEnabled(False)

        # Show progress dialog
        self.import_progress = QProgressDialog("Starting import...", None, 0, 0, self)
        self.import_progress.setWindowTitle("Importing Contacts")
        self.import_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.import_progress.setMinimumDuration(0)  # Show immediately
        self.import_progress.setCancelButton(None)  # No cancel during import
        self.import_progress.show()
        QApplication.processEvents()

        # Start import in background thread
        MAX_CONTACTS = 100000
        self.import_worker = ImportWorker(filename, MAX_CONTACTS)
        self.import_worker.progress_update.connect(self.on_import_progress)
        self.import_worker.import_complete.connect(self.on_import_complete)
        self.import_worker.start()

    def on_import_progress(self, message):
        """Update import progress"""
        self.import_progress.setLabelText(message)
        QApplication.processEvents()

    def on_import_complete(self, new_db, message):
        """Handle import completion"""
        self.import_progress.close()
        self.import_btn.setEnabled(True)

        if new_db is None:
            # Import failed
            QMessageBox.warning(self, "Import Failed", message)
            return

        # Ask confirmation for large databases
        if len(new_db) > 10000:
            reply = QMessageBox.question(
                self,
                "Large Database",
                f"Import {len(new_db):,} contacts? This will replace current address book.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Replace database
        self.database = new_db
        self.filtered_contacts = []
        self.search_input.clear()

        # Show completion message
        QMessageBox.information(self, "Import Successful", message)

        # Refresh table (this will show progress as it populates)
        self.refresh_table()
        self.modified.emit()

    def on_export_csv(self):
        """Export address book to CSV"""
        if len(self.database) == 0:
            QMessageBox.warning(self, "Export", "No contacts to export.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Address Book",
            "addressbook.csv",
            "CSV Files (*.csv)"
        )

        if not filename:
            return

        try:
            GlobalContactCSVParser.export_csv(self.database, filename)
            QMessageBox.information(
                self,
                "Export Successful",
                f"Exported {len(self.database):,} contacts to:\n{filename}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export CSV:\n{str(e)}"
            )

    def on_clear(self):
        """Clear all contacts"""
        reply = QMessageBox.question(
            self,
            "Clear Address Book",
            f"Delete all {len(self.database):,} contacts?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.database.clear()
            self.filtered_contacts = []
            self.search_input.clear()
            self.refresh_table()
            self.modified.emit()

    def on_search(self, text: str):
        """Triggered on every keystroke - restart debounce timer"""
        # Restart the timer on every keystroke
        # The actual search will happen 1 second after user stops typing
        self.search_timer.stop()
        self.search_timer.start()

    def perform_search(self):
        """Perform the actual search (called after 1s delay)"""
        text = self.search_input.text().strip()

        if not text:
            # Clear filter
            self.filtered_contacts = []
            self.refresh_table()
            return

        # Cancel any existing search
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.cancel()
            self.search_worker.wait()

        # Show searching indicator
        self.stats_label.setText("Searching...")
        QApplication.processEvents()  # Update UI immediately

        # Start background search
        self.search_worker = SearchWorker(self.database, text, self.max_display_results)
        self.search_worker.search_complete.connect(self.on_search_complete)
        self.search_worker.start()

    def on_search_complete(self, matches):
        """Handle search results from background thread"""
        self.filtered_contacts = matches
        self.refresh_table()

    def refresh_table(self):
        """Refresh table with current contacts"""
        # Cancel any ongoing population
        self._populating = False

        # Determine which contacts to show
        if self.filtered_contacts:
            contacts = self.filtered_contacts
        else:
            # Limit initial display for performance
            contacts = self.database.contacts[:self.max_display_results]

        # Update stats - save the base text
        total = len(self.database)
        filtered_total = len(self.filtered_contacts) if self.filtered_contacts else total
        shown = len(contacts)

        if self.filtered_contacts:
            if len(self.filtered_contacts) >= self.max_display_results:
                self._base_stats_text = f"Showing {shown:,} of {filtered_total:,}+ matches (limited for performance)"
            else:
                self._base_stats_text = f"Showing {shown:,} of {total:,} contacts"
        else:
            if total > self.max_display_results:
                self._base_stats_text = f"Showing {shown:,} of {total:,} contacts (use search to find more)"
            else:
                self._base_stats_text = f"Contacts: {total:,}"

        self.stats_label.setText(self._base_stats_text)

        # Update buttons
        has_contacts = total > 0
        self.export_btn.setEnabled(has_contacts)
        self.clear_btn.setEnabled(has_contacts)
        self.write_radio_btn.setEnabled(has_contacts)

        # Prepare for chunked population
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(shown)

        # Start chunked population
        self._populate_contacts = contacts
        self._populate_index = 0
        self._populating = True
        self._populate_chunk()

    def _populate_chunk(self):
        """Populate table in chunks to keep UI responsive"""
        if not self._populating:
            return

        CHUNK_SIZE = 250  # Populate 250 rows at a time (increased for better performance)
        start_idx = self._populate_index
        end_idx = min(start_idx + CHUNK_SIZE, len(self._populate_contacts))

        # Populate this chunk
        for row in range(start_idx, end_idx):
            contact = self._populate_contacts[row]

            # DMR ID
            item = QTableWidgetItem(str(contact.dmr_id))
            item.setData(Qt.ItemDataRole.UserRole, contact.dmr_id)
            self.table.setItem(row, 0, item)

            # Other fields
            self.table.setItem(row, 1, QTableWidgetItem(contact.callsign))
            self.table.setItem(row, 2, QTableWidgetItem(contact.name))
            self.table.setItem(row, 3, QTableWidgetItem(contact.city))
            self.table.setItem(row, 4, QTableWidgetItem(contact.state))
            self.table.setItem(row, 5, QTableWidgetItem(contact.country))
            self.table.setItem(row, 6, QTableWidgetItem(contact.remarks))

        self._populate_index = end_idx

        # Check if done
        if self._populate_index >= len(self._populate_contacts):
            # Finished - re-enable sorting and signals
            self.table.setSortingEnabled(True)
            self.table.blockSignals(False)
            self._populating = False
            # Restore base stats text
            self.stats_label.setText(self._base_stats_text)
        else:
            # Update progress - REPLACE text, don't append!
            progress = int((self._populate_index / len(self._populate_contacts)) * 100)
            self.stats_label.setText(f"{self._base_stats_text} - Loading {progress}%")
            # Schedule next chunk after yielding to event loop
            QTimer.singleShot(0, self._populate_chunk)

    def on_write_to_radio(self):
        """Write address book to radio via UART"""
        if len(self.database) == 0:
            QMessageBox.warning(self, "Write to Radio", "No contacts to write.")
            return

        # Import here to avoid circular dependencies
        from .radio_addressbook_dialog import RadioAddressBookDialog

        dialog = RadioAddressBookDialog(self, self.database)
        dialog.exec()

    def get_database(self) -> GlobalContactDatabase:
        """Get current database"""
        return self.database

    def set_database(self, database: GlobalContactDatabase):
        """Set database and refresh display"""
        self.database = database
        self.filtered_contacts = []
        self.search_input.clear()
        self.refresh_table()
