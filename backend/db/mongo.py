# backend/db/mongo.py
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database


def _load_env_once() -> None:
    """
    Loads .env from repo root (VAERS_Interactive/.env).
    Safe to call multiple times; dotenv will just re-parse.
    """
    root = Path(__file__).resolve().parents[2]  # .../VAERS_Interactive
    load_dotenv(root / ".env")


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    db_name: str
    app_name: str = "VaxScope"

    @staticmethod
    def from_env() -> "MongoSettings":
        _load_env_once()
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017").strip()
        db_name = os.getenv("MONGO_DB", "vaers_dev").strip()
        app_name = os.getenv("MONGO_APP_NAME", "VaxScope").strip() or "VaxScope"
        return MongoSettings(uri=uri, db_name=db_name, app_name=app_name)


@lru_cache(maxsize=1)
def get_client(settings: Optional[MongoSettings] = None) -> MongoClient:
    """
    Returns a cached MongoClient. MongoClient is thread-safe and intended to be reused.
    """
    s = settings or MongoSettings.from_env()

    # serverSelectionTimeoutMS avoids long hangs if Mongo is down.
    # appname shows up in Mongo logs/metrics.
    return MongoClient(
        s.uri,
        appname=s.app_name,
        serverSelectionTimeoutMS=int(os.getenv("MONGO_TIMEOUT_MS", "5000")),
    )


def get_db(settings: Optional[MongoSettings] = None) -> Database:
    """
    Convenience function to get the database handle.
    """
    s = settings or MongoSettings.from_env()
    client = get_client(s)
    return client[s.db_name]


def ping(settings: Optional[MongoSettings] = None) -> bool:
    """
    Returns True if Mongo is reachable.
    """
    db = get_db(settings)
    # "ping" is the canonical Mongo health command.
    res = db.command("ping")
    return bool(res.get("ok") == 1.0 or res.get("ok") == 1)


def quick_counts(settings: Optional[MongoSettings] = None) -> dict:
    """
    Returns quick counts for expected collections (if present).
    """
    db = get_db(settings)
    expected = ["vaers_data", "vaers_vax", "vaers_symptoms"]
    out = {"db": db.name, "collections": {}}
    for name in expected:
        if name in db.list_collection_names():
            out["collections"][name] = db[name].estimated_document_count()
        else:
            out["collections"][name] = None
    return out


def main() -> None:
    """
    Run:  python -m backend.db.mongo
    or:   python backend/db/mongo.py
    """
    s = MongoSettings.from_env()
    print(f"[INFO] MONGO_URI={s.uri}")
    print(f"[INFO] MONGO_DB ={s.db_name}")

    try:
        ok = ping(s)
        print(f"[OK] ping={ok}")
    except Exception as e:
        print(f"[ERROR] Failed to ping MongoDB: {e}")
        raise

    try:
        counts = quick_counts(s)
        print("[INFO] Quick counts:")
        for k, v in counts["collections"].items():
            print(f"  - {k}: {v}")
    except Exception as e:
        print(f"[WARN] Could not fetch counts: {e}")

    db = get_db(s)
    print("[INFO] Existing collections:", db.list_collection_names())


if __name__ == "__main__":
    main()
