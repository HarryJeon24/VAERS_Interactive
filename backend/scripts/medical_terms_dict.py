#!/usr/bin/env python3
"""
Curated medical terminology dictionary for VAERS data standardization.
Contains common medications, conditions, allergies, and their variants.
"""
from __future__ import annotations

from typing import Dict, List


# Common medication name variants and their standardized forms
MEDICATION_STANDARDIZATION = {
    # Pain relievers
    'ibuprofen': ['motrin', 'advil', 'nuprin'],
    'acetaminophen': ['tylenol', 'paracetamol', 'apap'],
    'aspirin': ['asa', 'acetylsalicylic acid'],
    'naproxen': ['aleve', 'naprosyn'],

    # Antibiotics
    'amoxicillin': ['amoxil', 'trimox'],
    'azithromycin': ['zithromax', 'z-pack', 'zpak'],
    'ciprofloxacin': ['cipro'],
    'doxycycline': ['vibramycin', 'doryx'],
    'penicillin': ['pen vk', 'penicillin vk'],
    'cephalexin': ['keflex'],

    # Diabetes medications
    'metformin': ['glucophage'],
    'insulin': ['humulin', 'novolin', 'lantus', 'humalog', 'novolog'],
    'glipizide': ['glucotrol'],
    'glyburide': ['diabeta', 'micronase'],

    # Blood pressure medications
    'lisinopril': ['prinivil', 'zestril'],
    'losartan': ['cozaar'],
    'amlodipine': ['norvasc'],
    'metoprolol': ['lopressor', 'toprol'],
    'atenolol': ['tenormin'],
    'hydrochlorothiazide': ['hctz', 'microzide'],

    # Cholesterol medications
    'atorvastatin': ['lipitor'],
    'simvastatin': ['zocor'],
    'rosuvastatin': ['crestor'],
    'pravastatin': ['pravachol'],

    # Antihistamines
    'diphenhydramine': ['benadryl'],
    'loratadine': ['claritin'],
    'cetirizine': ['zyrtec'],
    'fexofenadine': ['allegra'],

    # Acid reducers
    'omeprazole': ['prilosec'],
    'pantoprazole': ['protonix'],
    'esomeprazole': ['nexium'],
    'ranitidine': ['zantac'],
    'famotidine': ['pepcid'],

    # Antidepressants
    'sertraline': ['zoloft'],
    'fluoxetine': ['prozac'],
    'escitalopram': ['lexapro'],
    'citalopram': ['celexa'],
    'bupropion': ['wellbutrin'],

    # Thyroid
    'levothyroxine': ['synthroid', 'levoxyl'],

    # Blood thinners
    'warfarin': ['coumadin'],
    'apixaban': ['eliquis'],
    'rivaroxaban': ['xarelto'],

    # Asthma/COPD
    'albuterol': ['proventil', 'ventolin'],
    'fluticasone': ['flovent', 'flonase'],
    'montelukast': ['singulair'],
}


# Common medical conditions and their standardized forms
CONDITION_STANDARDIZATION = {
    # Cardiovascular
    'hypertension': ['high blood pressure', 'htn', 'elevated bp'],
    'hyperlipidemia': ['high cholesterol', 'dyslipidemia'],
    'coronary artery disease': ['cad', 'heart disease', 'coronary disease'],
    'myocardial infarction': ['mi', 'heart attack', 'myocardial infarction'],
    'congestive heart failure': ['chf', 'heart failure'],
    'atrial fibrillation': ['afib', 'a-fib'],
    'coronary artery bypass graft': ['cabg', 'bypass', 'bypass surgery', 'coronary artery bypass graft'],

    # Metabolic
    'diabetes mellitus': ['diabetes', 'dm', 'diabetic'],
    'type 2 diabetes': ['t2dm', 'type ii diabetes', 'niddm'],
    'type 1 diabetes': ['t1dm', 'type i diabetes', 'iddm'],
    'hypothyroidism': ['underactive thyroid', 'low thyroid'],
    'hyperthyroidism': ['overactive thyroid', 'high thyroid'],

    # Respiratory
    'asthma': ['reactive airway disease', 'rad'],
    'chronic obstructive pulmonary disease': ['copd', 'emphysema'],
    'pneumonia': ['lung infection'],
    'upper respiratory infection': ['uri', 'common cold'],

    # Gastrointestinal
    'gastroesophageal reflux disease': ['gerd', 'acid reflux', 'reflux'],
    'irritable bowel syndrome': ['ibs'],
    'inflammatory bowel disease': ['ibd', 'crohns', 'ulcerative colitis'],

    # Mental health
    'depression': ['major depressive disorder', 'mdd'],
    'anxiety': ['generalized anxiety disorder', 'gad'],
    'bipolar disorder': ['manic depression'],
    'attention deficit hyperactivity disorder': ['adhd', 'add'],

    # Autoimmune
    'rheumatoid arthritis': ['ra'],
    'systemic lupus erythematosus': ['sle', 'lupus'],
    'multiple sclerosis': ['ms'],

    # Cardiovascular procedures/events
    'transient ischemic attack': ['tia', 'mini stroke'],
    'cerebrovascular accident': ['cva', 'stroke'],
    'pulmonary embolism': ['pe'],
    'deep vein thrombosis': ['dvt', 'blood clot'],
    'angioplasty': ['ptca', 'balloon angioplasty'],
    'cardiac catheterization': ['cardiac cath'],

    # Other common conditions
    'osteoarthritis': ['oa', 'degenerative joint disease', 'djd'],
    'chronic kidney disease': ['ckd', 'renal insufficiency'],
    'end stage renal disease': ['esrd', 'kidney failure'],
    'urinary tract infection': ['uti', 'bladder infection'],
    'migraine': ['migraine headache'],
    'seizure disorder': ['epilepsy'],
}


