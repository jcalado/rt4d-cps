"""Address Book Widget - DMR User Database Manager"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableView,
    QTableWidgetItem, QFileDialog, QMessageBox, QLabel, QLineEdit,
    QProgressDialog, QHeaderView, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QAbstractTableModel, QModelIndex
from rt4d_codeplug.global_contacts import GlobalContactDatabase, GlobalContactCSVParser


class ContactTableModel(QAbstractTableModel):
    """Table model for displaying contacts with virtual scrolling and pagination

    This model provides:
    - Virtual scrolling (only visible rows are rendered)
    - Pagination support (load more contacts on demand)
    - Efficient sorting without widget overhead
    - Memory efficient display of 100k+ contacts
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._contacts = []
        self._displayed_count = 0  # Number of contacts currently shown (for pagination)
        self._headers = ["DMR ID", "Callsign", "Name", "City", "State", "Country", "Remarks"]

    def set_contacts(self, contacts, initial_count=1000):
        """Set contacts to display with optional initial count limit

        Args:
            contacts: List of GlobalContact objects to display
            initial_count: Initial number of contacts to show (for pagination)
        """
        self.beginResetModel()
        self._contacts = contacts
        self._displayed_count = min(len(contacts), initial_count)
        self.endResetModel()

    def load_more(self, count=1000):
        """Load more contacts for pagination

        Args:
            count: Number of additional contacts to load

        Returns:
            True if more contacts were loaded, False if no more available
        """
        if self._displayed_count >= len(self._contacts):
            return False  # No more to load

        old_count = self._displayed_count
        new_count = min(len(self._contacts), self._displayed_count + count)

        if new_count > old_count:
            self.beginInsertRows(QModelIndex(), old_count, new_count - 1)
            self._displayed_count = new_count
            self.endInsertRows()
            return True
        return False

    def has_more(self):
        """Check if more contacts are available to load"""
        return self._displayed_count < len(self._contacts)

    def total_contacts(self):
        """Get total number of contacts (including not yet displayed)"""
        return len(self._contacts)

    def rowCount(self, parent=QModelIndex()):
        """Return number of rows (contacts) currently displayed"""
        return self._displayed_count if not parent.isValid() else 0

    def columnCount(self, parent=QModelIndex()):
        """Return number of columns"""
        return 7 if not parent.isValid() else 0

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return data for a specific cell

        Args:
            index: QModelIndex for the cell
            role: Qt role (DisplayRole, UserRole, etc.)

        Returns:
            Data for the cell, or None if invalid
        """
        if not index.isValid() or index.row() >= self._displayed_count:
            return None

        contact = self._contacts[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(contact.dmr_id)
            elif col == 1:
                return contact.callsign
            elif col == 2:
                return contact.name
            elif col == 3:
                return contact.city
            elif col == 4:
                return contact.state
            elif col == 5:
                return contact.country
            elif col == 6:
                return contact.remarks
        elif role == Qt.ItemDataRole.UserRole:
            # Store DMR ID for programmatic access
            if col == 0:
                return contact.dmr_id

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        """Return header labels

        Args:
            section: Column or row number
            orientation: Horizontal or Vertical
            role: Qt role

        Returns:
            Header text for the section
        """
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal and section < len(self._headers):
                return self._headers[section]
        return None

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        """Sort contacts by column

        Args:
            column: Column index to sort by
            order: Ascending or Descending
        """
        if not self._contacts:
            return

        self.layoutAboutToBeChanged.emit()

        reverse = (order == Qt.SortOrder.DescendingOrder)

        # Sort based on column
        if column == 0:  # DMR ID
            self._contacts.sort(key=lambda c: c.dmr_id, reverse=reverse)
        elif column == 1:  # Callsign
            self._contacts.sort(key=lambda c: c.callsign.lower(), reverse=reverse)
        elif column == 2:  # Name
            self._contacts.sort(key=lambda c: c.name.lower(), reverse=reverse)
        elif column == 3:  # City
            self._contacts.sort(key=lambda c: c.city.lower(), reverse=reverse)
        elif column == 4:  # State
            self._contacts.sort(key=lambda c: c.state.lower(), reverse=reverse)
        elif column == 5:  # Country
            self._contacts.sort(key=lambda c: c.country.lower(), reverse=reverse)
        elif column == 6:  # Remarks
            self._contacts.sort(key=lambda c: c.remarks.lower(), reverse=reverse)

        self.layoutChanged.emit()


class ImportWorker(QThread):
    """Background thread for importing CSV"""

    progress_update = Signal(str)  # Status message
    progress_numeric = Signal(int, int)  # (current, total) for progress bar
    import_complete = Signal(object, str)  # database, message (None if error)

    def __init__(self, filename, max_contacts):
        super().__init__()
        self.filename = filename
        self.max_contacts = max_contacts
        self.estimated_total = 0

    def run(self):
        """Import CSV in background thread with deferred index building for performance"""
        try:
            # Count lines in file for progress estimation
            self.progress_update.emit("Counting rows...")
            try:
                with open(self.filename, 'r', encoding='utf-8-sig', errors='ignore') as f:
                    # Skip header and count data rows
                    self.estimated_total = sum(1 for line in f) - 1
                    if self.estimated_total < 0:
                        self.estimated_total = 0
            except Exception:
                # If counting fails, use 0 (will fall back to indeterminate)
                self.estimated_total = 0

            # Define progress callback with protection against widget deletion
            def progress_callback(current, total):
                try:
                    # Check if progress dialog still exists and wasn't cancelled
                    if hasattr(self, 'import_progress') and self.import_progress:
                        self.progress_numeric.emit(current, total)
                        # Cap progress at total to avoid >100%
                        if current <= total:
                            self.progress_update.emit(f"Importing contacts... ({current:,} / ~{total:,})")
                except (RuntimeError, AttributeError):
                    # Widget deleted or signal disconnected - stop reporting progress
                    pass

            # Define status callback for phase updates
            def status_callback(message):
                try:
                    if hasattr(self, 'import_progress') and self.import_progress:
                        self.progress_update.emit(message)
                except (RuntimeError, AttributeError):
                    pass

            # Note: parse_csv does 3 phases internally:
            # 1. Parse CSV rows (fast)
            # 2. Build search index (slower, but optimized with deferred building)
            # 3. Sort contacts (fast)
            self.progress_update.emit("Parsing CSV rows...")
            new_db = GlobalContactCSVParser.parse_csv(
                self.filename,
                max_contacts=self.max_contacts,
                progress_callback=progress_callback if self.estimated_total > 0 else None,
                estimated_total=self.estimated_total if self.estimated_total > 0 else None,
                status_callback=status_callback
            )

            if len(new_db) == 0:
                self.import_complete.emit(None, "No valid contacts found in CSV file.")
                return

            self.import_complete.emit(new_db, f"Successfully imported {len(new_db):,} contacts!")

        except Exception as e:
            self.import_complete.emit(None, f"Import failed: {str(e)}")


class SearchWorker(QThread):
    """Background thread for searching contacts using indexed search"""

    search_complete = Signal(list)  # Emits list of matching contacts

    def __init__(self, database, search_term):
        super().__init__()
        self.database = database
        self.search_term = search_term.lower()
        self._cancelled = False

    def run(self):
        """Perform search in background thread using indexed search"""
        if self._cancelled:
            return

        # Use indexed search (trie + hash map) - much faster than linear scan
        # Performance: O(m + k) where m=query length, k=results vs O(n) for linear scan
        # Returns ALL matches - pagination is handled by ContactTableModel
        matches = self.database.search(self.search_term)

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

        # Table model for virtual scrolling and pagination
        self.table_model = ContactTableModel(self)

        # Search worker thread
        self.search_worker = None

        # Search debounce timer (wait 200ms after user stops typing)
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(200)  # 200ms - reduced due to faster indexed search
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

        # Table with virtual scrolling (QTableView + Model)
        self.table = QTableView()
        self.table.setModel(self.table_model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
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

        self.load_more_btn = QPushButton("Load More Results...")
        self.load_more_btn.clicked.connect(self.on_load_more)
        self.load_more_btn.setEnabled(False)
        self.load_more_btn.setVisible(False)  # Hidden by default
        button_layout.addWidget(self.load_more_btn)

        button_layout.addStretch()

        self.write_radio_btn = QPushButton("Write to Radio...")
        self.write_radio_btn.clicked.connect(self.on_write_to_radio)
        # Always enabled to allow clearing radio address book when empty
        self.write_radio_btn.setEnabled(True)
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

        # Show progress dialog (initially determinate, will show percentage)
        self.import_progress = QProgressDialog("Starting import...", None, 0, 100, self)
        self.import_progress.setWindowTitle("Importing Contacts")
        self.import_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.import_progress.setMinimumDuration(0)  # Show immediately
        self.import_progress.setCancelButton(None)  # No cancel during import
        self.import_progress.setValue(0)
        self.import_progress.show()
        QApplication.processEvents()

        # Start import in background thread
        MAX_CONTACTS = 500000
        self.import_worker = ImportWorker(filename, MAX_CONTACTS)
        self.import_worker.progress_update.connect(self.on_import_progress)
        self.import_worker.progress_numeric.connect(self.on_import_progress_numeric)
        self.import_worker.import_complete.connect(self.on_import_complete)
        self.import_worker.start()

    def on_import_progress(self, message):
        """Update import progress text"""
        self.import_progress.setLabelText(message)
        # Note: No processEvents() - Qt signals already handle thread-safe updates

    def on_import_progress_numeric(self, current, total):
        """Update import progress bar with numeric progress"""
        if total > 0:
            # Calculate percentage, cap at 100% to avoid >100% display
            percentage = min(100, int((current / total) * 100))
            self.import_progress.setValue(percentage)
            # Note: No processEvents() - prevents re-entrancy issues with frequent updates

    def on_import_complete(self, new_db, message):
        """Handle import completion"""
        # Ensure thread is fully finished before ANY GUI operations
        if hasattr(self, 'import_worker') and self.import_worker:
            self.import_worker.wait(2000)  # Wait up to 2 seconds for cleanup

        self.import_progress.close()

        # Use QTimer to defer dialog display (let event loop settle)
        # This prevents Qt event loop corruption from showing modal dialogs
        # while thread cleanup is still happening
        QTimer.singleShot(100, lambda: self._complete_import_ui(new_db, message))

    def _complete_import_ui(self, new_db, message):
        """Deferred UI updates after thread fully exits (prevents crashes)"""
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
        # Note: No processEvents() needed - Qt handles this automatically

        # Start background search (returns all matches - pagination handled by model)
        self.search_worker = SearchWorker(self.database, text)
        self.search_worker.search_complete.connect(self.on_search_complete)
        self.search_worker.start()

    def on_search_complete(self, matches):
        """Handle search results from background thread"""
        self.filtered_contacts = matches
        self.refresh_table()

    def refresh_table(self):
        """Refresh table with current contacts using model (instant with virtual scrolling)"""
        # Determine which contacts to show
        if self.filtered_contacts:
            contacts = self.filtered_contacts
        else:
            contacts = self.database.contacts

        # Set contacts in model (with initial pagination limit of 1000)
        # This is INSTANT due to virtual scrolling - only visible rows are rendered
        self.table_model.set_contacts(contacts, initial_count=1000)

        # Update stats
        total = len(self.database)
        displayed = self.table_model.rowCount()
        total_available = self.table_model.total_contacts()

        # Update stats label with pagination info
        if self.filtered_contacts:
            if displayed < total_available:
                self.stats_label.setText(
                    f"Showing {displayed:,} of {total_available:,} matches "
                    f"(out of {total:,} total contacts)"
                )
            else:
                self.stats_label.setText(f"Showing all {total_available:,} matches (out of {total:,} total contacts)")
        else:
            if displayed < total:
                self.stats_label.setText(f"Showing {displayed:,} of {total:,} contacts")
            else:
                self.stats_label.setText(f"Contacts: {total:,}")

        # Show/hide Load More button based on pagination state
        if self.table_model.has_more():
            self.load_more_btn.setVisible(True)
            self.load_more_btn.setEnabled(True)
            remaining = total_available - displayed
            self.load_more_btn.setText(f"Load More ({remaining:,} remaining)...")
        else:
            self.load_more_btn.setVisible(False)

        # Update other buttons
        has_contacts = total > 0
        self.export_btn.setEnabled(has_contacts)
        self.clear_btn.setEnabled(has_contacts)
        # Always enable write button to allow clearing radio address book
        self.write_radio_btn.setEnabled(True)

    def on_load_more(self):
        """Load more contacts for pagination"""
        # Load next batch of 1000 contacts
        if self.table_model.load_more(count=1000):
            # Update stats
            displayed = self.table_model.rowCount()
            total_available = self.table_model.total_contacts()
            total = len(self.database)

            # Update stats label
            if self.filtered_contacts:
                if displayed < total_available:
                    self.stats_label.setText(
                        f"Showing {displayed:,} of {total_available:,} matches "
                        f"(out of {total:,} total contacts)"
                    )
                else:
                    self.stats_label.setText(f"Showing all {total_available:,} matches (out of {total:,} total contacts)")
            else:
                if displayed < total:
                    self.stats_label.setText(f"Showing {displayed:,} of {total:,} contacts")
                else:
                    self.stats_label.setText(f"Contacts: {total:,}")

            # Update Load More button
            if self.table_model.has_more():
                remaining = total_available - displayed
                self.load_more_btn.setText(f"Load More ({remaining:,} remaining)...")
            else:
                self.load_more_btn.setVisible(False)

    def on_write_to_radio(self):
        """Write address book to radio via UART"""
        if len(self.database) == 0:
            reply = QMessageBox.question(
                self,
                "Clear Radio Address Book",
                "No contacts loaded. Do you want to clear the address book on the radio?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
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
