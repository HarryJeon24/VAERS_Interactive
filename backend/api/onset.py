from __future__ import annotations

from datetime import datetime
from flask import Blueprint, jsonify, request

from backend.db.mongo import get_db
from backend.services.filters import build_filters

# Reuse the proven base-id join logic from signals (works with vax_type/vax_manu/symptom_term)
from backend.api.signals import _get_base_ids  # noqa: E402

bp = Blueprint("onset_api", __name__, url_prefix="/api")


@bp.get("/onset")
def onset():
    f, data_match, join_filters = build_filters(request)

    buckets = int(request.args.get("buckets", 30) or 30)
    buckets = max(5, min(buckets, 60))

    clip_max_days = int(request.args.get("clip_max_days", 180) or 180)
    clip_max_days = max(0, clip_max_days)

    base_id_cap = int(request.args.get("base_id_cap", 0) or 0)
    base_ids = _get_base_ids(data_match, join_filters, base_id_cap=base_id_cap)

    db = get_db()
    coll = db["vaers_data"]

    if not base_ids:
        return jsonify(
            {
                "time_utc": datetime.utcnow().isoformat() + "Z",
                "N_base": 0,
                "obs": 0,
                "buckets": [],
                "stats": {"min": None, "max": None, "avg": None},
            }
        )

    # Compute NUMDAYS from (ONSET_DATE - VAX_DATE) in days (date fields were parsed at load time)
    day_ms = 86400000

    match = {
        "VAERS_ID": {"$in": base_ids},
        "VAX_DATE": {"$ne": None},
        "ONSET_DATE": {"$ne": None},
    }

    pipeline_values = [
        {"$match": match},
        {
            "$project": {
                "_id": 0,
                "numdays": {
                    "$trunc": {
                        "$divide": [
                            {"$subtract": ["$ONSET_DATE", "$VAX_DATE"]},
                            day_ms,
                        ]
                    }
                }
            }
        },
    ]

    # Optional clipping (keeps charts readable)
    if clip_max_days > 0:
        pipeline_values.append({"$match": {"numdays": {"$gte": 0, "$lte": clip_max_days}}})

    values = [d["numdays"] for d in coll.aggregate(pipeline_values, allowDiskUse=True) if d.get("numdays") is not None]
    obs = len(values)

    if obs == 0:
        return jsonify(
            {
                "time_utc": datetime.utcnow().isoformat() + "Z",
                "N_base": len(base_ids),
                "obs": 0,
                "buckets": [],
                "stats": {"min": None, "max": None, "avg": None},
            }
        )

    vmin = min(values)
    vmax = max(values)
    avg = sum(values) / obs

    # Build histogram buckets in Python for simplicity (dev subsample size)
    # Equal-width buckets over [vmin, vmax] (or [0, clip_max_days] when clipped)
    lo = 0 if (clip_max_days > 0) else vmin
    hi = clip_max_days if (clip_max_days > 0) else vmax
    if hi <= lo:
        hi = lo + 1

    width = (hi - lo) / buckets
    if width <= 0:
        width = 1

    counts = [0] * buckets
    for x in values:
        if x < lo or x > hi:
            continue
        idx = int((x - lo) / width)
        if idx >= buckets:
            idx = buckets - 1
        if idx < 0:
            idx = 0
        counts[idx] += 1

    out_buckets = []
    for i, n in enumerate(counts):
        b_lo = int(lo + i * width)
        b_hi = int(lo + (i + 1) * width - 1)
        out_buckets.append({"lo": b_lo, "hi": b_hi, "n": n})

    return jsonify(
        {
            "time_utc": datetime.utcnow().isoformat() + "Z",
            "N_base": len(base_ids),
            "obs": obs,
            "stats": {"min": vmin, "max": vmax, "avg": avg},
            "buckets": out_buckets,
        }
    )
