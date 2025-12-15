from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from backend.db.mongo import get_db
from backend.services.filters import build_filters
from backend.api.signals import _get_base_ids

bp = Blueprint("outcomes", __name__, url_prefix="/api")


@bp.get("/outcomes")
def get_outcomes_summary():
    """
    Returns counts/percentages for key outcomes (Death, Hospital, etc.).
    Consistent with Search/Onset logic including:
    - Manual Died/Hospital filters
    - Strict Non-Serious logic
    - Onset Days calculation and filtering
    """
    try:
        # 1. Standard Filters
        f, data_match, join_filters = build_filters(request)

        # 2. Manual Filter Logic (Died / Hospital / Strict Non-Serious)
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
                data_match[flag] = {"$ne": "Y"}

        # 3. Handle Join Filters
        base_id_cap = int(request.args.get("base_id_cap", "0") or 0)
        base_ids = _get_base_ids(data_match, join_filters, base_id_cap=base_id_cap)

        if base_ids is not None and not base_ids:
            return jsonify({
                "outcomes": [],
                "total": 0,
                "N_base": 0,
                "time_utc": datetime.utcnow().isoformat()
            })

        match = data_match
        if base_ids is not None:
            match = {"VAERS_ID": {"$in": base_ids}}

        # 4. Onset Days Filtering (same logic as Search)
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

        db = get_db()
        coll = db["vaers_data"]

        # 5. Build Aggregation Pipeline
        pipeline = [{"$match": match}]

        # If filtering by duration, calculate days first
        if has_onset_filter:
            pipeline.extend([
                {
                    "$addFields": {
                        "_vax_dt": {"$convert": {"input": "$VAX_DATE", "to": "date", "onError": None, "onNull": None}},
                        "_onset_dt": {
                            "$convert": {"input": "$ONSET_DATE", "to": "date", "onError": None, "onNull": None}},
                    }
                },
                {
                    "$addFields": {
                        "ONSET_DAYS": {
                            "$cond": [
                                {"$and": [{"$ne": ["$_vax_dt", None]}, {"$ne": ["$_onset_dt", None]}]},
                                {"$dateDiff": {"startDate": "$_vax_dt", "endDate": "$_onset_dt", "unit": "day"}},
                                None
                            ]
                        }
                    }
                }
            ])

            onset_match_expr = {}
            if onset_min is not None: onset_match_expr["$gte"] = onset_min
            if onset_max is not None: onset_match_expr["$lte"] = onset_max
            pipeline.append({"$match": {"ONSET_DAYS": onset_match_expr}})

        # Group stage to count flags
        # We sum 1 if the field == "Y", else 0
        pipeline.append({
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "Death": {"$sum": {"$cond": [{"$eq": ["$DIED", "Y"]}, 1, 0]}},
                "Hospitalized": {"$sum": {"$cond": [{"$eq": ["$HOSPITAL", "Y"]}, 1, 0]}},
                "Life Threatening": {"$sum": {"$cond": [{"$eq": ["$L_THREAT", "Y"]}, 1, 0]}},
                "Disabled": {"$sum": {"$cond": [{"$eq": ["$DISABLE", "Y"]}, 1, 0]}},
                "Birth Defect": {"$sum": {"$cond": [{"$eq": ["$BIRTH_DEFECT", "Y"]}, 1, 0]}},
                "ER Visit": {"$sum": {"$cond": [{"$eq": ["$ER_VISIT", "Y"]}, 1, 0]}},
                "Recovered": {"$sum": {"$cond": [{"$eq": ["$RECOVD", "Y"]}, 1, 0]}},
            }
        })

        results = list(coll.aggregate(pipeline, allowDiskUse=True))

        if not results:
            return jsonify({
                "outcomes": [],
                "total": 0,
                "N_base": 0,
                "time_utc": datetime.utcnow().isoformat()
            })

        res = results[0]
        total = res.get("total", 0)

        # Format for frontend
        # Order matters for display
        keys_to_show = [
            "Death", "Life Threatening", "Hospitalized",
            "Disabled", "Birth Defect", "ER Visit", "Recovered"
        ]

        outcomes_list = []
        for k in keys_to_show:
            count = res.get(k, 0)
            outcomes_list.append({"key": k, "count": count})

        return jsonify({
            "outcomes": outcomes_list,
            "total": total,
            "N_base": total,
            "time_utc": datetime.utcnow().isoformat()
        })

    except Exception as e:
        return jsonify({"error": str(e), "outcomes": []}), 500