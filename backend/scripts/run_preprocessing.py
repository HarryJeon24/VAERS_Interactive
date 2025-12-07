#!/usr/bin/env python3
"""
CLI tool to run VAERS text preprocessing pipeline.

Usage examples:
    # Analyze and build term mappings from subsample data
    python run_preprocessing.py analyze --input data/subsample/devVAERSDATA.csv

    # Analyze with year filter (only 2023 and 2024)
    python run_preprocessing.py analyze --input data/subsample/devVAERSDATA.csv --years 2023,2024

    # Preprocess data using saved mappings
    python run_preprocessing.py preprocess --input data/raw/2024VAERSDATA.csv --output data/processed/2024VAERSDATA_clean.csv --mappings data/term_mappings.json

    # Full pipeline: analyze + preprocess
    python run_preprocessing.py full --input data/subsample/devVAERSDATA.csv --output data/processed/devVAERSDATA_clean.csv --years 2023,2024
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Set

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from preprocess_pipeline import VAERSPreprocessor


def parse_years(years_str: Optional[str]) -> Optional[Set[int]]:
    """
    Parse comma-separated years string.

    Args:
        years_str: Comma-separated years (e.g., "2023,2024,2025")

    Returns:
        Set of year integers, or None if not specified
    """
    if not years_str:
        return None

    years = set()
    for year_part in years_str.split(','):
        year_part = year_part.strip()
        if '-' in year_part:
            # Range: 2020-2024
            start, end = year_part.split('-')
            years.update(range(int(start), int(end) + 1))
        else:
            # Single year
            years.add(int(year_part))

    return years


def cmd_analyze(args):
    """Analyze data and build term mappings."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        return 1

    # Parse years filter
    year_filter = parse_years(args.years)
    if year_filter:
        print(f"[INFO] Year filter: {sorted(year_filter)}")
    else:
        print("[INFO] No year filter - processing all years")

    # Create preprocessor
    preprocessor = VAERSPreprocessor(
        use_lemmatization=not args.no_lemmatization,
        min_term_frequency=args.min_freq,
        similarity_threshold=args.similarity,
        use_medical_filter=True,
    )

    # Extract terms
    print("\n=== STEP 1: Extracting Terms ===")
    field_frequencies = preprocessor.extract_field_terms(
        input_path,
        year_filter=year_filter,
        encodings=args.encodings.split(',') if args.encodings else None,
    )

    # Build standardization maps
    print("\n=== STEP 2: Building Standardization Maps ===")
    preprocessor.build_standardization_maps(field_frequencies)

    # Print statistics
    preprocessor.print_statistics()

    # Save mappings
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / "term_mappings.json"

    preprocessor.save_term_mappings(output_path)

    print(f"\n[OK] Analysis complete. Mappings saved to: {output_path}")
    return 0


def cmd_preprocess(args):
    """Preprocess data using existing term mappings."""
    input_path = Path(args.input)
    output_path = Path(args.output)
    mappings_path = Path(args.mappings)

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        return 1

    if not mappings_path.exists():
        print(f"[ERROR] Mappings file not found: {mappings_path}")
        print("[HINT] Run 'analyze' command first to generate mappings")
        return 1

    # Parse years filter
    year_filter = parse_years(args.years)
    if year_filter:
        print(f"[INFO] Year filter: {sorted(year_filter)}")

    # Create preprocessor and load mappings
    preprocessor = VAERSPreprocessor(
        use_lemmatization=not args.no_lemmatization,
        use_medical_filter=True,
    )
    preprocessor.load_term_mappings(mappings_path)

    # Preprocess CSV
    print("\n=== Preprocessing Data ===")
    preprocessor.preprocess_csv(
        input_path,
        output_path,
        year_filter=year_filter,
        encodings=args.encodings.split(',') if args.encodings else None,
    )

    print(f"\n[OK] Preprocessing complete. Output saved to: {output_path}")
    return 0


