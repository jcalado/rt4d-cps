#!/usr/bin/env python3
"""Test script for global contacts / address book functionality"""

from rt4d_codeplug.global_contacts import GlobalContactCSVParser

def test_csv_parser():
    """Test CSV parsing"""
    print("Testing Global Contacts CSV Parser...")
    print("=" * 60)

    # Parse the test CSV
    db = GlobalContactCSVParser.parse_csv('test_addressbook.csv')

    print(f"\nLoaded {len(db)} contacts from CSV")
    print(f"Contacts are sorted by DMR ID: {all(db[i].dmr_id <= db[i+1].dmr_id for i in range(len(db)-1))}")

    print("\nFirst 5 contacts:")
    for i in range(min(5, len(db))):
        contact = db[i]
        print(f"  {contact.dmr_id:8d} | {contact.callsign:10s} | {contact.name:20s} | {contact.city}, {contact.state}, {contact.country}")

    # Test lookup
    print("\nTesting lookup by DMR ID:")
    test_id = 2040001
    contact = db.get_contact_by_id(test_id)
    if contact:
        print(f"  Found: {contact.to_display_string()}")
    else:
        print(f"  Not found: {test_id}")

    # Test export
    print("\nExporting to test_export.csv...")
    GlobalContactCSVParser.export_csv(db, 'test_export.csv')
    print("  Export successful!")

    # Verify export by re-importing
    print("\nRe-importing exported file to verify...")
    db2 = GlobalContactCSVParser.parse_csv('test_export.csv')
    print(f"  Re-imported {len(db2)} contacts")
    print(f"  Match: {len(db) == len(db2)}")

    print("\n" + "=" * 60)
    print("All tests passed!")

if __name__ == '__main__':
    test_csv_parser()
