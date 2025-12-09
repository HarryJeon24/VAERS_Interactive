# backend/api/search.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from backend.db.mongo import get_db
from backend.services.filters import build_filters
from backend.api.signals import _get_base_ids

bp = Blueprint("search_api", __name__, url_prefix="/api")


def _json_safe(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert Mongo-returned docs to JSON-safe dict:
    - ObjectId -> str
    - datetime -> ISO string
    """
    out: Dict[str, Any] = {}
    for k, v in doc.items():
        if k == "_id":
            out["_id"] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@bp.get("/search")
def search_reports():
    """
    GET /api/search
    Report-level search over vaers_data using shared filters.

    Query params (examples):
      /api/search?year=2023&sex=F&state=GA&age_min=18&age_max=45&serious_only=true
      /api/search?onset_start=2018-01-01&onset_end=2018-12-31

    Returns:
      - applied match
      - count (approx via limited scan)
      - list of sample reports
    """
    f, data_match, join_filters = build_filters(request)

    limit = request.args.get("limit", "50")
    try:
        limit_n = max(1, min(200, int(limit)))
    except ValueError:
        limit_n = 50

    base_id_cap = int(request.args.get("base_id_cap", "0") or 0)

    # Get filtered base IDs using join filters
    base_ids = _get_base_ids(data_match, join_filters, base_id_cap=base_id_cap)

    db = get_db()
    coll = db["vaers_data"]

    # If no reports match the filters, return empty results
    if not base_ids:
        return jsonify(
            {
                "time_utc": datetime.utcnow().isoformat() + "Z",
                "filters": {
                    "parsed": f.__dict__,
                    "vaers_data_match": data_match,
                    "join_filters": join_filters,
                },
                "count": 0,
                "limit": limit_n,
                "results": [],
            }
        )

    # projection: keep response small + relevant
    proj = {
        "_id": 1,
        "VAERS_ID": 1,
        "YEAR": 1,
        "SEX": 1,
        "AGE_YRS": 1,
        "STATE": 1,
        "VAX_DATE": 1,
        "ONSET_DATE": 1,
        "RECVDATE": 1,
        "DIED": 1,
        "HOSPITAL": 1,
        "L_THREAT": 1,
        "DISABLE": 1,
        "BIRTH_DEFECT": 1,
        "RECOVD": 1,
        "SYMPTOM_TEXT": 1,
        "FORM_VERS": 1,
    }

    # Query only the filtered base_ids
    cursor = (
        coll.find({"VAERS_ID": {"$in": base_ids}}, proj)
        .sort([("YEAR", 1), ("VAERS_ID", 1)])
        .limit(limit_n)
    )
    docs = [_json_safe(d) for d in cursor]

    count = len(base_ids)

    return jsonify(
        {
            "time_utc": datetime.utcnow().isoformat() + "Z",
            "filters": {
                "parsed": f.__dict__,
                "vaers_data_match": data_match,
                "join_filters": join_filters,
            },
            "count": count,
            "limit": limit_n,
            "results": docs,
        }
    )


def main() -> None:
    """
    Self-test runner that starts a tiny Flask app just for this blueprint.

    Run:
      python backend/api/search.py
    Then open:
      http://127.0.0.1:5001/api/search?year=2023&sex=F&serious_only=true&limit=10
    """
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(bp)
    app.run(host="127.0.0.1", port=5001, debug=True)


if __name__ == "__main__":
    main()
