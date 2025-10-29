"""RT-4D Global Contacts / Address Book

The Address Book is a separate database from the codeplug that can be uploaded
to the radio via UART. It stores DMR user information for caller ID lookup.
"""

from dataclasses import dataclass
from typing import List, Optional
import csv


@dataclass
class GlobalContact:
    """Global contact entry for address book"""
    dmr_id: int
    callsign: str = ""
    name: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    remarks: str = ""

    def __post_init__(self):
        """Validate global contact data"""
        if self.dmr_id < 0 or self.dmr_id > 16777215:  # 24-bit max
            raise ValueError(f"Invalid DMR ID: {self.dmr_id}")

        # Truncate fields to reasonable lengths
        self.callsign = self.callsign[:16]
        self.name = self.name[:16]
        self.city = self.city[:15]
        self.state = self.state[:16]
        self.country = self.country[:16]
        self.remarks = self.remarks[:16]

        # Pre-compute search strings (performance optimization)
        self._search_string = self._build_search_string()

    def _build_search_string(self) -> str:
        """Build pre-computed lowercase search string"""
        return f"{self.dmr_id}|{self.callsign.lower()}|{self.name.lower()}".lower()

    def matches_search(self, search_term: str) -> bool:
        """Fast search check using pre-computed string"""
        return search_term in self._search_string

    def to_display_string(self) -> str:
        """Format contact for display"""
        parts = [str(self.dmr_id)]
        if self.callsign:
            parts.append(self.callsign)
        if self.name:
            parts.append(self.name)
        if self.city or self.state:
            location = ", ".join(filter(None, [self.city, self.state]))
            parts.append(f"({location})")
        return " - ".join(parts)


class GlobalContactDatabase:
    """Address book database manager"""

    def __init__(self):
        self.contacts: List[GlobalContact] = []

    def add_contact(self, contact: GlobalContact):
        """Add a contact to the database"""
        self.contacts.append(contact)

    def clear(self):
        """Clear all contacts"""
        self.contacts.clear()

    def get_contact_by_id(self, dmr_id: int) -> Optional[GlobalContact]:
        """Find contact by DMR ID"""
        for contact in self.contacts:
            if contact.dmr_id == dmr_id:
                return contact
        return None

    def sort_by_id(self):
        """Sort contacts by DMR ID (required for radio upload)"""
        self.contacts.sort(key=lambda c: c.dmr_id)

    def __len__(self) -> int:
        return len(self.contacts)

    def __getitem__(self, index: int) -> GlobalContact:
        return self.contacts[index]


