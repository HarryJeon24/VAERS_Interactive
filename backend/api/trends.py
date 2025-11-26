from __future__ import annotations

from datetime import datetime
from flask import Blueprint, jsonify, request

from backend.db.mongo import get_db
from backend.services.filters import build_filters
from backend.api.signals import _get_base_ids

bp = Blueprint("trends_api", __name__, url_prefix="/api")


@bp.get("/trends")
def trends():
    f, data_match, join_filters = build_filters(request)

    clip_months = int(request.args.get("clip_months", 0) or 0)
    clip_months = max(0, clip_months)

    base_id_cap = int(request.args.get("base_id_cap", 0) or 0)
    base_ids = _get_base_ids(data_match, join_filters, base_id_cap=base_id_cap)

    db = get_db()
    coll = db["vaers_data"]

    if not base_ids:
        return jsonify(
            {"time_utc": datetime.utcnow().isoformat() + "Z", "N_base": 0, "points": 0, "series": []}
        )

    # Month key from onset date
    pipeline = [
        {"$match": {"VAERS_ID": {"$in": base_ids}, "ONSET_DATE": {"$ne": None}}},
        {"$project": {"month": {"$dateToString": {"format": "%Y-%m", "date": "$ONSET_DATE"}}}},
        {"$group": {"_id": "$month", "n": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]

    series = [{"month": d["_id"], "n": int(d["n"])} for d in coll.aggregate(pipeline, allowDiskUse=True)]

    if clip_months > 0 and len(series) > clip_months:
      series = series[-clip_months:]

    return jsonify(
        {
            "time_utc": datetime.utcnow().isoformat() + "Z",
            "N_base": len(base_ids),
            "points": len(series),
            "series": series,
        }
    )
