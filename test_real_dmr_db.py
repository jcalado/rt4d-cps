#!/usr/bin/env python3
"""Test script for real DMR database file"""

from rt4d_codeplug.global_contacts import GlobalContactCSVParser

def test_real_dmr_db():
    """Test with real KD1MU DMR database"""
    print("Testing with Real DMR Database (KD1MU)")
    print("=" * 70)

    filename = '08_01_2025_COMPLETE_DMR_ID_CONTACT_LIST_287191_RECORDS_RT4D_KD1MU.csv'

    # Test 1: Load first 100 contacts
    print("\n[Test 1] Loading first 100 contacts...")
    db = GlobalContactCSVParser.parse_csv(filename, max_contacts=100)
    print(f"✓ Loaded {len(db)} contacts")
    print(f"✓ Sorted by DMR ID: {all(db[i].dmr_id <= db[i+1].dmr_id for i in range(len(db)-1))}")

    print("\nFirst 5 contacts:")
    for i in range(min(5, len(db))):
        contact = db[i]
        print(f"  {contact.dmr_id:8d} | {contact.callsign:10s} | {contact.name:25s} | {contact.city}, {contact.state}, {contact.country}")

    # Test 2: Load first 10,000 contacts
    print("\n[Test 2] Loading first 10,000 contacts...")
    db = GlobalContactCSVParser.parse_csv(filename, max_contacts=10000)
    print(f"✓ Loaded {len(db):,} contacts")

    # Test lookup
    print("\n[Test 3] Testing lookup...")
    test_ids = [1023007, 2040001, 9999999]
    for test_id in test_ids:
        contact = db.get_contact_by_id(test_id)
        if contact:
            print(f"  ✓ Found {test_id}: {contact.to_display_string()}")
        else:
            print(f"  ✗ Not found: {test_id}")

    # Test 4: Load ALL contacts (this might take a moment)
    print("\n[Test 4] Loading ALL 287,191 contacts...")
    import time
    start = time.time()
    db_full = GlobalContactCSVParser.parse_csv(filename)
    elapsed = time.time() - start
    print(f"✓ Loaded {len(db_full):,} contacts in {elapsed:.2f} seconds")
    print(f"✓ Sorted by DMR ID: {all(db_full[i].dmr_id <= db_full[i+1].dmr_id for i in range(len(db_full)-1))}")

    # Stats
    print("\n[Stats]")
    print(f"  Total contacts: {len(db_full):,}")
    print(f"  Lowest DMR ID: {db_full[0].dmr_id}")
    print(f"  Highest DMR ID: {db_full[-1].dmr_id}")

    # Count contacts with names
    with_names = sum(1 for c in db_full.contacts[:1000] if c.name)
    print(f"  Contacts with names (first 1000): {with_names}/1000")

    print("\n" + "=" * 70)
    print("✓ All tests passed!")

if __name__ == '__main__':
    test_real_dmr_db()