class GlobalContactCSVParser:
    """Parse DMR user database CSV files

    Supports multiple CSV formats:
    - RadioDMRID format: No,Radio ID,CallSign,Name,City,State,Country,Remarks
    - Simple format: Radio ID,CallSign,Name,City,State,Country,Remarks
    - Minimal format: Radio ID,CallSign,Name
    """

    @staticmethod
    def parse_csv(filename: str, max_contacts: Optional[int] = None) -> GlobalContactDatabase:
        """Parse CSV file and return database

        Args:
            filename: Path to CSV file
            max_contacts: Optional limit on number of contacts to load

        Returns:
            GlobalContactDatabase with parsed contacts
        """
        db = GlobalContactDatabase()

        # Try multiple encodings
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
        f = None
        for encoding in encodings:
            try:
                f = open(filename, 'r', encoding=encoding, errors='replace')
                break
            except Exception:
                continue

        if f is None:
            raise ValueError(f"Could not open CSV file with any supported encoding")

        try:
            reader = csv.reader(f)

            # Read header
            header = next(reader, None)
            if not header:
                raise ValueError("Empty CSV file")

            # Normalize header (lowercase, strip spaces)
            header = [col.lower().strip() for col in header]

            # Detect column positions
            col_map = GlobalContactCSVParser._detect_columns(header)

            # Parse rows
            for row_num, row in enumerate(reader, start=2):
                if not row or len(row) < 2:
                    continue  # Skip empty rows

                try:
                    contact = GlobalContactCSVParser._parse_row(row, col_map)
                    if contact:
                        db.add_contact(contact)

                        # Check limit
                        if max_contacts and len(db) >= max_contacts:
                            break

                except Exception as e:
                    # Log error but continue parsing
                    print(f"Warning: Skipping row {row_num}: {e}")
                    continue

        finally:
            if f:
                f.close()

        # Sort by DMR ID (required for radio upload)
        db.sort_by_id()

        return db

    @staticmethod
    def _detect_columns(header: List[str]) -> dict:
        """Detect column positions from header

        Returns:
            Dictionary mapping field names to column indices
        """
        col_map = {}

        for idx, col in enumerate(header):
            # DMR ID column
            if 'radio' in col and 'id' in col:
                col_map['dmr_id'] = idx
            elif col in ['dmr_id', 'id', 'radioid', 'radio id', 'radio_id']:
                col_map['dmr_id'] = idx

            # Callsign
            elif 'call' in col:
                col_map['callsign'] = idx

            # Name (full name or first name)
            elif col in ['name', 'firstname', 'first name', 'fname', 'first_name']:
                if 'name' not in col_map:  # Prefer full name over first name
                    col_map['name'] = idx
                if 'first' in col:
                    col_map['first_name'] = idx

            # Last name
            elif col in ['lastname', 'last name', 'lname', 'last_name', 'surname']:
                col_map['last_name'] = idx

            # City
            elif col in ['city', 'town']:
                col_map['city'] = idx

            # State
            elif col in ['state', 'province', 'region']:
                col_map['state'] = idx

            # Country
            elif col in ['country', 'nation']:
                col_map['country'] = idx

            # Remarks
            elif col in ['remarks', 'comment', 'comments', 'note', 'notes']:
                col_map['remarks'] = idx

        # Validate required fields
        if 'dmr_id' not in col_map:
            # Try positional fallback - first column that looks like a number
            col_map['dmr_id'] = 0

        return col_map

    @staticmethod
    def _parse_row(row: List[str], col_map: dict) -> Optional[GlobalContact]:
        """Parse a single CSV row into GlobalContact

        Args:
            row: CSV row data
            col_map: Column mapping from _detect_columns

        Returns:
            GlobalContact or None if invalid
        """
        # Get DMR ID (required)
        dmr_id_idx = col_map.get('dmr_id', 0)
        if dmr_id_idx >= len(row):
            return None

        dmr_id_str = row[dmr_id_idx].strip()
        if not dmr_id_str:
            return None

        try:
            dmr_id = int(dmr_id_str)
        except ValueError:
            return None

        # Get optional fields
        def get_field(field_name: str, default: str = "") -> str:
            idx = col_map.get(field_name)
            if idx is not None and idx < len(row):
                return row[idx].strip()
            return default

        # Handle name field - combine first_name and last_name if separate
        name = get_field('name')
        if not name and ('first_name' in col_map or 'last_name' in col_map):
            first = get_field('first_name')
            last = get_field('last_name')
            name = " ".join(filter(None, [first, last]))

        return GlobalContact(
            dmr_id=dmr_id,
            callsign=get_field('callsign'),
            name=name,
            city=get_field('city'),
            state=get_field('state'),
            country=get_field('country'),
            remarks=get_field('remarks')
        )

    @staticmethod
    def export_csv(db: GlobalContactDatabase, filename: str):
        """Export database to CSV file

        Args:
            db: GlobalContactDatabase to export
            filename: Output CSV file path
        """
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow(['Radio ID', 'CallSign', 'Name', 'City', 'State', 'Country', 'Remarks'])

            # Write contacts
            for contact in db.contacts:
                writer.writerow([
                    contact.dmr_id,
                    contact.callsign,
                    contact.name,
                    contact.city,
                    contact.state,
                    contact.country,
                    contact.remarks
                ])

    @staticmethod
    def export_for_radio(db: GlobalContactDatabase) -> bytes:
        """Export database in format for radio upload

        Returns GBK-encoded CSV data (first 6 columns, no header, newline-separated)
        suitable for direct radio upload via UART.

        Args:
            db: GlobalContactDatabase to export

        Returns:
            GBK-encoded bytes ready for radio upload
        """
        lines = []

        # Format: Radio ID,CallSign,Name,City,State,Country (no remarks, no header)
        for contact in db.contacts:
            line = f"{contact.dmr_id},{contact.callsign},{contact.name},{contact.city},{contact.state},{contact.country}"
            lines.append(line)

        # Join with newlines
        text = '\n'.join(lines)

        # Encode to GBK (as expected by radio)
        try:
            return text.encode('gbk')
        except UnicodeEncodeError:
            # Fall back to latin-1 if GBK encoding fails
            return text.encode('latin-1', errors='replace')
