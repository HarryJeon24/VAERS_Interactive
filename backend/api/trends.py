from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from backend.db.mongo import get_db
from backend.services.filters import build_filters
from backend.api.signals import _get_base_ids

bp = Blueprint("trends", __name__, url_prefix="/api")


@bp.get("/trends")
def trends():
    """
    Returns aggregation of reports over time (Monthly).
    Defaults to last 12 months to prevent UI clutter.
    """
    try:
        f, data_match, join_filters = build_filters(request)

        # --- Manual Filter Logic ---
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
        # ---------------------------

        # DEFAULT CHANGE: Default to 12 months if not specified
        # If user explicitly sends "0", we respect it (All Time).
        # If param is missing, we default to 12.
        clip_raw = request.args.get("clip_months")
        if clip_raw is None or clip_raw.strip() == "":
            clip_months = 12
        else:
            clip_months = int(clip_raw)

        clip_months = max(0, clip_months)

        db = get_db()
        coll = db["vaers_data"]

        # Strategy: Broad Query vs Specific
        is_broad_query = False
        if join_filters.get("vax_type") and str(join_filters["vax_type"]).upper() == "COVID19":
            is_broad_query = True

        pipeline = []
        has_complex_join = bool(join_filters)

        if has_complex_join:
            if is_broad_query:
                # Direct Pipeline (Safe for massive sets)
                pipeline.append({"$match": data_match})
                if join_filters.get("vax_type") or join_filters.get("vax_manu"):
                    pipeline.append({
                        "$lookup": {"from": "vaers_vax", "localField": "VAERS_ID", "foreignField": "VAERS_ID",
                                    "as": "_vax"}
                    })
                    v_match = {}
                    if join_filters.get("vax_type"): v_match["_vax.VAX_TYPE"] = join_filters["vax_type"]
                    if join_filters.get("vax_manu"): v_match["_vax.VAX_MANU"] = join_filters["vax_manu"]
                    pipeline.append({"$match": v_match})

                if join_filters.get("symptom_term"):
                    term = join_filters["symptom_term"]
                    pipeline.append({
                        "$lookup": {"from": "vaers_symptoms", "localField": "VAERS_ID", "foreignField": "VAERS_ID",
                                    "as": "_sym"}
                    })
                    pipeline.append({
                        "$match": {
                            "$or": [
                                {"_sym.SYMPTOM1": term}, {"_sym.SYMPTOM2": term},
                                {"_sym.SYMPTOM3": term}, {"_sym.SYMPTOM4": term},
                                {"_sym.SYMPTOM5": term}
                            ]
                        }
                    })
            else:
                # ID Fetch (Faster for small sets)
                base_id_cap = int(request.args.get("base_id_cap", "0") or 0)
                if base_id_cap == 0: base_id_cap = 50000

                base_ids = _get_base_ids(data_match, join_filters, base_id_cap=base_id_cap)
                if not base_ids:
                    return jsonify({"series": [], "points": 0, "N_base": 0, "time_utc": datetime.utcnow().isoformat()})

                pipeline.append({"$match": {"VAERS_ID": {"$in": base_ids}}})
        else:
            pipeline.append({"$match": data_match})

        # Count Total (Skip for broad to save time)
        if is_broad_query:
            N_base = -1
        else:
            try:
                if pipeline and "$match" in pipeline[0]:
                    N_base = coll.count_documents(pipeline[0]["$match"])
                else:
                    N_base = 0
            except:
                N_base = 0

        # Aggregation
        pipeline.extend([
            {
                "$project": {
                    "date": {
                        "$convert": {"input": "$RECVDATE", "to": "date", "onError": None, "onNull": None}
                    }
                }
            },
            {"$match": {"date": {"$ne": None}}},
            {
                "$group": {
                    "_id": {"y": {"$year": "$date"}, "m": {"$month": "$date"}},
                    "n": {"$sum": 1}
                }
            },
            {"$sort": {"_id.y": 1, "_id.m": 1}}
        ])

        raw_series = list(coll.aggregate(pipeline, allowDiskUse=True))

        series = []
        for item in raw_series:
            y = item["_id"]["y"]
            m = item["_id"]["m"]
            label = f"{y}-{m:02d}"
            series.append({"month": label, "n": item["n"]})

        # Apply Clip (Python side)
        if clip_months > 0:
            series = series[-clip_months:]

        points = sum(p["n"] for p in series)

        return jsonify({
            "series": series,
            "points": points,
            "N_base": N_base if N_base != -1 else points,
            "time_utc": datetime.utcnow().isoformat()
        })

    except Exception as e:
        return jsonify({"error": str(e), "series": []}), 500