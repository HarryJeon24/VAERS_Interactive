from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from backend.db.mongo import get_db
from backend.services.filters import build_filters
from backend.api.signals import _get_base_ids

bp = Blueprint("onset", __name__, url_prefix="/api")


@bp.get("/onset")
def get_onset_distribution():
    """
    Returns a strict day-by-day histogram of Onset Days.
    Respects both 'onset_days_min' and 'onset_days_max' filters.
    """
    try:
        # 1. Build standard filters
        f, data_match, join_filters = build_filters(request)

        # 2. Manual Filter Logic
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
            for flag in ["DIED", "HOSPITAL", "L_THREAT", "DISABLE", "BIRTH_DEFECT"]:
                data_match[flag] = {"$ne": "Y"}

        # 3. Handle Join Filters
        base_id_cap = int(request.args.get("base_id_cap", "0") or 0)
        base_ids = _get_base_ids(data_match, join_filters, base_id_cap=base_id_cap)

        if base_ids is not None and not base_ids:
            return jsonify({"stats": {}, "days": [], "obs": 0, "N_base": 0, "time_utc": datetime.utcnow().isoformat()})

        match = data_match
        if base_ids is not None: match = {"VAERS_ID": {"$in": base_ids}}

        # 4. Determine Date Limits (Min & Max)
        # Default Max is 60 if not specified
        user_max = request.args.get("onset_days_max", "").strip()
        try:
            limit_max = int(user_max) if user_max else 60
        except ValueError:
            limit_max = 60

        # Default Min is 0 if not specified
        user_min = request.args.get("onset_days_min", "").strip()
        try:
            limit_min = int(user_min) if user_min else 0
        except ValueError:
            limit_min = 0

        # Safety: ensure limits are non-negative (onset can't be negative for this chart)
        limit_min = max(0, limit_min)

        # If user explicitly sets Min > Max (logic error), return empty
        if limit_min > limit_max:
            return jsonify({"stats": {}, "days": [], "obs": 0, "N_base": 0, "time_utc": datetime.utcnow().isoformat()})

        db = get_db()
        coll = db["vaers_data"]
        N_base = coll.count_documents(match)

        # 5. Pipeline: Calculate Days -> Filter Range -> Group
        pipeline = [
            {"$match": match},
            {
                "$addFields": {
                    "_vax_dt": {"$convert": {"input": "$VAX_DATE", "to": "date", "onError": None, "onNull": None}},
                    "_onset_dt": {"$convert": {"input": "$ONSET_DATE", "to": "date", "onError": None, "onNull": None}}
                }
            },
            {
                "$addFields": {
                    "numdays": {
                        "$cond": [
                            {"$and": [{"$ne": ["$_vax_dt", None]}, {"$ne": ["$_onset_dt", None]}]},
                            {"$dateDiff": {"startDate": "$_vax_dt", "endDate": "$_onset_dt", "unit": "day"}},
                            None
                        ]
                    }
                }
            },
            # STRICT FILTER: Must be within [limit_min, limit_max]
            {"$match": {"numdays": {"$gte": limit_min, "$lte": limit_max}}},
            # Group by exact day
            {"$group": {"_id": "$numdays", "n": {"$sum": 1}}},
            {"$sort": {"_id": 1}}
        ]

        results = list(coll.aggregate(pipeline, allowDiskUse=True))

        # 6. Post-process stats
        days = [{"day": r["_id"], "n": r["n"]} for r in results]

        obs = sum(d["n"] for d in days)
        if obs > 0:
            total_days = sum(d["day"] * d["n"] for d in days)
            avg = total_days / obs
            stats = {
                "min": days[0]["day"],
                "max": days[-1]["day"],
                "avg": round(avg, 2)
            }
        else:
            stats = {"min": 0, "max": 0, "avg": 0}

        return jsonify({
            "stats": stats,
            "days": days,
            "obs": obs,
            "N_base": N_base,
            "time_utc": datetime.utcnow().isoformat()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500