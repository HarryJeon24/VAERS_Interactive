#!/usr/bin/env python3
"""
Example usage of the VAERS preprocessing pipeline.
This script demonstrates how to use the preprocessing tools programmatically.
"""
from __future__ import annotations

from pathlib import Path
from preprocess_pipeline import VAERSPreprocessor
from text_normalizer import TextNormalizer
from medical_terms_dict import (
    standardize_medication,
    standardize_condition,
    standardize_allergy,
    standardize_vaccine,
)


def example_1_text_normalization():
    """Example 1: Basic text normalization."""
    print("=== Example 1: Text Normalization ===\n")

    normalizer = TextNormalizer(use_lemmatization=True)

    sample_texts = {
        'OTHER_MEDS': "Patient taking Tylenol 500mg twice daily, Lipitor 10mg PO at bedtime",
        'CUR_ILL': "Hx of HTN, DM, and COPD. Experiencing URI symptoms",
        'ALLERGIES': "PCN, sulfa drugs, shellfish",
        'HISTORY': "Previous MI in 2020. CABG performed 03/15/2020. Currently on Coumadin",
    }

    for field, text in sample_texts.items():
        normalized = normalizer.normalize(text)
        terms = normalizer.extract_terms(normalized)

        print(f"{field}:")
        print(f"  Original:   {text}")
        print(f"  Normalized: {normalized}")
        print(f"  Terms:      {terms}")
        print()


def example_2_medical_dictionary():
    """Example 2: Using the medical terminology dictionary."""
    print("\n=== Example 2: Medical Dictionary ===\n")

    medications = ["tylenol", "motrin", "lipitor", "glucophage"]
    conditions = ["htn", "dm", "mi", "copd"]
    allergies = ["pcn", "sulfa", "shellfish"]
    vaccines = ["flu", "covid", "mmr"]

    print("Medication standardization:")
    for med in medications:
        print(f"  {med:15} -> {standardize_medication(med)}")

    print("\nCondition standardization:")
    for cond in conditions:
        print(f"  {cond:15} -> {standardize_condition(cond)}")

    print("\nAllergy standardization:")
    for allergy in allergies:
        print(f"  {allergy:15} -> {standardize_allergy(allergy)}")

    print("\nVaccine standardization:")
    for vaccine in vaccines:
        print(f"  {vaccine:15} -> {standardize_vaccine(vaccine)}")


def example_3_batch_processing():
    """Example 3: Batch processing with year filter."""
    print("\n=== Example 3: Batch Processing ===\n")

    # Get path to subsample data
    root = Path(__file__).resolve().parents[2]
    csv_path = root / "data" / "subsample" / "devVAERSDATA.csv"

    if not csv_path.exists():
        print(f"[SKIP] CSV file not found: {csv_path}")
        return

    # Create preprocessor
    preprocessor = VAERSPreprocessor(
        use_lemmatization=True,
        min_term_frequency=2,
        similarity_threshold=0.85,
    )

    # Extract terms (filter to 2025 only as per user's .env)
    print("Extracting terms from 2025 data...")
    field_frequencies = preprocessor.extract_field_terms(
        csv_path,
        year_filter={2025},
    )

    # Show top terms for each field
    print("\nTop 10 terms per field:")
    for field, term_freqs in field_frequencies.items():
        if not term_freqs:
            continue

        print(f"\n{field}:")
        sorted_terms = sorted(term_freqs.items(), key=lambda x: x[1], reverse=True)
        for term, freq in sorted_terms[:10]:
            print(f"  {term:20} {freq:3} occurrences")

    # Build standardization maps
    print("\n\nBuilding standardization maps...")
    standardization_maps = preprocessor.build_standardization_maps(field_frequencies)

    # Show some examples
    print("\nExample standardization mappings:")
    for field, mappings in standardization_maps.items():
        if mappings:
            print(f"\n{field} ({len(mappings)} mappings):")
            # Show first 5 mappings
            for i, (variant, standard) in enumerate(list(mappings.items())[:5]):
                print(f"  {variant} -> {standard}")
            if len(mappings) > 5:
                print(f"  ... and {len(mappings) - 5} more")


def example_4_full_workflow():
    """Example 4: Complete preprocessing workflow."""
    print("\n=== Example 4: Full Preprocessing Workflow ===\n")

    root = Path(__file__).resolve().parents[2]
    input_csv = root / "data" / "subsample" / "devVAERSDATA.csv"
    output_csv = root / "data" / "subsample" / "devVAERSDATA_preprocessed.csv"
    mappings_json = root / "data" / "subsample" / "term_mappings.json"

    if not input_csv.exists():
        print(f"[SKIP] Input CSV not found: {input_csv}")
        return

    print(f"Input:  {input_csv}")
    print(f"Output: {output_csv}")
    print(f"Mappings: {mappings_json}\n")

    # Create preprocessor
    preprocessor = VAERSPreprocessor(
        use_lemmatization=True,
        min_term_frequency=3,
        similarity_threshold=0.85,
    )

    # Step 1: Extract terms
    print("Step 1: Extracting terms...")
    field_frequencies = preprocessor.extract_field_terms(input_csv, year_filter={2025})

    # Step 2: Build standardization
    print("\nStep 2: Building standardization maps...")
    preprocessor.build_standardization_maps(field_frequencies)

    # Step 3: Save mappings
    print("\nStep 3: Saving term mappings...")
    preprocessor.save_term_mappings(mappings_json)

    # Step 4: Preprocess CSV
    print("\nStep 4: Preprocessing CSV...")
    preprocessor.preprocess_csv(input_csv, output_csv, year_filter={2025})

    # Step 5: Show statistics
    print("\n")
    preprocessor.print_statistics()

    print(f"\n[OK] Preprocessing complete!")
    print(f"  Preprocessed data saved to: {output_csv}")
    print(f"  Term mappings saved to: {mappings_json}")


def main():
    """Run all examples."""
    examples = [
        ("Text Normalization", example_1_text_normalization),
        ("Medical Dictionary", example_2_medical_dictionary),
        ("Batch Processing", example_3_batch_processing),
        ("Full Workflow", example_4_full_workflow),
    ]

    print("=" * 70)
    print("VAERS Preprocessing Pipeline - Example Usage")
    print("=" * 70)

    for i, (name, func) in enumerate(examples, 1):
        print(f"\n{'=' * 70}")
        print(f"Running Example {i}/{len(examples)}: {name}")
        print(f"{'=' * 70}")
        try:
            func()
        except Exception as e:
            print(f"\n[ERROR] Example failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
