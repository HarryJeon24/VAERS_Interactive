# backend/app.py
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify

# When running as a script, ensure repo root is importable
ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.mongo import MongoSettings, get_db, ping  # noqa: E402
from backend.api.search import bp as search_bp  # noqa: E402


def create_app() -> Flask:
    app = Flask(__name__)

    # Register API blueprints
    app.register_blueprint(search_bp)

    @app.get("/api/health")
    def health():
        settings = MongoSettings.from_env()
        mongo_ok = False
        err = None
        try:
            mongo_ok = ping(settings)
        except Exception as e:
            err = str(e)

        return jsonify(
            {
                "ok": True,
                "service": "vaxscope",
                "time_utc": datetime.utcnow().isoformat() + "Z",
                "mongo": {
                    "ok": mongo_ok,
                    "db": settings.db_name,
                    "uri": settings.uri,
                    "error": err,
                },
            }
        )

    @app.get("/api/stats")
    def stats():
        db = get_db()
        out: Dict[str, Any] = {
            "db": db.name,
            "time_utc": datetime.utcnow().isoformat() + "Z",
            "collections": {},
            "year_counts": [],
            "field_samples_by_year": [],
        }

        for name in ["vaers_data", "vaers_vax", "vaers_symptoms"]:
            out["collections"][name] = db[name].estimated_document_count()

        year_counts = list(
            db["vaers_data"].aggregate(
                [
                    {"$group": {"_id": "$YEAR", "n": {"$sum": 1}}},
                    {"$sort": {"_id": 1}},
                ]
            )
        )
        out["year_counts"] = [{"year": d["_id"], "n": d["n"]} for d in year_counts]

        sample = list(
            db["vaers_data"].aggregate(
                [
                    {"$match": {"YEAR": {"$ne": None}}},
                    {"$group": {"_id": "$YEAR", "doc": {"$first": "$$ROOT"}}},
                    {"$sort": {"_id": 1}},
                    {"$limit": 20},
                ]
            )
        )

        field_samples: List[Dict[str, Any]] = []
        for item in sample:
            y = item["_id"]
            doc = item.get("doc") or {}
            keys = sorted([k for k in doc.keys() if k not in ("_id",)])
            field_samples.append({"year": y, "num_fields": len(keys), "fields_head": keys[:40]})
        out["field_samples_by_year"] = field_samples

        return jsonify(out)

    return app


def main() -> None:
    """
    Run:
      python backend/app.py

    Then test:
      http://127.0.0.1:5000/api/health
      http://127.0.0.1:5000/api/stats
      http://127.0.0.1:5000/api/search?year=2023&limit=5
    """
    port = int(os.getenv("PORT", "5000"))
    app = create_app()
    app.run(host="127.0.0.1", port=port, debug=True)


if __name__ == "__main__":
    main()
