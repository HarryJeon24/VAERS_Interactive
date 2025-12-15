"""
API endpoint for geographic data visualization.
Returns state-level counts for map visualization.
"""

from flask import Blueprint, jsonify, request
from backend.db.mongo import get_db
from backend.services.filters import build_filters
from backend.api.signals import _get_base_ids
from datetime import datetime

bp = Blueprint("geo_data", __name__, url_prefix="/api")


@bp.get("/geo/states")
def get_state_counts():
    """
    Get comprehensive state statistics for map visualization.
    Applies the same filters as search endpoint, including new manual
    handlers for died/hospital/strict-serious.
    """
    try:
        f, data_match, join_filters = build_filters(request)
        db = get_db()

        # --- Manual Filter Logic (Must match search.py) ---

        # 1. Died
        died_arg = request.args.get("died", "").strip().lower()
        if died_arg == "true":
            data_match["DIED"] = "Y"
        elif died_arg == "false":
            data_match["DIED"] = {"$ne": "Y"}

        # 2. Hospital
        hosp_arg = request.args.get("hospital", "").strip().lower()
        if hosp_arg == "true":
            data_match["HOSPITAL"] = "Y"
        elif hosp_arg == "false":
            data_match["HOSPITAL"] = {"$ne": "Y"}

        # 3. Serious = False (Strict Non-Serious)
        serious_arg = request.args.get("serious_only", "").strip().lower()
        if serious_arg == "false":
            serious_flags = ["DIED", "HOSPITAL", "L_THREAT", "DISABLE", "BIRTH_DEFECT"]
            for flag in serious_flags:
                if flag not in data_match:
                     data_match[flag] = {"$ne": "Y"}
                else:
                     data_match[flag] = {"$ne": "Y"}

        # --------------------------------------------------

        base_id_cap = int(request.args.get("base_id_cap", "0") or 0)

        # Get filtered base IDs using join filters
        base_ids = _get_base_ids(data_match, join_filters, base_id_cap=base_id_cap)

        if not base_ids:
            return jsonify({
                "states": [],
                "total": 0,
                "time_utc": datetime.utcnow().isoformat()
            })

        # Aggregation pipeline to get comprehensive state stats
        pipeline = [
            {"$match": {"VAERS_ID": {"$in": base_ids}}},
            {
                "$group": {
                    "_id": "$STATE",
                    "count": {"$sum": 1},
                    "serious_count": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$or": [
                                        {"$eq": ["$DIED", "Y"]},
                                        {"$eq": ["$HOSPITAL", "Y"]},
                                        {"$eq": ["$L_THREAT", "Y"]},
                                        {"$eq": ["$DISABLE", "Y"]},
                                        {"$eq": ["$BIRTH_DEFECT", "Y"]}
                                    ]
                                },
                                1,
                                0
                            ]
                        }
                    },
                    "ages": {"$push": "$AGE_YRS"}
                }
            },
            {"$match": {"_id": {"$ne": None}}},  # Filter out null states
            {"$sort": {"count": -1}}
        ]

        results = list(db["vaers_data"].aggregate(pipeline))

        # Calculate statistics for each state
        states = []
        for r in results:
            if not r["_id"] or not str(r["_id"]).strip():
                continue

            # Calculate average age (filter out None values)
            valid_ages = [age for age in r["ages"] if age is not None and isinstance(age, (int, float))]
            avg_age = sum(valid_ages) / len(valid_ages) if valid_ages else 0

            # Calculate serious ratio
            serious_ratio = r["serious_count"] / r["count"] if r["count"] > 0 else 0

            states.append({
                "state": r["_id"],
                "count": r["count"],
                "serious_count": r["serious_count"],
                "serious_ratio": round(serious_ratio, 3),
                "avg_age": round(avg_age, 1)
            })

        total = sum(item["count"] for item in states)

        return jsonify({
            "states": states,
            "total": total,
            "time_utc": datetime.utcnow().isoformat()
        })

    except Exception as e:
        return jsonify({"error": str(e), "states": [], "total": 0}), 500