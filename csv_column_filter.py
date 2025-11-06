#!/usr/bin/env python3
"""CSV Column Filter - Select and extract specific columns from CSV files

This utility helps prepare CSV files by allowing you to select which columns to keep.
Useful for cleaning up large DMR database files before importing into the address book.

Usage:
    Default DMR mode:
        python csv_column_filter.py input.csv [output.csv]

        Transforms: RADIO_ID, CALLSIGN, FIRST_NAME, LAST_NAME, CITY, STATE, COUNTRY
        To:         RADIO_ID, CALLSIGN, FIRST_NAME (combined), LAST_NAME (empty), CITY (empty), STATE, COUNTRY

    Interactive mode:
        python csv_column_filter.py input.csv --interactive

    Command-line mode:
        python csv_column_filter.py input.csv output.csv --columns "1,3,5"
        python csv_column_filter.py input.csv output.csv --columns "Name,Callsign,City"
"""

import csv
import sys
import argparse
from pathlib import Path
from typing import List, Optional, Tuple


class CSVColumnFilter:
    """Filter and extract specific columns from CSV files"""

    def __init__(self, input_file: str):
        self.input_file = input_file
        self.headers = []
        self.encoding = None
        self._detect_encoding_and_read_headers()

    def _detect_encoding_and_read_headers(self):
        """Detect file encoding and read CSV headers"""
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

        for encoding in encodings:
            try:
                with open(self.input_file, 'r', encoding=encoding, errors='replace') as f:
                    reader = csv.reader(f)
                    self.headers = next(reader, None)
                    if self.headers:
                        self.encoding = encoding
                        # Normalize headers (strip whitespace)
                        self.headers = [h.strip() for h in self.headers]
                        return
            except Exception:
                continue

        raise ValueError(f"Could not read CSV file with any supported encoding")

    def display_columns(self, show_preview: bool = True):
        """Display available columns with their indices"""
        print("\n" + "=" * 70)
        print("Available columns in CSV:")
        print("=" * 70)

        for idx, header in enumerate(self.headers, start=1):
            print(f"  [{idx:2d}] {header}")

        if show_preview:
            print("\n" + "=" * 70)
            print("Preview (first 3 rows):")
            print("=" * 70)
            try:
                with open(self.input_file, 'r', encoding=self.encoding, errors='replace') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for i, row in enumerate(reader):
                        if i >= 3:
                            break
                        # Show first 80 chars of each row
                        row_preview = ','.join(row)[:80]
                        print(f"  {row_preview}...")
            except Exception as e:
                print(f"  Could not show preview: {e}")

        print("=" * 70 + "\n")

    def parse_column_selection(self, selection: str) -> List[int]:
        """Parse user column selection string into list of column indices

        Supports:
        - Numbers: "1,3,5" -> columns 1, 3, 5
        - Ranges: "1-5" -> columns 1, 2, 3, 4, 5
        - Names: "Name,City" -> find columns by name
        - Mix: "1,Name,5-7"

        Args:
            selection: User input string

        Returns:
            List of 0-based column indices
        """
        indices = set()
        parts = [p.strip() for p in selection.split(',')]

        for part in parts:
            # Handle ranges (e.g., "1-5")
            if '-' in part and part.replace('-', '').isdigit():
                try:
                    start, end = map(int, part.split('-'))
                    for i in range(start, end + 1):
                        if 1 <= i <= len(self.headers):
                            indices.add(i - 1)  # Convert to 0-based
                except ValueError:
                    print(f"Warning: Invalid range '{part}', skipping")
                    continue

            # Handle numbers
            elif part.isdigit():
                idx = int(part)
                if 1 <= idx <= len(self.headers):
                    indices.add(idx - 1)  # Convert to 0-based
                else:
                    print(f"Warning: Column {idx} out of range (1-{len(self.headers)}), skipping")

            # Handle column names
            else:
                # Try to find column by name (case-insensitive)
                found = False
                for idx, header in enumerate(self.headers):
                    if header.lower() == part.lower():
                        indices.add(idx)
                        found = True
                        break
                if not found:
                    print(f"Warning: Column '{part}' not found, skipping")

        # Return sorted indices
        return sorted(list(indices))

    def get_interactive_selection(self) -> List[int]:
        """Interactively ask user which columns to keep"""
        self.display_columns(show_preview=True)

        print("Select columns to keep:")
        print("  - By number: 1,3,5")
        print("  - By range: 1-5")
        print("  - By name: Name,City,State")
        print("  - Mix: 1,Name,5-7")
        print("  - All: all")
        print()

        while True:
            selection = input("Your selection: ").strip()

            if not selection:
                print("Error: Please enter a selection\n")
                continue

            if selection.lower() == 'all':
                return list(range(len(self.headers)))

            indices = self.parse_column_selection(selection)

            if not indices:
                print("Error: No valid columns selected, please try again\n")
                continue

            # Show selected columns
            print(f"\nSelected {len(indices)} column(s):")
            for idx in indices:
                print(f"  [{idx + 1:2d}] {self.headers[idx]}")

            confirm = input("\nProceed with these columns? (y/n): ").strip().lower()
            if confirm in ['y', 'yes']:
                return indices
            else:
                print("\nLet's try again...\n")

    def filter_csv(self, output_file: str, column_indices: List[int],
                   column_transforms: Optional[List[Tuple[List[int], str]]] = None):
        """Filter CSV file to keep only selected columns

        Args:
            output_file: Path to output file
            column_indices: List of 0-based column indices to keep
            column_transforms: Optional list of (indices, header_name) tuples for combining columns
        """
        if not column_indices and not column_transforms:
            raise ValueError("No columns selected")

        print(f"\nProcessing CSV file...")
        print(f"  Input:  {self.input_file}")
        print(f"  Output: {output_file}")

        rows_processed = 0

        try:
            with open(self.input_file, 'r', encoding=self.encoding, errors='replace') as infile, \
                 open(output_file, 'w', encoding='utf-8', newline='') as outfile:

                reader = csv.reader(infile)
                writer = csv.writer(outfile)

                # Write filtered header
                header = next(reader, None)
                if header:
                    if column_transforms:
                        # Build header with transformations
                        filtered_header = []
                        for transform in column_transforms:
                            if isinstance(transform, tuple):
                                # Combined column
                                filtered_header.append(transform[1])
                            else:
                                # Single column
                                filtered_header.append(header[transform])
                    else:
                        filtered_header = [header[i] for i in column_indices]

                    writer.writerow(filtered_header)
                    print(f"  Output columns: {', '.join(filtered_header)}")

                # Write filtered rows
                for row in reader:
                    try:
                        if column_transforms:
                            # Build row with transformations
                            filtered_row = []
                            for transform in column_transforms:
                                if isinstance(transform, tuple):
                                    # Combine multiple columns
                                    indices, _ = transform
                                    values = [row[i].strip() if i < len(row) else '' for i in indices]
                                    # Combine with space, filter out empty strings
                                    combined = ' '.join(v for v in values if v)
                                    filtered_row.append(combined)
                                else:
                                    # Single column
                                    filtered_row.append(row[transform] if transform < len(row) else '')
                        else:
                            filtered_row = [row[i] if i < len(row) else '' for i in column_indices]

                        writer.writerow(filtered_row)
                        rows_processed += 1

                        # Progress indicator
                        if rows_processed % 10000 == 0:
                            print(f"  Processed {rows_processed:,} rows...")
                    except Exception as e:
                        print(f"  Warning: Skipping row {rows_processed + 1}: {e}")
                        continue

            print(f"\n✓ Successfully processed {rows_processed:,} rows")
            print(f"✓ Output saved to: {output_file}")

        except Exception as e:
            print(f"\n✗ Error processing CSV: {e}")
            raise

    def apply_dmr_transform(self, output_file: str):
        """Apply default DMR database transformation

        Input:  RADIO_ID, CALLSIGN, FIRST_NAME, LAST_NAME, CITY, STATE, COUNTRY
        Output: RADIO_ID, CALLSIGN, FIRST_NAME (combined), LAST_NAME (empty), CITY (empty), STATE, COUNTRY

        Args:
            output_file: Path to output file
        """
        # Find required columns
        required_cols = {
            'RADIO_ID': None,
            'CALLSIGN': None,
            'FIRST_NAME': None,
            'LAST_NAME': None,
            'CITY': None,
            'STATE': None,
            'COUNTRY': None
        }

        for idx, header in enumerate(self.headers):
            header_upper = header.upper()
            if header_upper in required_cols:
                required_cols[header_upper] = idx

        # Check if all required columns exist
        missing = [col for col, idx in required_cols.items() if idx is None]
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}\n" +
                           f"Available columns: {', '.join(self.headers)}")

        # Build transformation list
        # Format: list of either int (single column) or tuple ([indices], header_name) for combined
        transforms = [
            required_cols['RADIO_ID'],                                      # RADIO_ID
            required_cols['CALLSIGN'],                                      # CALLSIGN
            ([required_cols['FIRST_NAME'], required_cols['LAST_NAME']], 'FIRST_NAME'),  # Combined name in FIRST_NAME
            ([],  'LAST_NAME'),                                            # LAST_NAME (empty)
            ([],  'CITY'),                                                 # CITY (empty)
            required_cols['STATE'],                                         # STATE
            required_cols['COUNTRY']                                        # COUNTRY
        ]

        print("\nApplying default DMR transformation:")
        print(f"  RADIO_ID    -> RADIO_ID")
        print(f"  CALLSIGN    -> CALLSIGN")
        print(f"  FIRST_NAME + LAST_NAME -> FIRST_NAME (combined)")
        print(f"  LAST_NAME   -> (empty)")
        print(f"  CITY        -> (empty)")
        print(f"  STATE       -> STATE")
        print(f"  COUNTRY     -> COUNTRY")

        # Process the CSV with transformations
        self.filter_csv(output_file, [], column_transforms=transforms)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Filter and extract specific columns from CSV files (Default: DMR transformation)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Default DMR transformation:
    Combines FIRST_NAME + LAST_NAME into FIRST_NAME column, empties LAST_NAME and CITY
    Output: RADIO_ID, CALLSIGN, FIRST_NAME (combined), LAST_NAME (empty), CITY (empty), STATE, COUNTRY

    python csv_column_filter.py input.csv
    python csv_column_filter.py input.csv output.csv

  Interactive mode:
    python csv_column_filter.py input.csv --interactive

  Select columns by number:
    python csv_column_filter.py input.csv output.csv --columns "1,3,5"

  Select columns by name:
    python csv_column_filter.py input.csv output.csv --columns "DMR ID,Callsign,Name"

  Select column range:
    python csv_column_filter.py input.csv output.csv --columns "1-5"
        """
    )

    parser.add_argument('input_file', help='Input CSV file')
    parser.add_argument('output_file', nargs='?', help='Output CSV file (optional, defaults based on mode)')
    parser.add_argument('--columns', '-c', help='Comma-separated column numbers, names, or ranges')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Use interactive mode to select columns')

    args = parser.parse_args()

    # Validate input file exists
    if not Path(args.input_file).exists():
        print(f"Error: Input file '{args.input_file}' not found")
        sys.exit(1)

    try:
        # Create filter instance
        filter_tool = CSVColumnFilter(args.input_file)

        # Determine operation mode
        if args.columns:
            # Command-line mode with explicit columns
            if not args.output_file:
                print("Error: Output file required when using --columns")
                sys.exit(1)

            column_indices = filter_tool.parse_column_selection(args.columns)
            if not column_indices:
                print("Error: No valid columns selected")
                sys.exit(1)

            # Show selected columns
            print(f"\nSelected {len(column_indices)} column(s):")
            for idx in column_indices:
                print(f"  [{idx + 1:2d}] {filter_tool.headers[idx]}")

            # Process the CSV file
            filter_tool.filter_csv(args.output_file, column_indices)

        elif args.interactive:
            # Interactive mode
            column_indices = filter_tool.get_interactive_selection()

            # Get output filename if not provided
            if not args.output_file:
                default_output = Path(args.input_file).stem + "_filtered.csv"
                output_input = input(f"\nOutput file [{default_output}]: ").strip()
                args.output_file = output_input if output_input else default_output

            # Process the CSV file
            filter_tool.filter_csv(args.output_file, column_indices)

        else:
            # Default mode: DMR transformation
            if not args.output_file:
                default_output = Path(args.input_file).stem + "_dmr.csv"
                args.output_file = default_output
                print(f"Using default output file: {args.output_file}")

            # Apply DMR transformation
            filter_tool.apply_dmr_transform(args.output_file)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
