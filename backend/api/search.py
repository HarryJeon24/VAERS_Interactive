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
    # join_filters typically contains: vax_type, vax_manu, symptom_term
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
    Report-level search over vaers_data.

    Fixes:
    - Applies 'Onset Days' filter BEFORE limiting results to ensure accuracy.
    - Supports died/hospital/strict-serious logic.
    """
    f, data_match, join_filters = build_filters(request)

    # --- 1. Manual Filter Logic ---
    died_arg = request.args.get("died", "").strip().lower()
    if died_arg == "true":
        data_match["DIED"] = "Y"
    elif died_arg == "false":
        data_match["DIED"] = {"$ne": "Y"}

    hosp_arg = request.args.get("hospital", "").strip().lower()
    if hosp_arg == "true":
        data_match["HOSPITAL"] = "Y"
    elif hosp_arg == "false":
        data_match["HOSPITAL"] = {"$ne": "Y"}

    serious_arg = request.args.get("serious_only", "").strip().lower()
    if serious_arg == "false":
        serious_flags = ["DIED", "HOSPITAL", "L_THREAT", "DISABLE", "BIRTH_DEFECT"]
        for flag in serious_flags:
            if flag not in data_match:
                data_match[flag] = {"$ne": "Y"}
            else:
                data_match[flag] = {"$ne": "Y"}

    # --- 2. Onset Days Filters ---
    # We must detect these to decide pipeline order
    onset_min_raw = request.args.get("onset_days_min", "").strip()
    onset_max_raw = request.args.get("onset_days_max", "").strip()

    has_onset_filter = False
    onset_min = None
    onset_max = None

    if onset_min_raw:
        try:
            onset_min = float(onset_min_raw)
            has_onset_filter = True
        except ValueError:
            pass

    if onset_max_raw:
        try:
            onset_max = float(onset_max_raw)
            has_onset_filter = True
        except ValueError:
            pass

    # --- 3. Limit & Cap ---
    limit = request.args.get("limit", "50")
    try:
        limit_n = max(1, min(1000, int(limit)))
    except ValueError:
        limit_n = 50

    base_id_cap = int(request.args.get("base_id_cap", "0") or 0)

    # ---- Year normalization ----
    if "YEAR" in data_match and "RECVDATE_YEAR" not in data_match:
        data_match["RECVDATE_YEAR"] = data_match.pop("YEAR")

    db = get_db()
    coll = db["vaers_data"]

    has_join = _has_join_filters(join_filters)
    base_ids: Optional[List[int]] = None
    count: int = 0

    if has_join:
        effective_cap = base_id_cap if base_id_cap > 0 else 50000
        base_ids = _get_base_ids(data_match, join_filters, base_id_cap=effective_cap)

        if not base_ids:
            return jsonify({
                "time_utc": datetime.utcnow().isoformat() + "Z",
                "count": 0, "limit": limit_n, "results": []
            })

        count = len(base_ids)
        match: Dict[str, Any] = {"VAERS_ID": {"$in": base_ids}}
    else:
        match = data_match or {}
        try:
            count = int(coll.count_documents(match))
        except Exception:
            count = 0

    sort_year_field = "RECVDATE_YEAR" if ("RECVDATE_YEAR" in match or "RECVDATE_YEAR" in data_match) else "YEAR"

    # --- 4. Build Pipeline ---
    pipeline: List[Dict[str, Any]] = [
        {"$match": match}
    ]

    # STAGE A: DATE CALCULATION
    # We define this stage but only add it early if needed.
    date_calc_stages = [
        {
            "$addFields": {
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
        }
    ]

    # STAGE B: FILTERING (The Fix)
    # If users filtered by days (e.g. max 20), we MUST calculate & filter BEFORE limiting.
    if has_onset_filter:
        pipeline.extend(date_calc_stages)

        onset_match = {}
        if onset_min is not None:
            onset_match["$gte"] = onset_min
        if onset_max is not None:
            onset_match["$lte"] = onset_max

        pipeline.append({"$match": {"ONSET_DAYS": onset_match}})

    # STAGE C: SORT & LIMIT
    # Now that bad data is removed, we can safely sort and limit.
    pipeline.extend([
        {"$sort": {sort_year_field: 1, "VAERS_ID": 1}},
        {"$limit": limit_n}
    ])

    # STAGE D: LOOKUPS (Expensive)
    pipeline.extend([
        {"$lookup": {"from": "vaers_vax", "localField": "VAERS_ID", "foreignField": "VAERS_ID", "as": "_vax"}},
        {"$lookup": {"from": "vaers_symptoms", "localField": "VAERS_ID", "foreignField": "VAERS_ID", "as": "_sym"}},
        {
            "$addFields": {
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
            }
        }
    ])

    # STAGE E: Fallback Calc
    # If we didn't calculate dates earlier (because no filter was set), we do it now.
    if not has_onset_filter:
        pipeline.extend(date_calc_stages)

    # STAGE F: Final Project
    pipeline.append({
        "$project": {
            "_id": 1,
            "VAERS_ID": 1,
            "RECVDATE_YEAR": 1,
            "YEAR": 1,
            "SEX": 1,
            "AGE_YRS": 1,
            "STATE": 1,
            "VAX_DATE": 1,
            "ONSET_DATE": 1,
            "ONSET_DAYS": 1,
            "DIED": 1,
            "HOSPITAL": 1,
            "L_THREAT": 1,
            "DISABLE": 1,
            "BIRTH_DEFECT": 1,
            "SYMPTOM_TEXT": 1,
            "VAX_TYPES": 1,
            "VAX_MANUS": 1,
            "SYMPTOM_TERMS": 1,
        }
    })

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
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    app.run(host="127.0.0.1", port=5001, debug=True)


if __name__ == "__main__":
    main()