def cmd_full(args):
    """Run full pipeline: analyze + preprocess."""
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}")
        return 1

    # Parse years filter
    year_filter = parse_years(args.years)
    if year_filter:
        print(f"[INFO] Year filter: {sorted(year_filter)}")
    else:
        print("[INFO] No year filter - processing all years")

    # Create preprocessor
    preprocessor = VAERSPreprocessor(
        use_lemmatization=not args.no_lemmatization,
        min_term_frequency=args.min_freq,
        similarity_threshold=args.similarity,
        use_medical_filter=True,
    )

    encodings = args.encodings.split(',') if args.encodings else None

    # STEP 1: Analyze
    print("\n=== STEP 1: Analyzing and Building Term Mappings ===")
    field_frequencies = preprocessor.extract_field_terms(
        input_path,
        year_filter=year_filter,
        encodings=encodings,
    )

    preprocessor.build_standardization_maps(field_frequencies)
    preprocessor.print_statistics()

    # Save mappings
    mappings_path = output_path.parent / f"{output_path.stem}_term_mappings.json"
    preprocessor.save_term_mappings(mappings_path)

    # STEP 2: Preprocess
    print("\n=== STEP 2: Preprocessing Data ===")
    preprocessor.preprocess_csv(
        input_path,
        output_path,
        year_filter=year_filter,
        encodings=encodings,
    )

    print(f"\n[OK] Full pipeline complete!")
    print(f"  Preprocessed data: {output_path}")
    print(f"  Term mappings: {mappings_path}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='VAERS text preprocessing pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze data and build term mappings')
    analyze_parser.add_argument('--input', '-i', required=True, help='Input CSV file path')
    analyze_parser.add_argument('--output', '-o', help='Output mappings JSON path (default: same dir as input)')
    analyze_parser.add_argument('--years', '-y', help='Comma-separated years or ranges (e.g., "2023,2024" or "2020-2024")')
    analyze_parser.add_argument('--min-freq', type=int, default=3, help='Minimum term frequency (default: 3)')
    analyze_parser.add_argument('--similarity', type=float, default=0.85, help='Similarity threshold for term matching (default: 0.85)')
    analyze_parser.add_argument('--no-lemmatization', action='store_true', help='Disable lemmatization')
    analyze_parser.add_argument('--encodings', default='utf-8,cp1252,latin1', help='Comma-separated encodings to try')

    # Preprocess command
    preprocess_parser = subparsers.add_parser('preprocess', help='Preprocess data using existing mappings')
    preprocess_parser.add_argument('--input', '-i', required=True, help='Input CSV file path')
    preprocess_parser.add_argument('--output', '-o', required=True, help='Output CSV file path')
    preprocess_parser.add_argument('--mappings', '-m', required=True, help='Term mappings JSON file path')
    preprocess_parser.add_argument('--years', '-y', help='Comma-separated years to include')
    preprocess_parser.add_argument('--no-lemmatization', action='store_true', help='Disable lemmatization')
    preprocess_parser.add_argument('--encodings', default='utf-8,cp1252,latin1', help='Comma-separated encodings to try')

    # Full pipeline command
    full_parser = subparsers.add_parser('full', help='Run full pipeline: analyze + preprocess')
    full_parser.add_argument('--input', '-i', required=True, help='Input CSV file path')
    full_parser.add_argument('--output', '-o', required=True, help='Output CSV file path')
    full_parser.add_argument('--years', '-y', help='Comma-separated years to include')
    full_parser.add_argument('--min-freq', type=int, default=3, help='Minimum term frequency (default: 3)')
    full_parser.add_argument('--similarity', type=float, default=0.85, help='Similarity threshold for term matching (default: 0.85)')
    full_parser.add_argument('--no-lemmatization', action='store_true', help='Disable lemmatization')
    full_parser.add_argument('--encodings', default='utf-8,cp1252,latin1', help='Comma-separated encodings to try')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Route to appropriate command
    if args.command == 'analyze':
        return cmd_analyze(args)
    elif args.command == 'preprocess':
        return cmd_preprocess(args)
    elif args.command == 'full':
        return cmd_full(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
