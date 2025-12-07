# VAERS Text Preprocessing Pipeline

This preprocessing pipeline standardizes text fields in VAERS data to create unified terminology across datasets.

## Overview

The pipeline processes the following text fields:
- `LAB_DATA` - Laboratory data
- `OTHER_MEDS` - Other medications
- `CUR_ILL` - Current illness
- `HISTORY` - Medical history
- `PRIOR_VAX` - Prior vaccinations
- `ALLERGIES` - Known allergies

## Features

✅ **Text Normalization**: Lowercase, remove special characters, expand abbreviations
✅ **Dose & Date Removal**: Automatically removes dosage and date information
✅ **Lemmatization**: Converts words to base forms (requires NLTK)
✅ **Term Standardization**: Maps similar terms to standard forms
✅ **Medical Dictionary**: Curated list of common medical terms
✅ **Year Filtering**: Process specific years or year ranges
✅ **Encoding Support**: Handles multiple CSV encodings (UTF-8, CP1252, etc.)

## Installation

Install required dependencies:

```bash
pip install nltk
```

The pipeline will automatically download required NLTK data on first run.

## Usage

### 1. Analyze Data and Build Term Mappings

Analyze your data to extract terms and build standardization mappings:

```bash
# Analyze subsample data
python run_preprocessing.py analyze --input ../../data/subsample/devVAERSDATA.csv

# Analyze specific years only
python run_preprocessing.py analyze --input ../../data/subsample/devVAERSDATA.csv --years 2023,2024,2025

# Analyze year range
python run_preprocessing.py analyze --input ../../data/raw/VAERSDATA.csv --years 2020-2024

# Custom output location
python run_preprocessing.py analyze --input ../../data/subsample/devVAERSDATA.csv --output ../../data/my_mappings.json
```

This will:
- Extract all terms from text fields
- Count term frequencies
- Build standardization mappings for similar terms
- Save mappings to JSON file

### 2. Preprocess Data Using Saved Mappings

Apply preprocessing to data using previously generated mappings:

```bash
# Preprocess data
python run_preprocessing.py preprocess \
    --input ../../data/raw/2024VAERSDATA.csv \
    --output ../../data/processed/2024VAERSDATA_clean.csv \
    --mappings ../../data/term_mappings.json

# Preprocess with year filter
python run_preprocessing.py preprocess \
    --input ../../data/raw/VAERSDATA.csv \
    --output ../../data/processed/2024VAERSDATA_clean.csv \
    --mappings ../../data/term_mappings.json \
    --years 2024
```

### 3. Full Pipeline (Analyze + Preprocess)

Run both steps in one command:

```bash
# Full pipeline
python run_preprocessing.py full \
    --input ../../data/subsample/devVAERSDATA.csv \
    --output ../../data/processed/devVAERSDATA_clean.csv

# With year filter
python run_preprocessing.py full \
    --input ../../data/subsample/devVAERSDATA.csv \
    --output ../../data/processed/devVAERSDATA_clean.csv \
    --years 2023,2024,2025

# Adjust similarity threshold for term matching
python run_preprocessing.py full \
    --input ../../data/subsample/devVAERSDATA.csv \
    --output ../../data/processed/devVAERSDATA_clean.csv \
    --similarity 0.90
```

## Command Reference

### Common Options

- `--input`, `-i`: Input CSV file path (required)
- `--output`, `-o`: Output file path
- `--years`, `-y`: Comma-separated years or ranges (e.g., "2023,2024" or "2020-2024")
- `--no-lemmatization`: Disable lemmatization (faster, less normalization)
- `--encodings`: Encodings to try (default: "utf-8,cp1252,latin1")

### Analyze-Specific Options

- `--min-freq`: Minimum term frequency (default: 3)
- `--similarity`: Similarity threshold for term matching (default: 0.85)

### Preprocess-Specific Options

- `--mappings`, `-m`: Path to term mappings JSON file (required)

## Examples

### Example 1: Process All Years

