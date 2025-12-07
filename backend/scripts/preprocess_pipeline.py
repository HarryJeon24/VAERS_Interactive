#!/usr/bin/env python3
"""
VAERS data preprocessing pipeline.
Processes text fields to create unified terminology across datasets.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Iterable

from text_normalizer import TextNormalizer, create_term_standardization_map
from medical_terms_dict import get_all_lookups


# Text fields to preprocess (as requested)
TEXT_FIELDS = [
    'LAB_DATA',
    'OTHER_MEDS',
    'CUR_ILL',
    'HISTORY',
    'PRIOR_VAX',
    'ALLERGIES',
]


class VAERSPreprocessor:
    """
    Main preprocessing pipeline for VAERS data.
    """

    def __init__(
        self,
        use_lemmatization: bool = True,
        min_term_frequency: int = 3,
        similarity_threshold: float = 0.85,
        use_medical_filter: bool = True,
    ):
        """
        Initialize the preprocessor.

        Args:
            use_lemmatization: Use lemmatization for text normalization
            min_term_frequency: Minimum frequency for terms to be included
            similarity_threshold: Similarity threshold for term standardization
            use_medical_filter: Filter to only keep terms in medical dictionary
        """
        self.normalizer = TextNormalizer(use_lemmatization=use_lemmatization)
        self.min_term_frequency = min_term_frequency
        self.similarity_threshold = similarity_threshold
        self.use_medical_filter = use_medical_filter

        # Load medical dictionaries
        self.medical_lookups = get_all_lookups()

        # Create a combined lookup of all medical terms
        self.all_medical_terms = set()
        for lookup in self.medical_lookups.values():
            self.all_medical_terms.update(lookup.keys())

        # Statistics
        self.field_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.term_mappings: Dict[str, Dict[str, str]] = {}  # field -> term -> standard_term

    def read_csv_with_encoding(self, csv_path: Path, encodings: List[str]) -> Iterable[Dict[str, str]]:
        """
        Read CSV with encoding fallback.

        Args:
            csv_path: Path to CSV file
            encodings: List of encodings to try

        Yields:
            Dictionary rows
        """
        for enc in encodings:
            if not enc:
                continue
            try:
                with csv_path.open('r', newline='', encoding=enc, errors='strict') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        yield row
                return
            except (UnicodeDecodeError, FileNotFoundError):
                continue

        # Fallback to latin1 with replacement
        with csv_path.open('r', newline='', encoding='latin1', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row

    def extract_field_terms(
        self,
        csv_path: Path,
        year_filter: Optional[Set[int]] = None,
        encodings: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, int]]:
        """
        Extract and count terms from text fields.

        Args:
            csv_path: Path to VAERS CSV file
            year_filter: Set of years to include (None = all years)
            encodings: List of encodings to try

        Returns:
            Dictionary mapping field -> term -> frequency
        """
        if encodings is None:
            encodings = ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']

        field_terms: Dict[str, List[str]] = defaultdict(list)
        rows_processed = 0
        rows_filtered = 0

        print(f"[INFO] Extracting terms from {csv_path.name}...")

        for row in self.read_csv_with_encoding(csv_path, encodings):
            # Apply year filter if specified
            if year_filter is not None:
                year_str = row.get('YEAR', '').strip()
                if year_str:
                    try:
                        year = int(float(year_str))
                        if year not in year_filter:
                            rows_filtered += 1
                            continue
                    except ValueError:
                        pass

            rows_processed += 1

            # Process each text field
            for field in TEXT_FIELDS:
                if field not in row:
                    continue

                text = row.get(field, '')
                if not text or text.strip() == '':
                    self.field_stats[field]['empty'] += 1
                    continue

                # Normalize and extract terms
                normalized = self.normalizer.normalize(text)
                if normalized:
                    terms = self.normalizer.extract_terms(normalized)
                    field_terms[field].extend(terms)
                    self.field_stats[field]['non_empty'] += 1

            if rows_processed % 10000 == 0:
                print(f"  Processed {rows_processed:,} rows...")

        print(f"[INFO] Processed {rows_processed:,} rows (filtered {rows_filtered:,} by year)")

        # Count term frequencies per field
        field_frequencies = {}
        for field, terms in field_terms.items():
            field_frequencies[field] = self.normalizer.extract_unique_terms(
                [' '.join(terms)],
                min_frequency=self.min_term_frequency
            )

        return field_frequencies

    def build_standardization_maps(
        self,
        field_frequencies: Dict[str, Dict[str, int]]
    ) -> Dict[str, Dict[str, str]]:
        """
        Build term standardization maps for each field.

        Args:
            field_frequencies: Field -> term -> frequency

        Returns:
            Field -> term -> standardized_term mappings
        """
        print("[INFO] Building term standardization maps...")

        standardization_maps = {}

        for field, term_freqs in field_frequencies.items():
            print(f"  Processing {field}: {len(term_freqs)} unique terms")

            # Create standardization map
            std_map = create_term_standardization_map(
                term_freqs,
                similarity_threshold=self.similarity_threshold
            )

            standardization_maps[field] = std_map
            print(f"    Created {len(std_map)} standardization mappings")

        self.term_mappings = standardization_maps
        return standardization_maps

    def filter_and_standardize_medical_terms(self, terms: List[str], field: str) -> List[str]:
        """
        Filter terms to only include medical terms and standardize them.

        Args:
            terms: List of terms
            field: Field name (for field-specific filtering)

        Returns:
            Filtered and standardized list of medical terms
        """
        if not self.use_medical_filter:
            return terms

        filtered = []

        # Field-specific lookups
        field_lookups = {
            'OTHER_MEDS': ('medications', self.medical_lookups['medications']),
            'PRIOR_VAX': ('vaccines', self.medical_lookups['vaccines']),
            'ALLERGIES': ('allergies', self.medical_lookups['allergies']),
            'CUR_ILL': ('conditions', self.medical_lookups['conditions']),
            'HISTORY': ('conditions', self.medical_lookups['conditions']),
        }

        # Get relevant lookup for this field
        if field in field_lookups:
            lookup_type, relevant_lookup = field_lookups[field]
        else:
            # For LAB_DATA and other fields, use all medical terms
            lookup_type = None
            relevant_lookup = None

        for term in terms:
            term_lower = term.lower()

            # Check field-specific lookup first and standardize
            if relevant_lookup and term_lower in relevant_lookup:
                standardized = relevant_lookup[term_lower]
                filtered.append(standardized)
            # Then check all medical terms
            elif term_lower in self.all_medical_terms:
                # Find which lookup it belongs to and standardize
                for lookup_dict in self.medical_lookups.values():
                    if term_lower in lookup_dict:
                        filtered.append(lookup_dict[term_lower])
                        break

        return filtered

    def preprocess_row(self, row: Dict[str, str]) -> Dict[str, str]:
        """
        Preprocess a single row by normalizing text fields.
        Only keeps relevant medical terms, formatted as comma-separated values.

        Args:
            row: CSV row as dictionary

        Returns:
            Row with preprocessed text fields
        """
        processed_row = row.copy()

        for field in TEXT_FIELDS:
            if field not in row:
                continue

            text = row.get(field, '')

            # Check if text indicates "none/unknown"
            if self.normalizer.is_none_text(text):
                processed_row[field] = ''
                continue

            if not text or text.strip() == '':
                processed_row[field] = ''
                continue

            # Normalize
            normalized = self.normalizer.normalize(text)

            # Extract terms
            terms = self.normalizer.extract_terms(normalized)

            # Apply standardization if available
            if field in self.term_mappings:
                terms = [
                    self.term_mappings[field].get(term, term)
                    for term in terms
                ]

            # Filter to only medical terms and standardize them
            medical_terms = self.filter_and_standardize_medical_terms(terms, field)

            # Remove duplicates while preserving order
            seen = set()
            unique_terms = []
            for term in medical_terms:
                if term not in seen:
                    seen.add(term)
                    unique_terms.append(term)

            # Format as comma-separated
            processed_row[field] = ', '.join(unique_terms) if unique_terms else ''

        return processed_row

    def preprocess_csv(
        self,
        input_path: Path,
        output_path: Path,
        year_filter: Optional[Set[int]] = None,
        encodings: Optional[List[str]] = None,
    ):
        """
        Preprocess an entire CSV file.

        Args:
            input_path: Input CSV path
            output_path: Output CSV path
            year_filter: Years to include
            encodings: Encodings to try
        """
        if encodings is None:
            encodings = ['utf-8', 'utf-8-sig', 'cp1252', 'latin1']

        print(f"[INFO] Preprocessing {input_path.name} -> {output_path.name}")

        rows_written = 0
        rows_filtered = 0

        # Get first row to determine fieldnames
        first_row = None
        for row in self.read_csv_with_encoding(input_path, encodings):
            first_row = row
            break

        if not first_row:
            print("[ERROR] Could not read input CSV")
            return

        fieldnames = list(first_row.keys())

        # Write preprocessed data
        with output_path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in self.read_csv_with_encoding(input_path, encodings):
                # Apply year filter
                if year_filter is not None:
                    year_str = row.get('YEAR', '').strip()
                    if year_str:
                        try:
                            year = int(float(year_str))
                            if year not in year_filter:
                                rows_filtered += 1
                                continue
                        except ValueError:
                            pass

                # Preprocess row
                processed_row = self.preprocess_row(row)
                writer.writerow(processed_row)
                rows_written += 1

                if rows_written % 10000 == 0:
                    print(f"  Written {rows_written:,} rows...")

        print(f"[INFO] Wrote {rows_written:,} rows (filtered {rows_filtered:,} by year)")

    def save_term_mappings(self, output_path: Path):
        """
        Save term standardization mappings to JSON.

        Args:
            output_path: Output JSON path
        """
        print(f"[INFO] Saving term mappings to {output_path.name}")

        output_data = {
            'field_stats': dict(self.field_stats),
            'term_mappings': self.term_mappings,
        }

        with output_path.open('w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        print(f"[OK] Saved term mappings")

    def load_term_mappings(self, input_path: Path):
        """
        Load term standardization mappings from JSON.

        Args:
            input_path: Input JSON path
        """
        print(f"[INFO] Loading term mappings from {input_path.name}")

        with input_path.open('r', encoding='utf-8') as f:
            data = json.load(f)

        self.field_stats = defaultdict(lambda: defaultdict(int), data.get('field_stats', {}))
        self.term_mappings = data.get('term_mappings', {})

        print(f"[OK] Loaded term mappings for {len(self.term_mappings)} fields")

    def print_statistics(self):
        """Print preprocessing statistics."""
        print("\n=== Preprocessing Statistics ===\n")

        for field in TEXT_FIELDS:
            if field not in self.field_stats:
                continue

            stats = self.field_stats[field]
            total = stats.get('empty', 0) + stats.get('non_empty', 0)

            if total == 0:
                continue

            print(f"{field}:")
            print(f"  Total records: {total:,}")
            print(f"  Non-empty: {stats.get('non_empty', 0):,} ({stats.get('non_empty', 0)/total*100:.1f}%)")
            print(f"  Empty: {stats.get('empty', 0):,} ({stats.get('empty', 0)/total*100:.1f}%)")

            if field in self.term_mappings:
                print(f"  Standardization mappings: {len(self.term_mappings[field]):,}")
            print()


if __name__ == "__main__":
    # Example usage
    from pathlib import Path

    data_dir = Path(__file__).resolve().parents[2] / "data" / "subsample"
    csv_path = data_dir / "devVAERSDATA.csv"

    if not csv_path.exists():
        print(f"[ERROR] CSV file not found: {csv_path}")
        exit(1)

    # Create preprocessor
    preprocessor = VAERSPreprocessor(
        use_lemmatization=True,
        min_term_frequency=3,
        similarity_threshold=0.85,
    )

    # Extract terms
    field_frequencies = preprocessor.extract_field_terms(csv_path)

    # Build standardization maps
    preprocessor.build_standardization_maps(field_frequencies)

    # Print stats
    preprocessor.print_statistics()

    # Save mappings
    output_mappings = data_dir / "term_mappings.json"
    preprocessor.save_term_mappings(output_mappings)

    print("\n[OK] Preprocessing analysis complete")
