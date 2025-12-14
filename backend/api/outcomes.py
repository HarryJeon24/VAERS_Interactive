from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from backend.db.mongo import get_db
from backend.services.filters import build_filters

bp = Blueprint("outcomes_api", __name__, url_prefix="/api")

OUTCOME_KEYS = [
    ("DIED", "Died"),
    ("HOSPITAL", "Hospitalized"),
    ("L_THREAT", "Life-threatening"),
    ("DISABLE", "Disabled"),
    ("BIRTH_DEFECT", "Birth defect"),
    ("RECOVD", "Recovered"),
]


def _nonempty(s: Any) -> bool:
    if s is None:
        return False
    if isinstance(s, str):
        return bool(s.strip())
    return bool(s)


@bp.get("/outcomes")
def outcomes():
    f, data_match, join_filters = build_filters(request)

    # IMPORTANT:
    # Building a huge list of VAERS_IDs and sending {"$in": [...]} will exceed MongoDB's
    # 16MB command/document limit on large datasets. So we avoid "$in base_ids" entirely
    # and apply join constraints via $lookup.
    base_id_cap = int(request.args.get("base_id_cap", 0) or 0)

    vax_type = join_filters.get("vax_type")
    vax_manu = join_filters.get("vax_manu")
    symptom_term = join_filters.get("symptom_term")
    symptom_text = join_filters.get("symptom_text")

    db = get_db()
    coll = db["vaers_data"]

    pipeline: List[Dict[str, Any]] = []

    # Base filters on vaers_data
    if data_match:
        pipeline.append({"$match": data_match})

    # Optional cap to keep dev/testing responsive on huge DBs
    if base_id_cap and base_id_cap > 0:
        # stable ordering (index on VAERS_ID strongly recommended)
        pipeline.append({"$sort": {"VAERS_ID": 1}})
        pipeline.append({"$limit": int(base_id_cap)})

    # Vaccine-side constraints via $lookup (no giant "$in" lists)
    if _nonempty(vax_type) or _nonempty(vax_manu):
        vax_pipeline: List[Dict[str, Any]] = [
            {"$match": {"$expr": {"$eq": ["$VAERS_ID", "$$id"]}}}
        ]
        if _nonempty(vax_type):
            vax_pipeline.append({"$match": {"VAX_TYPE": str(vax_type).strip()}})
        if _nonempty(vax_manu):
            vax_pipeline.append({"$match": {"VAX_MANU": str(vax_manu).strip()}})
        vax_pipeline.append({"$limit": 1})

        pipeline.extend(
            [
                {
                    "$lookup": {
                        "from": "vaers_vax",
                        "let": {"id": "$VAERS_ID"},
                        "pipeline": vax_pipeline,
                        "as": "_vax",
                    }
                },
                {"$match": {"_vax.0": {"$exists": True}}},
            ]
        )

    # Symptom-side constraints via $lookup
    if _nonempty(symptom_term) or _nonempty(symptom_text):
        sym_pipeline: List[Dict[str, Any]] = [
            {"$match": {"$expr": {"$eq": ["$VAERS_ID", "$$id"]}}}
        ]

        # Exact MedDRA PT match (SYMPTOM1..5)
        if _nonempty(symptom_term):
            term = str(symptom_term).strip()
            sym_pipeline.append(
                {
                    "$match": {
                        "$or": [
                            {"SYMPTOM1": term},
                            {"SYMPTOM2": term},
                            {"SYMPTOM3": term},
                            {"SYMPTOM4": term},
                            {"SYMPTOM5": term},
                        ]
                    }
                }
            )

        # Text contains match across SYMPTOM1..5 (case-insensitive)
        if _nonempty(symptom_text):
            txt = str(symptom_text).strip()
            sym_pipeline.append(
                {
                    "$match": {
                        "$or": [
                            {"SYMPTOM1": {"$regex": txt, "$options": "i"}},
                            {"SYMPTOM2": {"$regex": txt, "$options": "i"}},
                            {"SYMPTOM3": {"$regex": txt, "$options": "i"}},
                            {"SYMPTOM4": {"$regex": txt, "$options": "i"}},
                            {"SYMPTOM5": {"$regex": txt, "$options": "i"}},
                        ]
                    }
                }
            )

        sym_pipeline.append({"$limit": 1})

        pipeline.extend(
            [
                {
                    "$lookup": {
                        "from": "vaers_symptoms",
                        "let": {"id": "$VAERS_ID"},
                        "pipeline": sym_pipeline,
                        "as": "_sym",
                    }
                },
                {"$match": {"_sym.0": {"$exists": True}}},
            ]
        )

    # Aggregate outcomes from filtered vaers_data
    pipeline.append(
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                **{
                    k: {"$sum": {"$cond": [{"$eq": [f"${k}", "Y"]}, 1, 0]}}
                    for k, _ in OUTCOME_KEYS
                },
            }
        }
    )

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
            "N_base": total,
            "total": total,
            "outcomes": [{"key": label, "count": counts[k]} for k, label in OUTCOME_KEYS],
        }
    )
