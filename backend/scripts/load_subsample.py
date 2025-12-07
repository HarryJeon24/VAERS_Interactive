#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection


# ----------------------------
# Paths + env
# ----------------------------

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data" / "subsample"
DATA_PROCESSED = ROOT / "data" / "processed"
CSV_DATA = DATA_PROCESSED / "devVAERSDATA_clean.csv"
CSV_VAX  = DATA_DIR / "devVAERSVAX.csv"
CSV_SYM  = DATA_DIR / "devVAERSSYMPTOMS.csv"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB", "vaers_dev")

# Try encodings in this order (matches your earlier fix)
ENCODINGS = [os.getenv("VAERS_CSV_ENCODING", "").strip(), "utf-8", "utf-8-sig", "cp1252", "latin1"]
ENCODINGS = [e for e in ENCODINGS if e]


# ----------------------------
# Helpers
# ----------------------------

def read_csv_rows(path: Path) -> Iterable[Dict[str, str]]:
    """
    Stream CSV rows as dicts with encoding fallback.
    """
    last_err: Optional[Exception] = None
    for enc in ENCODINGS:
        try:
            with path.open("r", newline="", encoding=enc, errors="strict") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    yield row
            return
        except UnicodeDecodeError as e:
            last_err = e

    # last resort: latin1 replace
    with path.open("r", newline="", encoding="latin1", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def to_int(x: str) -> Optional[int]:
    x = (x or "").strip()
    if x == "":
        return None
    try:
        return int(float(x))
    except ValueError:
        return None


def to_float(x: str) -> Optional[float]:
    x = (x or "").strip()
    if x == "":
        return None
    try:
        return float(x)
    except ValueError:
        return None


def to_date_mmddyyyy(x: str) -> Optional[datetime]:
    """
    VAERS dates are typically MM/DD/YYYY in the CSVs. Handle blanks safely.
    """
    x = (x or "").strip()
    if not x:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(x, fmt)
        except ValueError:
            pass
    return None


def normalize_row(row: Dict[str, str]) -> Dict:
    """
    Minimal normalization:
    - VAERS_ID as int
    - YEAR as int (if present)
    - Common numeric/date fields parsed when encountered
    Everything else stored as raw strings (fine for dev).
    """
    doc: Dict = {}

    for k, v in row.items():
        if k is None:
            continue
        key = k.strip()
        val = (v or "").strip()

        if key == "VAERS_ID":
            doc["VAERS_ID"] = to_int(val)
        elif key == "YEAR":
            doc["YEAR"] = to_int(val)
        elif key in ("AGE_YRS", "NUMDAYS"):
            doc[key] = to_float(val)
        elif key in ("VAX_DATE", "ONSET_DATE", "RECVDATE", "RPT_DATE", "DATEDIED"):
            doc[key] = to_date_mmddyyyy(val)
        else:
            doc[key] = val if val != "" else None

    return doc


def bulk_upsert(
    coll: Collection,
    docs: Iterable[Dict],
    key_fields=("VAERS_ID",),
    batch_size: int = 2000,
) -> int:
    """
    Upsert docs in batches by compound key_fields.
    Returns total operations executed.
    """
    ops = []
    total = 0

    for d in docs:
        # build filter by key_fields
        filt = {k: d.get(k) for k in key_fields}
        if any(v is None for v in filt.values()):
            continue

        ops.append(UpdateOne(filt, {"$set": d}, upsert=True))

        if len(ops) >= batch_size:
            res = coll.bulk_write(ops, ordered=False)
            total += res.inserted_count + res.modified_count + res.upserted_count
            ops = []

    if ops:
        res = coll.bulk_write(ops, ordered=False)
        total += res.inserted_count + res.modified_count + res.upserted_count

    return total


# ----------------------------
# Main load
# ----------------------------

def main():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]

    c_data = db["vaers_data"]
    c_vax  = db["vaers_vax"]
    c_sym  = db["vaers_symptoms"]

    # Optional: reset collections for clean dev runs
    for c in (c_data, c_vax, c_sym):
        c.drop()

    print(f"[INFO] Loading into DB='{MONGO_DB}' at {MONGO_URI}")

    # DATA: one row per report (VAERS_ID)
    print(f"[INFO] Loading {CSV_DATA.name} -> vaers_data")
    data_docs = (normalize_row(r) for r in read_csv_rows(CSV_DATA))
    n1 = bulk_upsert(c_data, data_docs, key_fields=("VAERS_ID",), batch_size=2000)
    print(f"[OK] vaers_data upserts: {n1:,}")

    # VAX: multiple rows per VAERS_ID; use (VAERS_ID, VAX_TYPE, VAX_MANU, VAX_NAME, VAX_LOT) as a practical key
    # (VAERS doesn’t provide an explicit row id; this is fine for dev.)
    print(f"[INFO] Loading {CSV_VAX.name} -> vaers_vax")
    vax_docs = (normalize_row(r) for r in read_csv_rows(CSV_VAX))
    n2 = bulk_upsert(c_vax, vax_docs, key_fields=("VAERS_ID", "VAX_TYPE", "VAX_MANU", "VAX_NAME", "VAX_LOT"), batch_size=3000)
    print(f"[OK] vaers_vax upserts: {n2:,}")

    # SYMPTOMS: multiple rows per VAERS_ID; each row contains SYMPTOM1-5; practical key includes those fields
    print(f"[INFO] Loading {CSV_SYM.name} -> vaers_symptoms")
    sym_docs = (normalize_row(r) for r in read_csv_rows(CSV_SYM))
    n3 = bulk_upsert(c_sym, sym_docs, key_fields=("VAERS_ID", "SYMPTOM1", "SYMPTOM2", "SYMPTOM3", "SYMPTOM4", "SYMPTOM5"), batch_size=3000)
    print(f"[OK] vaers_symptoms upserts: {n3:,}")

    # Indexes (dev-friendly)
    print("[INFO] Creating indexes...")
    c_data.create_index([("VAERS_ID", 1)], unique=True)
    c_data.create_index([("YEAR", 1)])
    c_data.create_index([("STATE", 1)])
    c_data.create_index([("SEX", 1)])
    c_data.create_index([("AGE_YRS", 1)])
    c_data.create_index([("ONSET_DATE", 1)])
    c_data.create_index([("RECVDATE", 1)])

    c_vax.create_index([("VAERS_ID", 1)])
    c_vax.create_index([("YEAR", 1)])
    c_vax.create_index([("VAX_TYPE", 1)])
    c_vax.create_index([("VAX_MANU", 1)])
    c_vax.create_index([("VAX_DOSE_SERIES", 1)])
    c_vax.create_index([("VAX_DATE", 1)])

    c_sym.create_index([("VAERS_ID", 1)])
    c_sym.create_index([("YEAR", 1)])
    c_sym.create_index([("SYMPTOM1", 1)])
    c_sym.create_index([("SYMPTOM_TEXT", "text")])  # optional (can be heavy)

    print("[OK] Done. Quick counts:")
    print("  vaers_data     =", c_data.estimated_document_count())
    print("  vaers_vax      =", c_vax.estimated_document_count())
    print("  vaers_symptoms =", c_sym.estimated_document_count())


if __name__ == "__main__":
    main()
