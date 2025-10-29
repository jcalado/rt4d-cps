#!/usr/bin/env python3
"""Test address book search performance"""

import time
from rt4d_codeplug.global_contacts import GlobalContactCSVParser

def test_search_performance():
    """Test search performance with different database sizes"""
    print("Address Book Search Performance Test")
    print("=" * 70)

    # Test with different sizes
    test_sizes = [1000, 10000, 50000, 100000]

    for size in test_sizes:
        print(f"\n[Test] Loading {size:,} contacts...")
        db = GlobalContactCSVParser.parse_csv(
            '08_01_2025_COMPLETE_DMR_ID_CONTACT_LIST_287191_RECORDS_RT4D_KD1MU.csv',
            max_contacts=size
        )
        print(f"✓ Loaded {len(db):,} contacts")

        # Test 1: Search with old method (string conversions)
        print("\n  Old method (with string conversions):")
        search_term = "smith"
        start = time.time()
        matches_old = []
        for contact in db.contacts:
            if (search_term in str(contact.dmr_id).lower() or
                search_term in contact.callsign.lower() or
                search_term in contact.name.lower()):
                matches_old.append(contact)
                if len(matches_old) >= 1000:  # Limit results
                    break
        elapsed_old = time.time() - start
        print(f"    Found {len(matches_old)} matches in {elapsed_old:.3f}s")

        # Test 2: Search with new method (pre-computed strings)
        print("\n  New method (pre-computed strings):")
        start = time.time()
        matches_new = []
        for contact in db.contacts:
            if contact.matches_search(search_term):
                matches_new.append(contact)
                if len(matches_new) >= 1000:  # Limit results
                    break
        elapsed_new = time.time() - start
        print(f"    Found {len(matches_new)} matches in {elapsed_new:.3f}s")

        # Calculate speedup
        if elapsed_old > 0:
            speedup = elapsed_old / elapsed_new
            print(f"\n  ⚡ Speedup: {speedup:.2f}x faster")
            print(f"  ⏱️  Time saved: {(elapsed_old - elapsed_new)*1000:.1f}ms")

    print("\n" + "=" * 70)
    print("Performance test complete!")

    # Test 3: Demonstrate result limiting
    print("\n[Test] Result Limiting Effect")
    print("=" * 70)

    db = GlobalContactCSVParser.parse_csv(
        '08_01_2025_COMPLETE_DMR_ID_CONTACT_LIST_287191_RECORDS_RT4D_KD1MU.csv',
        max_contacts=100000
    )

    search_term = "a"  # Common letter - will match many results

    # Without limiting
    print("\nSearching for 'a' without result limit:")
    start = time.time()
    matches_unlimited = []
    for contact in db.contacts:
        if contact.matches_search(search_term):
            matches_unlimited.append(contact)
    elapsed_unlimited = time.time() - start
    print(f"  Found {len(matches_unlimited):,} matches in {elapsed_unlimited:.3f}s")

    # With limiting (first 1000)
    print("\nSearching for 'a' with 1000 result limit:")
    start = time.time()
    matches_limited = []
    for contact in db.contacts:
        if contact.matches_search(search_term):
            matches_limited.append(contact)
            if len(matches_limited) >= 1000:
                break
    elapsed_limited = time.time() - start
    print(f"  Found {len(matches_limited):,} matches in {elapsed_limited:.3f}s")

    # Speedup from limiting
    if elapsed_unlimited > 0:
        speedup = elapsed_unlimited / elapsed_limited
        print(f"\n  ⚡ Speedup: {speedup:.2f}x faster")
        print(f"  ⏱️  Time saved: {(elapsed_unlimited - elapsed_limited)*1000:.1f}ms")

    print("\n" + "=" * 70)

if __name__ == '__main__':
    test_search_performance()
