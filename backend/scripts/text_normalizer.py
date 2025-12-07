#!/usr/bin/env python3
"""
Text normalization utilities for VAERS data preprocessing.
Handles medical text cleaning, lemmatization, and term standardization.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Set, Optional
import string


class TextNormalizer:
    """
    Normalizes medical text fields by:
    1. Cleaning and standardizing text
    2. Extracting medical terms
    3. Lemmatizing words
    4. Creating unified term mappings
    """

    def __init__(self, use_lemmatization: bool = True):
        """
        Initialize the text normalizer.

        Args:
            use_lemmatization: Whether to use lemmatization (requires nltk)
        """
        self.use_lemmatization = use_lemmatization
        self.lemmatizer = None
        self.stopwords = self._get_medical_stopwords()

        # Common medical abbreviations and their expansions
        self.medical_abbrevs = self._get_medical_abbreviations()

        # Dose-related patterns to remove (as requested)
        self.dose_patterns = [
            r'\d+\s*mg\b',
            r'\d+\s*mcg\b',
            r'\d+\s*ml\b',
            r'\d+\s*units?\b',
            r'\d+\s*tabs?\b',
            r'\d+\s*capsules?\b',
            r'dose\s*\d+',
            r'q\d+h',  # q6h, q12h, etc.
        ]

        # Date patterns to remove (as requested)
        self.date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # MM/DD/YYYY
            r'\d{4}-\d{2}-\d{2}',          # YYYY-MM-DD
            r'\b\d{1,2}-[A-Za-z]{3}-\d{4}\b',  # DD-Mon-YYYY
        ]

        # Patterns for "none/unknown" detection
        self.none_patterns = self._get_none_patterns()

        if use_lemmatization:
            self._init_lemmatizer()

    def _init_lemmatizer(self):
        """Initialize NLTK lemmatizer (lazy load)."""
        try:
            import nltk
            from nltk.stem import WordNetLemmatizer

            # Try to use wordnet, download if needed
            try:
                nltk.data.find('corpora/wordnet')
            except LookupError:
                print("[INFO] Downloading NLTK wordnet...")
                nltk.download('wordnet', quiet=True)
                nltk.download('omw-1.4', quiet=True)

            self.lemmatizer = WordNetLemmatizer()
        except ImportError:
            print("[WARN] NLTK not installed. Lemmatization disabled.")
            print("[WARN] Install with: pip install nltk")
            self.use_lemmatization = False

    def _get_medical_stopwords(self) -> Set[str]:
        """Return medical-specific stopwords to filter out."""
        return {
            'reported', 'provided', 'administered', 'given',
            'patient', 'subject', 'individual', 'hcp',
            'lot', 'batch', 'number', 'exp', 'expiration',
        }

    def _get_none_patterns(self) -> List[str]:
        """Return patterns that indicate empty/no information."""
        return [
            r'\bnone\b',
            r'\bno\b',
            r'\bunk\b',
            r'\bunknown\b',
            r'\bn/a\b',
            r'\bna\b',
            r'\bnot\s+known\b',
            r'\bnone\s+known\b',
            r'\bno\s+known\b',
            r'\bnkda\b',  # no known drug allergies
            r'\bnone\s+reported\b',
            r'\bnot\s+reported\b',
            r'\bnot\s+provided\b',
        ]

    def _get_medical_abbreviations(self) -> Dict[str, str]:
        """Common medical abbreviations and their expansions."""
        return {
            'hx': 'history',
            'dx': 'diagnosis',
            'tx': 'treatment',
            'rx': 'prescription',
            'sx': 'symptoms',
            'pt': 'patient',
            'hcp': 'healthcare provider',
            'er': 'emergency room',
            'icu': 'intensive care unit',
            'prn': 'as needed',
            'bid': 'twice daily',
            'tid': 'three times daily',
            'qid': 'four times daily',
            'po': 'by mouth',
            'iv': 'intravenous',
            'im': 'intramuscular',
            'sq': 'subcutaneous',
            'sc': 'subcutaneous',
            'adhd': 'attention deficit hyperactivity disorder',
            'copd': 'chronic obstructive pulmonary disease',
            'dm': 'diabetes mellitus',
            'htn': 'hypertension',
            'mi': 'myocardial infarction',
            'cvd': 'cardiovascular disease',
            'cad': 'coronary artery disease',
            'chf': 'congestive heart failure',
            'afib': 'atrial fibrillation',
            'a-fib': 'atrial fibrillation',
            'cabg': 'coronary artery bypass graft',
            'gerd': 'gastroesophageal reflux disease',
            'uti': 'urinary tract infection',
            'uri': 'upper respiratory infection',
            'gi': 'gastrointestinal',
            'ckd': 'chronic kidney disease',
            'esrd': 'end stage renal disease',
            'ra': 'rheumatoid arthritis',
            'oa': 'osteoarthritis',
            'sle': 'systemic lupus erythematosus',
            'ms': 'multiple sclerosis',
            'tia': 'transient ischemic attack',
            'cva': 'cerebrovascular accident',
            'pe': 'pulmonary embolism',
            'dvt': 'deep vein thrombosis',
        }

    def clean_text(self, text: Optional[str]) -> str:
        """
        Clean and normalize text.

        Args:
            text: Raw text input

        Returns:
            Cleaned text string
        """
        if not text or text.strip() == '':
            return ''

        text = str(text)

        # Remove dose information (as requested)
        for pattern in self.dose_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # Remove dates (as requested)
        for pattern in self.date_patterns:
            text = re.sub(pattern, '', text)

        # Convert to lowercase
        text = text.lower()

        # Expand common medical abbreviations
        for abbrev, expansion in self.medical_abbrevs.items():
            text = re.sub(r'\b' + abbrev + r'\b', expansion, text)

        # Remove URLs, emails
        text = re.sub(r'http\S+|www\.\S+', '', text)
        text = re.sub(r'\S+@\S+', '', text)

        # Remove lot numbers, case IDs, etc.
        text = re.sub(r'lot\s*#?\s*[A-Z0-9]+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'case\s*#?\s*[A-Z0-9-]+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'us-\w+-\w+', '', text, flags=re.IGNORECASE)

        # Remove extra punctuation but keep hyphens in compound terms
        text = re.sub(r'[^\w\s-]', ' ', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def lemmatize_text(self, text: str) -> str:
        """
        Lemmatize text to base forms.

        Args:
            text: Cleaned text

        Returns:
            Lemmatized text
        """
        if not self.use_lemmatization or not self.lemmatizer:
            return text

        words = text.split()
        lemmatized = [self.lemmatizer.lemmatize(word) for word in words]
        return ' '.join(lemmatized)

    def extract_terms(self, text: str, min_length: int = 3) -> List[str]:
        """
        Extract meaningful medical terms from text.

        Args:
            text: Cleaned text
            min_length: Minimum term length

        Returns:
            List of extracted terms
        """
        if not text:
            return []

        # Split on whitespace
        words = text.split()

        # Filter stopwords and short terms
        terms = [
            word for word in words
            if len(word) >= min_length
            and word not in self.stopwords
            and not word.isdigit()
        ]

        return terms

    def is_none_text(self, text: Optional[str]) -> bool:
        """
        Check if text indicates no information (none, unknown, etc.).

        Args:
            text: Text to check

        Returns:
            True if text indicates no information
        """
        if not text or text.strip() == '':
            return True

        text_lower = text.lower().strip()

        # Check for exact matches
        if text_lower in ['none', 'no', 'unk', 'unknown', 'n/a', 'na', 'nkda']:
            return True

        # Check patterns
        for pattern in self.none_patterns:
            if re.search(pattern, text_lower):
                # Make sure it's not part of a longer medical term
                # Check if the entire cleaned text is just the "none" phrase
                cleaned_words = re.sub(r'[^\w\s]', ' ', text_lower).split()
                none_words = {'none', 'no', 'unk', 'unknown', 'na', 'not', 'known', 'reported', 'provided', 'nkda', 'allergies', 'allergy', 'drug', 'drugs', 'medication', 'medications', 'history', 'illness'}
                # If most words are "none" indicators, consider it empty
                if len(cleaned_words) > 0:
                    none_count = sum(1 for word in cleaned_words if word in none_words)
                    if none_count >= len(cleaned_words) * 0.7:  # 70% threshold
                        return True

        return False

    def normalize(self, text: Optional[str]) -> str:
        """
        Full normalization pipeline.

        Args:
            text: Raw text

        Returns:
            Fully normalized text
        """
        if not text:
            return ''

        # Clean
        cleaned = self.clean_text(text)

        # Lemmatize
        if self.use_lemmatization:
            cleaned = self.lemmatize_text(cleaned)

        return cleaned

    def extract_unique_terms(self, texts: List[str], min_frequency: int = 2) -> Dict[str, int]:
        """
        Extract unique terms from a list of texts with frequency counts.

        Args:
            texts: List of text strings
            min_frequency: Minimum frequency for a term to be included

        Returns:
            Dictionary of term -> frequency
        """
        all_terms = []

        for text in texts:
            normalized = self.normalize(text)
            terms = self.extract_terms(normalized)
            all_terms.extend(terms)

        # Count frequencies
        term_counts = Counter(all_terms)

        # Filter by minimum frequency
        return {
            term: count
            for term, count in term_counts.items()
            if count >= min_frequency
        }


def create_term_standardization_map(
    term_frequencies: Dict[str, int],
    similarity_threshold: float = 0.85
) -> Dict[str, str]:
    """
    Create a mapping of variant terms to standardized terms.
    Uses fuzzy matching to group similar terms.

    Args:
        term_frequencies: Dictionary of term -> frequency
        similarity_threshold: Similarity threshold for matching (0-1)

    Returns:
        Dictionary mapping variant -> standard term
    """
    try:
        from difflib import SequenceMatcher
    except ImportError:
        print("[WARN] difflib not available. Skipping fuzzy matching.")
        return {}

    # Sort terms by frequency (most common first)
    sorted_terms = sorted(term_frequencies.items(), key=lambda x: x[1], reverse=True)

    standardization_map = {}
    processed = set()

    for term, freq in sorted_terms:
        if term in processed:
            continue

        # This term becomes the standard
        standard_term = term
        processed.add(term)

        # Find similar terms
        for other_term, other_freq in sorted_terms:
            if other_term in processed:
                continue

            # Calculate similarity
            similarity = SequenceMatcher(None, term, other_term).ratio()

            if similarity >= similarity_threshold:
                standardization_map[other_term] = standard_term
                processed.add(other_term)

    return standardization_map


if __name__ == "__main__":
    # Test the normalizer
    normalizer = TextNormalizer(use_lemmatization=True)

    test_texts = [
        "Patient taking Ibuprofen 200mg twice daily, Lisinopril 10mg PO daily",
        "Hx of HTN, DM, COPD. Current meds: metformin 500mg BID",
        "allergies: penicillin, sulfa drugs. Previous vax: influenza 10/15/2023",
        "No known drug allergies. Lab data from 01/15/2024 shows elevated WBC",
    ]

    print("=== Text Normalization Examples ===\n")
    for text in test_texts:
        normalized = normalizer.normalize(text)
        terms = normalizer.extract_terms(normalized)
        print(f"Original: {text}")
        print(f"Normalized: {normalized}")
        print(f"Terms: {terms}")
        print()
