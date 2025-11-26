from __future__ import annotations

from datetime import datetime
from flask import Blueprint, jsonify, request

from backend.db.mongo import get_db
from backend.services.filters import build_filters
from backend.api.signals import _get_base_ids  # reuse join-safe filtering

bp = Blueprint("outcomes_api", __name__, url_prefix="/api")

OUTCOME_KEYS = [
    ("DIED", "Died"),
    ("HOSPITAL", "Hospitalized"),
    ("L_THREAT", "Life-threatening"),
    ("DISABLE", "Disabled"),
    ("BIRTH_DEFECT", "Birth defect"),
    ("RECOVD", "Recovered"),
]


@bp.get("/outcomes")
def outcomes():
    f, data_match, join_filters = build_filters(request)

    base_id_cap = int(request.args.get("base_id_cap", 0) or 0)
    base_ids = _get_base_ids(data_match, join_filters, base_id_cap=base_id_cap)

    db = get_db()
    coll = db["vaers_data"]

    if not base_ids:
        return jsonify(
            {
                "time_utc": datetime.utcnow().isoformat() + "Z",
                "N_base": 0,
                "total": 0,
                "outcomes": [{"key": label, "count": 0} for _, label in OUTCOME_KEYS],
            }
        )

    pipeline = [
        {"$match": {"VAERS_ID": {"$in": base_ids}}},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                **{
                    k: {
                        "$sum": {
                            "$cond": [{"$eq": [f"${k}", "Y"]}, 1, 0]
                        }
                    }
                    for k, _ in OUTCOME_KEYS
                },
            }
        },
    ]

    agg = list(coll.aggregate(pipeline, allowDiskUse=True))
    if not agg:
        total = 0
        counts = {k: 0 for k, _ in OUTCOME_KEYS}
    else:
        total = int(agg[0].get("total", 0))
        counts = {k: int(agg[0].get(k, 0)) for k, _ in OUTCOME_KEYS}

    return jsonify(
        {
            "time_utc": datetime.utcnow().isoformat() + "Z",
            "N_base": len(base_ids),
            "total": total,
            "outcomes": [{"key": label, "count": counts[k]} for k, label in OUTCOME_KEYS],
        }
    )
