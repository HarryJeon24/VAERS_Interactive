#!/usr/bin/env python3
"""
Create MongoDB indexes for VAERS database collections.
This improves query performance for commonly filtered fields.

Run this script after loading data:
    python backend/db/indexes.py
"""
from __future__ import annotations

import os
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "vaers_dev")


def create_indexes():
    """Create indexes on VAERS collections for better query performance."""
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]

    print(f"Creating indexes on database: {MONGO_DB}")

    # vaers_data collection indexes
    print("\n[vaers_data] Creating indexes...")
    vaers_data = db["vaers_data"]

    # Primary identifier
    vaers_data.create_index([("VAERS_ID", ASCENDING)], unique=True, name="idx_vaers_id")

    # Common filter fields
    vaers_data.create_index([("YEAR", ASCENDING)], name="idx_year")
    vaers_data.create_index([("STATE", ASCENDING)], name="idx_state")
    vaers_data.create_index([("SEX", ASCENDING)], name="idx_sex")
    vaers_data.create_index([("AGE_YRS", ASCENDING)], name="idx_age_yrs")
    vaers_data.create_index([("ONSET_DATE", ASCENDING)], name="idx_onset_date")

    # Serious outcome flags (for filtering)
    vaers_data.create_index([("DIED", ASCENDING)], name="idx_died")
    vaers_data.create_index([("HOSPITAL", ASCENDING)], name="idx_hospital")
    vaers_data.create_index([("L_THREAT", ASCENDING)], name="idx_l_threat")
    vaers_data.create_index([("DISABLE", ASCENDING)], name="idx_disable")
    vaers_data.create_index([("BIRTH_DEFECT", ASCENDING)], name="idx_birth_defect")

    # Compound indexes for common query patterns
    vaers_data.create_index(
        [("YEAR", ASCENDING), ("STATE", ASCENDING)],
        name="idx_year_state"
    )
    vaers_data.create_index(
        [("YEAR", ASCENDING), ("VAERS_ID", ASCENDING)],
        name="idx_year_vaers_id"
    )

    print(f"  Created {len(vaers_data.index_information())} indexes on vaers_data")

    # vaers_vax collection indexes
    print("\n[vaers_vax] Creating indexes...")
    vaers_vax = db["vaers_vax"]

    # Foreign key for joins
    vaers_vax.create_index([("VAERS_ID", ASCENDING)], name="idx_vaers_id")

    # Vaccine filter fields
    vaers_vax.create_index([("VAX_TYPE", ASCENDING)], name="idx_vax_type")
    vaers_vax.create_index([("VAX_MANU", ASCENDING)], name="idx_vax_manu")

    # Compound index for common vaccine queries
    vaers_vax.create_index(
        [("VAX_TYPE", ASCENDING), ("VAX_MANU", ASCENDING)],
        name="idx_vax_type_manu"
    )
    vaers_vax.create_index(
        [("VAERS_ID", ASCENDING), ("VAX_TYPE", ASCENDING)],
        name="idx_vaers_id_vax_type"
    )

    print(f"  Created {len(vaers_vax.index_information())} indexes on vaers_vax")

    # vaers_symptoms collection indexes
    print("\n[vaers_symptoms] Creating indexes...")
    vaers_symptoms = db["vaers_symptoms"]

    # Foreign key for joins
    vaers_symptoms.create_index([("VAERS_ID", ASCENDING)], name="idx_vaers_id")

    # Symptom term fields (SYMPTOM1-5 are the most commonly queried)
    vaers_symptoms.create_index([("SYMPTOM1", ASCENDING)], name="idx_symptom1")
    vaers_symptoms.create_index([("SYMPTOM2", ASCENDING)], name="idx_symptom2")
    vaers_symptoms.create_index([("SYMPTOM3", ASCENDING)], name="idx_symptom3")
    vaers_symptoms.create_index([("SYMPTOM4", ASCENDING)], name="idx_symptom4")
    vaers_symptoms.create_index([("SYMPTOM5", ASCENDING)], name="idx_symptom5")

    print(f"  Created {len(vaers_symptoms.index_information())} indexes on vaers_symptoms")

    print("\n All indexes created successfully!")
    print("\nTo view indexes, run:")
    print(f"  db.vaers_data.getIndexes()")
    print(f"  db.vaers_vax.getIndexes()")
    print(f"  db.vaers_symptoms.getIndexes()")

    client.close()


if __name__ == "__main__":
    create_indexes()
