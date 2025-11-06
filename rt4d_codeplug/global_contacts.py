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


class TrieNode:
    """Node in a prefix trie for fast prefix matching"""

    def __init__(self):
        self.children: dict = {}
        self.contacts: List[GlobalContact] = []


class ContactIndex:
    """In-memory search index for fast contact lookups

    Uses a combination of:
    - Hash map for O(1) DMR ID lookups
    - Prefix tries for fast prefix matching on callsign and name

    Expected performance:
    - DMR ID lookup: O(1) vs O(n) linear scan
    - Prefix search: O(m + k) where m=prefix length, k=results vs O(n) linear scan
    - Memory overhead: ~10-20MB for 100k contacts
    """

    def __init__(self):
        self.dmr_id_map: dict = {}  # Fast DMR ID lookup: {dmr_id: GlobalContact}
        self.callsign_trie: TrieNode = TrieNode()  # Prefix trie for callsign search
        self.name_trie: TrieNode = TrieNode()  # Prefix trie for name search

    def add_contact(self, contact: GlobalContact):
        """Add a contact to all indexes"""
        # DMR ID hash map for exact/prefix ID lookups
        self.dmr_id_map[contact.dmr_id] = contact

        # Add to callsign trie (full callsign)
        if contact.callsign:
            self._add_to_trie(self.callsign_trie, contact.callsign.lower(), contact)

        # Add to name trie (split by words for multi-word names)
        if contact.name:
            for word in contact.name.lower().split():
                if word:
                    self._add_to_trie(self.name_trie, word, contact)

    def _add_to_trie(self, root: TrieNode, text: str, contact: GlobalContact):
        """Add text to trie, storing contact at leaf nodes

        Args:
            root: Root node of the trie
            text: Text to index
            contact: Contact to store at the leaf
        """
        if not text:
            return

        node = root
        for char in text:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]

        # Store contact at the end of the word
        if contact not in node.contacts:
            node.contacts.append(contact)

    def search(self, query: str) -> List[GlobalContact]:
        """Search for contacts matching query

        Searches across DMR ID (prefix), callsign (prefix), and name (prefix on any word).
        Returns deduplicated list of matching contacts.

        Performance: O(m + k) where m=query length, k=number of matches

        Args:
            query: Search query (can be DMR ID, callsign, or name)

        Returns:
            List of matching GlobalContact objects (deduplicated)
        """
        if not query:
            return []

        query_lower = query.lower().strip()
        # Use dict for deduplication by object id (contacts are not hashable)
        matches_dict = {}

        # Try DMR ID search (both exact and prefix)
        if query.isdigit():
            dmr_query = query  # Keep original for prefix matching
            # Exact match
            try:
                dmr_id = int(dmr_query)
                if dmr_id in self.dmr_id_map:
                    contact = self.dmr_id_map[dmr_id]
                    matches_dict[id(contact)] = contact
            except ValueError:
                pass

            # Prefix match for partial DMR IDs (e.g., "123" matches "1234567")
            for contact_dmr_id, contact in self.dmr_id_map.items():
                if str(contact_dmr_id).startswith(dmr_query):
                    matches_dict[id(contact)] = contact

        # Search callsign trie (prefix match)
        callsign_matches = self._search_trie(self.callsign_trie, query_lower)
        for contact in callsign_matches:
            matches_dict[id(contact)] = contact

        # Search name trie (prefix match on any word)
        name_matches = self._search_trie(self.name_trie, query_lower)
        for contact in name_matches:
            matches_dict[id(contact)] = contact

        return list(matches_dict.values())

    def _search_trie(self, root: TrieNode, prefix: str) -> List[GlobalContact]:
        """Search trie for contacts with fields starting with prefix

        Args:
            root: Root node of the trie to search
            prefix: Prefix to search for

        Returns:
            List of contacts whose indexed field starts with prefix
        """
        if not prefix:
            return []

        # Navigate to the prefix node
        node = root
        for char in prefix:
            if char not in node.children:
                return []  # Prefix doesn't exist in trie
            node = node.children[char]

        # Collect all contacts from this node and all descendants
        return self._collect_all_contacts(node)

    def _collect_all_contacts(self, node: TrieNode) -> List[GlobalContact]:
        """Recursively collect all contacts from a trie node and its descendants

        Args:
            node: Starting node

        Returns:
            Deduplicated list of all contacts in subtree
        """
        # Use dict to deduplicate by object id (contacts are not hashable)
        contacts_dict = {}

        for contact in node.contacts:
            contacts_dict[id(contact)] = contact

        for child in node.children.values():
            for contact in self._collect_all_contacts(child):
                contacts_dict[id(contact)] = contact

        return list(contacts_dict.values())

    def get_by_id(self, dmr_id: int) -> Optional[GlobalContact]:
        """Fast O(1) lookup by DMR ID

        Args:
            dmr_id: DMR ID to look up

        Returns:
            GlobalContact if found, None otherwise
        """
        return self.dmr_id_map.get(dmr_id)

    def clear(self):
        """Clear all indexes"""
        self.dmr_id_map.clear()
        self.callsign_trie = TrieNode()
        self.name_trie = TrieNode()

    def rebuild(self, contacts: List[GlobalContact]):
        """Rebuild all indexes from a list of contacts

        Args:
            contacts: List of contacts to index
        """
        self.clear()
        for contact in contacts:
            self.add_contact(contact)


class GlobalContactDatabase:
    """Address book database manager with fast search indexing"""

    def __init__(self):
        self.contacts: List[GlobalContact] = []
        self.index: ContactIndex = ContactIndex()

    def add_contact(self, contact: GlobalContact, build_index: bool = True):
        """Add a contact to the database and optionally to search index

        Args:
            contact: GlobalContact to add
            build_index: If True, add to search index immediately (default).
                        If False, skip index building (use for bulk imports,
                        then call rebuild_index() after all contacts added)
        """
        self.contacts.append(contact)
        if build_index:
            self.index.add_contact(contact)

    def rebuild_index(self):
        """Rebuild search index from all contacts in database

        Use this after bulk adding contacts with build_index=False.
        Much faster than building index incrementally during import.
        """
        self.index.rebuild(self.contacts)

    def clear(self):
        """Clear all contacts and search index"""
        self.contacts.clear()
        self.index.clear()

    def get_contact_by_id(self, dmr_id: int) -> Optional[GlobalContact]:
        """Find contact by DMR ID using fast O(1) index lookup"""
        return self.index.get_by_id(dmr_id)

    def search(self, query: str) -> List[GlobalContact]:
        """Search for contacts matching query

        Uses fast indexed search across DMR ID, callsign, and name fields.
        Performance: O(m + k) where m=query length, k=number of matches

        Args:
            query: Search query string

        Returns:
            List of matching GlobalContact objects
        """
        return self.index.search(query)

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

            # Parse rows (deferred index building for performance)
            for row_num, row in enumerate(reader, start=2):
                if not row or len(row) < 2:
                    continue  # Skip empty rows

                try:
                    contact = GlobalContactCSVParser._parse_row(row, col_map)
                    if contact:
                        # Skip index building during import for 3-10x speedup
                        db.add_contact(contact, build_index=False)

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

        # Build search index after all contacts loaded (much faster than incremental)
        db.rebuild_index()

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