```bash
# Build mappings from all data
python run_preprocessing.py analyze --input ../../data/subsample/devVAERSDATA.csv

# Apply to full dataset
python run_preprocessing.py preprocess \
    --input ../../data/raw/VAERSDATA_FULL.csv \
    --output ../../data/processed/VAERSDATA_FULL_clean.csv \
    --mappings ../../data/subsample/term_mappings.json
```

### Example 2: Process Specific Year

```bash
# Process only 2024 data
python run_preprocessing.py full \
    --input ../../data/raw/2024VAERSDATA.csv \
    --output ../../data/processed/2024VAERSDATA_clean.csv \
    --years 2024
```

### Example 3: Process Year Range

```bash
# Process 2020-2024 data
python run_preprocessing.py full \
    --input ../../data/raw/VAERSDATA.csv \
    --output ../../data/processed/VAERSDATA_2020_2024_clean.csv \
    --years 2020-2024
```

### Example 4: Custom Parameters

```bash
# High similarity threshold, high minimum frequency
python run_preprocessing.py analyze \
    --input ../../data/subsample/devVAERSDATA.csv \
    --min-freq 10 \
    --similarity 0.95
```

## Output Files

### Preprocessed CSV
The output CSV has the same structure as input, but with normalized text fields:
- Cleaned and standardized terminology
- Removed dosage and date information
- Lemmatized terms
- Applied standardization mappings

### Term Mappings JSON
The mappings file contains:
- `field_stats`: Statistics for each text field (empty vs non-empty counts)
- `term_mappings`: Standardization mappings for each field

Example:
```json
{
  "field_stats": {
    "OTHER_MEDS": {
      "empty": 1234,
      "non_empty": 5678
    }
  },
  "term_mappings": {
    "OTHER_MEDS": {
      "motrin": "ibuprofen",
      "tylenol": "acetaminophen"
    }
  }
}
```

## Advanced Usage

### Using Medical Terms Dictionary

The pipeline includes a curated medical terminology dictionary (`medical_terms_dict.py`) with standardized names for:
- Common medications (e.g., Tylenol → acetaminophen)
- Medical conditions (e.g., HTN → hypertension)
- Allergies (e.g., PCN → penicillin)
- Vaccines (e.g., flu → influenza)

To use it programmatically:

```python
from medical_terms_dict import standardize_medication, standardize_condition

# Standardize medication names
med = standardize_medication("tylenol")  # Returns "acetaminophen"

# Standardize conditions
condition = standardize_condition("htn")  # Returns "hypertension"
```

### Programmatic Usage

```python
from preprocess_pipeline import VAERSPreprocessor

# Create preprocessor
preprocessor = VAERSPreprocessor(
    use_lemmatization=True,
    min_term_frequency=3,
    similarity_threshold=0.85
)

# Extract terms from CSV
field_frequencies = preprocessor.extract_field_terms(
    csv_path,
    year_filter={2023, 2024}
)

# Build mappings
preprocessor.build_standardization_maps(field_frequencies)

# Save mappings
preprocessor.save_term_mappings(output_path)

# Preprocess CSV
preprocessor.preprocess_csv(input_path, output_path, year_filter={2024})
```

## Performance Tips

1. **Disable lemmatization** for faster processing (use `--no-lemmatization`)
2. **Increase minimum frequency** to reduce term count (use `--min-freq 5` or higher)
3. **Use year filters** to process smaller subsets
4. **Generate mappings once** and reuse for multiple datasets

## Troubleshooting

### NLTK Download Issues
If NLTK data download fails, manually download:
```python
import nltk
nltk.download('wordnet')
nltk.download('omw-1.4')
```

### Encoding Errors
If CSV reading fails, try specifying encodings:
```bash
python run_preprocessing.py analyze --input file.csv --encodings "cp1252,latin1,utf-8"
```

### Memory Issues
For very large files:
- Process year-by-year instead of all at once
- Increase system swap space
- Use a machine with more RAM

## Files

- `text_normalizer.py` - Core text normalization utilities
- `preprocess_pipeline.py` - Main preprocessing pipeline
- `run_preprocessing.py` - CLI tool (this is what you run)
- `medical_terms_dict.py` - Curated medical terminology dictionary
- `README_preprocessing.md` - This documentation

## License

Part of the VAERS Interactive project.
