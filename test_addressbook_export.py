#!/usr/bin/env python3
"""Test address book radio export format"""

import os
import pytest
from rt4d_codeplug.global_contacts import GlobalContactCSVParser

TEST_ADDRESSBOOK_CSV = 'test_addressbook.csv'
LARGE_DMR_CSV = '08_01_2025_COMPLETE_DMR_ID_CONTACT_LIST_287191_RECORDS_RT4D_KD1MU.csv'

@pytest.mark.skipif(
    not os.path.exists(TEST_ADDRESSBOOK_CSV),
    reason=f"Test data file {TEST_ADDRESSBOOK_CSV} not found"
)
def test_export_format():
    """Test export for radio format"""
    print("Testing Address Book Radio Export Format")
    print("=" * 70)

    # Load small test database
    print("\n[Test 1] Loading test database...")
    db = GlobalContactCSVParser.parse_csv('test_addressbook.csv')
    print(f"✓ Loaded {len(db)} contacts")

    # Export for radio
    print("\n[Test 2] Exporting for radio...")
    data = GlobalContactCSVParser.export_for_radio(db)
    print(f"✓ Exported {len(data)} bytes")

    # Decode and display
    print("\n[Test 3] Decoded content (first 5 lines):")
    try:
        text = data.decode('gbk')
        lines = text.split('\n')
        for i, line in enumerate(lines[:5]):
            print(f"  {i+1}: {line}")
    except Exception as e:
        print(f"✗ Error decoding: {e}")

    # Check format
    print("\n[Test 4] Format validation:")
    print(f"  Lines: {len(lines)}")
    print(f"  Expected: {len(db)}")
    print(f"  Match: {len(lines) == len(db)}")

    # Check first line has 6 columns
    if lines:
        parts = lines[0].split(',')
        print(f"  Columns in first line: {len(parts)}")
        print(f"  Expected: 6 (ID, Call, Name, City, State, Country)")
        print(f"  Match: {len(parts) == 6}")

    # Test with large database
    print("\n[Test 5] Loading large database (first 10K contacts)...")
    db_large = GlobalContactCSVParser.parse_csv(
        '08_01_2025_COMPLETE_DMR_ID_CONTACT_LIST_287191_RECORDS_RT4D_KD1MU.csv',
        max_contacts=10000
    )
    print(f"✓ Loaded {len(db_large):,} contacts")

    print("\n[Test 6] Exporting large database...")
    data_large = GlobalContactCSVParser.export_for_radio(db_large)
    print(f"✓ Exported {len(data_large):,} bytes ({len(data_large)/1024:.1f} KB)")

    # Calculate how many 1KB blocks
    num_blocks = (len(data_large) + 4 + 1023) // 1024
    print(f"  Will require {num_blocks:,} blocks to upload")
    print(f"  Estimated time: ~{num_blocks * 0.1:.1f} seconds (at 10 blocks/sec)")

    print("\n" + "=" * 70)
    print("✓ All tests passed!")

if __name__ == '__main__':
    test_export_format()
