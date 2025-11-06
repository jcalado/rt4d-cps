#!/usr/bin/env python3
"""Test script to verify address book search is working correctly"""

from rt4d_codeplug.global_contacts import GlobalContactDatabase, GlobalContact

def test_search():
    print("Testing address book search functionality...\n")

    # Create test database
    db = GlobalContactDatabase()

    # Add test contacts
    test_contacts = [
        GlobalContact(dmr_id=1234567, callsign="W1ABC", name="John Smith"),
        GlobalContact(dmr_id=2345678, callsign="K2XYZ", name="Jane Doe"),
        GlobalContact(dmr_id=3456789, callsign="N3FOO", name="Bob Johnson"),
    ]

    for contact in test_contacts:
        db.add_contact(contact)

    print(f"Created database with {len(db)} contacts\n")

    # Test searches
    tests = [
        ("W1", 1, "callsign prefix"),
        ("K2XYZ", 1, "full callsign"),
        ("john", 1, "name search"),
        ("123", 1, "DMR ID prefix"),
        ("n3", 1, "lowercase callsign"),
    ]

    all_passed = True
    for query, expected_count, description in tests:
        results = db.search(query)
        if len(results) == expected_count:
            print(f"✓ PASS: '{query}' ({description}) - found {len(results)} result(s)")
        else:
            print(f"✗ FAIL: '{query}' ({description}) - expected {expected_count}, got {len(results)}")
            all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("✓ All tests PASSED! Search is working correctly.")
        print("\nCallsign search is functioning properly.")
    else:
        print("✗ Some tests FAILED! There may still be cached files.")
        print("\nTry restarting Python completely.")
    print("="*60)

if __name__ == "__main__":
    test_search()
