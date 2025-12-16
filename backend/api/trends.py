from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from backend.db.mongo import get_db
from backend.services.filters import build_filters

bp = Blueprint("trends", __name__, url_prefix="/api")


@bp.get("/trends")
def trends():
    """
    Returns aggregation of reports over time (Monthly).
    Counts ALL matching records (no 50k cap).
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

        # Default to 12 months if not specified
        clip_raw = request.args.get("clip_months")
        if clip_raw is None or clip_raw.strip() == "":
            clip_months = 12
        else:
            clip_months = int(clip_raw)

        clip_months = max(0, clip_months)

        db = get_db()
        coll = db["vaers_data"]

        # Build Aggregation Pipeline
        # We ALWAYS use the pipeline approach to ensure we count EVERYTHING.
        # No 'base_id_cap' limitation for Trends.
        pipeline = []

        # 1. Filter by Main Data (Sex, Age, Year, State)
        pipeline.append({"$match": data_match})

        # 2. Join with Vaccine Table if needed
        if join_filters.get("vax_type") or join_filters.get("vax_manu"):
            pipeline.append({
                "$lookup": {
                    "from": "vaers_vax",
                    "localField": "VAERS_ID",
                    "foreignField": "VAERS_ID",
                    "as": "_vax"
                }
            })
            v_match = {}
            if join_filters.get("vax_type"): v_match["_vax.VAX_TYPE"] = join_filters["vax_type"]
            if join_filters.get("vax_manu"): v_match["_vax.VAX_MANU"] = join_filters["vax_manu"]
            pipeline.append({"$match": v_match})

        # 3. Join with Symptoms Table if needed
        if join_filters.get("symptom_term"):
            term = join_filters["symptom_term"]
            pipeline.append({
                "$lookup": {
                    "from": "vaers_symptoms",
                    "localField": "VAERS_ID",
                    "foreignField": "VAERS_ID",
                    "as": "_sym"
                }
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

        # 4. Project & Group by Date
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

        # Calculate total points BEFORE clipping to get the true "Base N" for this timeline
        total_points = sum(p["n"] for p in series)

        # Apply Clip (Python side) - show only last N months
        if clip_months > 0:
            series = series[-clip_months:]

        displayed_points = sum(p["n"] for p in series)

        return jsonify({
            "series": series,
            "points": displayed_points,
            "N_base": total_points,
            "time_utc": datetime.utcnow().isoformat()
        })

    except Exception as e:
        return jsonify({"error": str(e), "series": []}), 500