# Common allergy terms
ALLERGY_STANDARDIZATION = {
    'penicillin': ['pcn', 'pen'],
    'sulfa drugs': ['sulfa', 'sulfamethoxazole', 'sulfonamides'],
    'shellfish': ['shrimp', 'crab', 'lobster', 'seafood'],
    'tree nuts': ['walnuts', 'almonds', 'cashews', 'pecans'],
    'peanuts': ['peanut'],
    'eggs': ['egg'],
    'dairy': ['milk', 'lactose'],
    'gluten': ['wheat', 'celiac'],
    'latex': ['rubber'],
}


# Vaccine name standardization
VACCINE_STANDARDIZATION = {
    'influenza': ['flu', 'flu shot', 'influenza vaccine'],
    'covid-19': ['covid', 'coronavirus', 'sars-cov-2', 'mrna vaccine'],
    'pneumococcal': ['pneumonia', 'prevnar', 'pneumovax'],
    'tetanus': ['tdap', 'td', 'tetanus toxoid'],
    'measles mumps rubella': ['mmr'],
    'hepatitis b': ['hep b', 'hbv'],
    'hepatitis a': ['hep a', 'hav'],
    'varicella': ['chickenpox', 'varicella zoster'],
    'shingles': ['zoster', 'herpes zoster', 'shingrix'],
    'human papillomavirus': ['hpv', 'gardasil'],
}


def create_reverse_mapping(standardization_dict: Dict[str, List[str]]) -> Dict[str, str]:
    """
    Create a reverse mapping from variants to standard terms.

    Args:
        standardization_dict: Dictionary of standard_term -> [variants]

    Returns:
        Dictionary of variant -> standard_term
    """
    reverse_map = {}

    for standard, variants in standardization_dict.items():
        # Add the standard term itself
        reverse_map[standard] = standard

        # Add all variants
        for variant in variants:
            reverse_map[variant.lower()] = standard.lower()

    return reverse_map


# Create reverse mappings for quick lookup
MEDICATION_LOOKUP = create_reverse_mapping(MEDICATION_STANDARDIZATION)
CONDITION_LOOKUP = create_reverse_mapping(CONDITION_STANDARDIZATION)
ALLERGY_LOOKUP = create_reverse_mapping(ALLERGY_STANDARDIZATION)
VACCINE_LOOKUP = create_reverse_mapping(VACCINE_STANDARDIZATION)


def standardize_medication(term: str) -> str:
    """Standardize a medication name."""
    return MEDICATION_LOOKUP.get(term.lower(), term.lower())


def standardize_condition(term: str) -> str:
    """Standardize a medical condition."""
    return CONDITION_LOOKUP.get(term.lower(), term.lower())


def standardize_allergy(term: str) -> str:
    """Standardize an allergy term."""
    return ALLERGY_LOOKUP.get(term.lower(), term.lower())


def standardize_vaccine(term: str) -> str:
    """Standardize a vaccine name."""
    return VACCINE_LOOKUP.get(term.lower(), term.lower())


def get_all_lookups() -> Dict[str, Dict[str, str]]:
    """
    Get all standardization lookups.

    Returns:
        Dictionary with lookup tables for each field type
    """
    return {
        'medications': MEDICATION_LOOKUP,
        'conditions': CONDITION_LOOKUP,
        'allergies': ALLERGY_LOOKUP,
        'vaccines': VACCINE_LOOKUP,
    }


if __name__ == "__main__":
    # Test the standardization
    print("=== Medical Term Standardization Examples ===\n")

    test_meds = ['tylenol', 'motrin', 'zithromax', 'lipitor']
    print("Medications:")
    for med in test_meds:
        print(f"  {med} -> {standardize_medication(med)}")

    test_conditions = ['htn', 'diabetes', 'copd', 'afib']
    print("\nConditions:")
    for cond in test_conditions:
        print(f"  {cond} -> {standardize_condition(cond)}")

    test_allergies = ['pcn', 'sulfa', 'shellfish']
    print("\nAllergies:")
    for allergy in test_allergies:
        print(f"  {allergy} -> {standardize_allergy(allergy)}")

    test_vaccines = ['flu', 'covid', 'mmr', 'shingrix']
    print("\nVaccines:")
    for vaccine in test_vaccines:
        print(f"  {vaccine} -> {standardize_vaccine(vaccine)}")

    print(f"\nTotal standardization mappings:")
    print(f"  Medications: {len(MEDICATION_LOOKUP)}")
    print(f"  Conditions: {len(CONDITION_LOOKUP)}")
    print(f"  Allergies: {len(ALLERGY_LOOKUP)}")
    print(f"  Vaccines: {len(VACCINE_LOOKUP)}")
