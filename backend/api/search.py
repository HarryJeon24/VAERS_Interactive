# backend/api/search.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

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


def _has_join_filters(join_filters: Dict[str, Any]) -> bool:
    # join_filters typically contains: vax_type, vax_manu, symptom_term, symptom_text
    for v in (join_filters or {}).values():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return True
    return False


@bp.get("/search")
def search_reports():
    """
    GET /api/search
    Report-level search over vaers_data using shared filters.

    Notes:
    - If join-side filters are present (vax_type/vax_manu/symptom_term/symptom_text), we first compute base_ids
      (VAERS_IDs) that satisfy those joins, then fetch report rows from vaers_data.
    - If no join-side filters are present, we query vaers_data directly without materializing base_ids.
    """
    f, data_match, join_filters = build_filters(request)

    limit = request.args.get("limit", "50")
    try:
        limit_n = max(1, min(200, int(limit)))
    except ValueError:
        limit_n = 50

    # Cap to prevent giant $in arrays for search (signals can be heavier; search should stay snappy)
    base_id_cap_raw = request.args.get("base_id_cap", "0") or "0"
    try:
        base_id_cap = int(base_id_cap_raw)
    except ValueError:
        base_id_cap = 0

    # ---- Year normalization (defensive) ----
    # Some datasets store report-year as RECVDATE_YEAR rather than YEAR.
    # If filters.py still emits YEAR, translate it here so search stays correct.
    if "YEAR" in data_match and "RECVDATE_YEAR" not in data_match:
        data_match["RECVDATE_YEAR"] = data_match.pop("YEAR")

    db = get_db()
    coll = db["vaers_data"]

    has_join = _has_join_filters(join_filters)

    base_ids: Optional[List[int]] = None
    count: int = 0

    if has_join:
        # If caller didn't set a cap, apply a safe cap for this endpoint.
        # (Avoid exceeding BSON limits / slow queries with massive $in arrays.)
        effective_cap = base_id_cap if base_id_cap > 0 else 50000

        base_ids = _get_base_ids(data_match, join_filters, base_id_cap=effective_cap)

        if not base_ids:
            return jsonify(
                {
                    "time_utc": datetime.utcnow().isoformat() + "Z",
                    "filters": {
                        "parsed": f.__dict__,
                        "vaers_data_match": data_match,
                        "join_filters": join_filters,
                        "base_id_cap_effective": effective_cap,
                    },
                    "count": 0,
                    "limit": limit_n,
                    "results": [],
                }
            )

        count = len(base_ids)
        match: Dict[str, Any] = {"VAERS_ID": {"$in": base_ids}}
    else:
        match = data_match or {}
        try:
            count = int(coll.count_documents(match))
        except Exception:
            count = 0

    # Choose sort field if present
    sort_year_field = "RECVDATE_YEAR" if ("RECVDATE_YEAR" in match or "RECVDATE_YEAR" in data_match) else "YEAR"

    # Build pipeline:
    # - match
    # - sort
    # - limit
    # - lookups for filterables (vax + symptoms)
    # - computed onset days
    # - project (small + useful)
    pipeline: List[Dict[str, Any]] = [
        {"$match": match},
        {"$sort": {sort_year_field: 1, "VAERS_ID": 1}},
        {"$limit": limit_n},
        {"$lookup": {"from": "vaers_vax", "localField": "VAERS_ID", "foreignField": "VAERS_ID", "as": "_vax"}},
        {"$lookup": {"from": "vaers_symptoms", "localField": "VAERS_ID", "foreignField": "VAERS_ID", "as": "_sym"}},
        {
            "$addFields": {
                # aggregate vaccine filterables
                "VAX_TYPES": {
                    "$setDifference": [
                        {"$setUnion": [[], {"$map": {"input": "$_vax", "as": "v", "in": "$$v.VAX_TYPE"}}]},
                        [None, ""],
                    ]
                },
                "VAX_MANUS": {
                    "$setDifference": [
                        {"$setUnion": [[], {"$map": {"input": "$_vax", "as": "v", "in": "$$v.VAX_MANU"}}]},
                        [None, ""],
                    ]
                },
                # symptoms collection is usually 1 doc per VAERS_ID; take first and union SYMPTOM1..5
                "SYMPTOM_TERMS": {
                    "$setDifference": [
                        {
                            "$setUnion": [
                                [],
                                {
                                    "$let": {
                                        "vars": {"s": {"$arrayElemAt": ["$_sym", 0]}},
                                        "in": [
                                            "$$s.SYMPTOM1",
                                            "$$s.SYMPTOM2",
                                            "$$s.SYMPTOM3",
                                            "$$s.SYMPTOM4",
                                            "$$s.SYMPTOM5",
                                        ],
                                    }
                                },
                            ]
                        },
                        [None, ""],
                    ]
                },
                # compute onset days if both dates parse
                "_vax_dt": {"$convert": {"input": "$VAX_DATE", "to": "date", "onError": None, "onNull": None}},
                "_onset_dt": {"$convert": {"input": "$ONSET_DATE", "to": "date", "onError": None, "onNull": None}},
            }
        },
        {
            "$addFields": {
                "ONSET_DAYS": {
                    "$cond": [
                        {"$and": [{"$ne": ["$_vax_dt", None]}, {"$ne": ["$_onset_dt", None]}]},
                        {
                            "$dateDiff": {
                                "startDate": "$_vax_dt",
                                "endDate": "$_onset_dt",
                                "unit": "day",
                            }
                        },
                        None,
                    ]
                }
            }
        },
        {
            "$project": {
                "_id": 1,
                "VAERS_ID": 1,
                # year (keep both if present; frontend can choose)
                "RECVDATE_YEAR": 1,
                "YEAR": 1,
                "SEX": 1,
                "AGE_YRS": 1,
                "STATE": 1,
                "VAX_DATE": 1,
                "ONSET_DATE": 1,
                "RECVDATE": 1,
                "ONSET_DAYS": 1,
                # serious flags
                "DIED": 1,
                "HOSPITAL": 1,
                "L_THREAT": 1,
                "DISABLE": 1,
                "BIRTH_DEFECT": 1,
                "RECOVD": 1,
                # narratives + form
                "SYMPTOM_TEXT": 1,
                "FORM_VERS": 1,
                # additional filterable fields (can be long, but useful)
                "OTHER_MEDS": 1,
                "CUR_ILL": 1,
                "HISTORY": 1,
                "PRIOR_VAX": 1,
                "ALLERGIES": 1,
                # joined filterables
                "VAX_TYPES": 1,
                "VAX_MANUS": 1,
                "SYMPTOM_TERMS": 1,
            }
        },
    ]

    cursor = coll.aggregate(pipeline, allowDiskUse=True)
    docs = [_json_safe(d) for d in cursor]

    return jsonify(
        {
            "time_utc": datetime.utcnow().isoformat() + "Z",
            "filters": {
                "parsed": f.__dict__,
                "vaers_data_match": data_match,
                "join_filters": join_filters,
                "uses_join_prefilter": bool(has_join),
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
