"""
API endpoint for geographic data visualization.
Returns state-level counts for map visualization.
"""

from flask import Blueprint, jsonify, request
from backend.db.mongo import get_db
from backend.services.filters import build_filters

bp = Blueprint("geo_data", __name__, url_prefix="/api")


@bp.get("/geo/states")
def get_state_counts():
    """
    Get comprehensive state statistics for map visualization.
    Applies the same filters as search endpoint.

    Returns:
        {
            "states": [
                {
                    "state": "CA",
                    "count": 1234,
                    "serious_count": 456,
                    "serious_ratio": 0.369,
                    "avg_age": 45.2
                },
                ...
            ],
            "total": 5678,
            "time_utc": "..."
        }
    """
    from datetime import datetime

    try:
        f, data_match, join_filters = build_filters(request)
        db = get_db()

        # Aggregation pipeline to get comprehensive state stats
        pipeline = [
            {"$match": data_match},
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
