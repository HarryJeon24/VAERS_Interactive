# backend/api/signals.py
from __future__ import annotations

from datetime import datetime
from math import exp, log, sqrt
from typing import Any, Dict, List, Tuple, Optional

from flask import Blueprint, jsonify, request

from backend.db.mongo import get_db
from backend.services.cache import CACHE, stable_hash
from backend.services.filters import build_filters

bp = Blueprint("signals_api", __name__, url_prefix="/api")


def _compute_metrics(
        N: int,
        a: int,
        vax_total: int,
        sym_total: int,
        *,
        cc: float = 0.5,
) -> Dict[str, Any]:
    """
    Compute PRR/ROR and (Wald) CIs with optional continuity correction (cc).
    """
    a0 = float(a)
    b0 = float(max(vax_total - a, 0))
    c0 = float(max(sym_total - a, 0))
    d0 = float(max(N - a0 - b0 - c0, 0))

    if N <= 0 or a0 < 0 or b0 < 0 or c0 < 0 or d0 < 0:
        return {"a": a, "b": int(b0), "c": int(c0), "d": int(d0),
                "prr": None, "prr_ci": None, "ror": None, "ror_ci": None}

    use_cc = (a0 == 0 or b0 == 0 or c0 == 0 or d0 == 0) and cc > 0
    a1, b1, c1, d1 = (a0 + cc, b0 + cc, c0 + cc, d0 + cc) if use_cc else (a0, b0, c0, d0)

    # PRR
    prr = None
    if (a1 + b1) > 0 and (c1 + d1) > 0 and c1 > 0:
        prr = (a1 / (a1 + b1)) / (c1 / (c1 + d1))

    # ROR
    ror = None
    if a1 > 0 and b1 > 0 and c1 > 0 and d1 > 0:
        ror = (a1 / b1) / (c1 / d1)

    prr_ci = None
    ror_ci = None
    z = 1.96

    if prr is not None and a1 > 0 and b1 > 0 and c1 > 0 and d1 > 0:
        try:
            log_prr = log(prr)
            se_prr = sqrt(1.0 / a1 - 1.0 / (a1 + b1) + 1.0 / c1 - 1.0 / (c1 + d1))
            prr_ci = [exp(log_prr - z * se_prr), exp(log_prr + z * se_prr)]
        except (ValueError, ZeroDivisionError):
            prr_ci = None

    if ror is not None and a1 > 0 and b1 > 0 and c1 > 0 and d1 > 0:
        try:
            log_ror = log(ror)
            se_ror = sqrt(1.0 / a1 + 1.0 / b1 + 1.0 / c1 + 1.0 / d1)
            ror_ci = [exp(log_ror - z * se_ror), exp(log_ror + z * se_ror)]
        except (ValueError, ZeroDivisionError):
            ror_ci = None

    return {
        "a": int(a0),
        "b": int(b0),
        "c": int(c0),
        "d": int(d0),
        "cc_applied": use_cc,
        "prr": prr,
        "prr_ci": prr_ci,
        "ror": ror,
        "ror_ci": ror_ci,
    }


def _get_base_ids(
        data_match: Dict[str, Any],
        join_filters: Dict[str, Any],
        onset_min: Optional[float] = None,
        onset_max: Optional[float] = None,
        *,
        base_id_cap: int = 0,
) -> List[int]:
    """
    Build base universe VAERS_IDs.
    UPDATED: Now includes aggregation logic to filter by Onset Days.
    """
    db = get_db()

    vax_type = join_filters.get("vax_type")
    vax_manu = join_filters.get("vax_manu")
    symptom_term = join_filters.get("symptom_term")

    base_ids_set = None

    # 1. Pre-filter by Vaccine Table
    if vax_type or vax_manu:
        vax_match: Dict[str, Any] = {}
        if vax_type: vax_match["VAX_TYPE"] = vax_type
        if vax_manu: vax_match["VAX_MANU"] = vax_manu

        vax_ids = set(
            doc["VAERS_ID"]
            for doc in db["vaers_vax"].find(vax_match, {"VAERS_ID": 1})
            if doc.get("VAERS_ID") is not None
        )
        base_ids_set = vax_ids

    # 2. Pre-filter by Symptom Table
    if symptom_term:
        pt = symptom_term.strip()
        sym_match = {
            "$or": [
                {"SYMPTOM1": pt}, {"SYMPTOM2": pt}, {"SYMPTOM3": pt}, {"SYMPTOM4": pt}, {"SYMPTOM5": pt},
            ]
        }
        sym_ids = set(
            doc["VAERS_ID"]
            for doc in db["vaers_symptoms"].find(sym_match, {"VAERS_ID": 1})
            if doc.get("VAERS_ID") is not None
        )

        if base_ids_set is not None:
            base_ids_set = base_ids_set.intersection(sym_ids)
        else:
            base_ids_set = sym_ids

    # 3. Combine with Main Data Filters
    final_match = data_match.copy()
    if base_ids_set is not None:
        final_match["VAERS_ID"] = {"$in": list(base_ids_set)}

    # 4. EXECUTE QUERY
    # Strategy A: No Onset Filter -> Use Fast .find()
    if onset_min is None and onset_max is None:
        projection = {"VAERS_ID": 1}
        query = db["vaers_data"].find(final_match, projection)
        if base_id_cap and base_id_cap > 0:
            query = query.limit(int(base_id_cap))
        return [doc["VAERS_ID"] for doc in query if doc.get("VAERS_ID") is not None]

    # Strategy B: Onset Filter -> Use Aggregation Pipeline (Slower but necessary)
    else:
        pipeline = [{"$match": final_match}]

        # Calculate Days
        pipeline.append({
            "$addFields": {
                "_vax_dt": {"$convert": {"input": "$VAX_DATE", "to": "date", "onError": None, "onNull": None}},
                "_onset_dt": {"$convert": {"input": "$ONSET_DATE", "to": "date", "onError": None, "onNull": None}}
            }
        })
        pipeline.append({
            "$addFields": {
                "calc_days": {
                    "$cond": [
                        {"$and": [{"$ne": ["$_vax_dt", None]}, {"$ne": ["$_onset_dt", None]}]},
                        {"$dateDiff": {"startDate": "$_vax_dt", "endDate": "$_onset_dt", "unit": "day"}},
                        None
                    ]
                }
            }
        })

        # Apply Range Filter
        range_match = {}
        if onset_min is not None: range_match["$gte"] = onset_min
        if onset_max is not None: range_match["$lte"] = onset_max
        pipeline.append({"$match": {"calc_days": range_match}})

        # Limit
        if base_id_cap and base_id_cap > 0:
            pipeline.append({"$limit": int(base_id_cap)})

        # Project
        pipeline.append({"$project": {"VAERS_ID": 1}})

        return [doc["VAERS_ID"] for doc in db["vaers_data"].aggregate(pipeline, allowDiskUse=True) if
                doc.get("VAERS_ID") is not None]


def _build_vax_marginals(base_ids: List[int], join_filters: Dict[str, Any]) -> Dict[Tuple[str, str], int]:
    db = get_db()
    vax_type = join_filters.get("vax_type")
    vax_manu = join_filters.get("vax_manu")

    pipeline: List[Dict[str, Any]] = [
        {"$match": {"VAERS_ID": {"$in": base_ids}}},
        {"$lookup": {"from": "vaers_vax", "localField": "VAERS_ID", "foreignField": "VAERS_ID", "as": "vax"}},
        {"$unwind": "$vax"},
        {"$project": {"vax_type": "$vax.VAX_TYPE", "vax_manu": "$vax.VAX_MANU"}},
        {"$match": {"vax_type": {"$ne": None}}},
    ]
    if vax_type or vax_manu:
        cond: Dict[str, Any] = {}
        if vax_type: cond["vax_type"] = vax_type
        if vax_manu: cond["vax_manu"] = vax_manu
        pipeline.append({"$match": cond})

    pipeline.append({"$group": {"_id": {"vax_type": "$vax_type", "vax_manu": "$vax_manu"}, "vax_total": {"$sum": 1}}})

    out: Dict[Tuple[str, str], int] = {}
    for doc in db["vaers_data"].aggregate(pipeline, allowDiskUse=True):
        out[(doc["_id"].get("vax_type") or "", doc["_id"].get("vax_manu") or "")] = int(doc["vax_total"])
    return out


def _build_sym_marginals(base_ids: List[int], join_filters: Dict[str, Any]) -> Dict[str, int]:
    db = get_db()
    symptom_term = join_filters.get("symptom_term")

    pipeline: List[Dict[str, Any]] = [
        {"$match": {"VAERS_ID": {"$in": base_ids}}},
        {"$lookup": {"from": "vaers_symptoms", "localField": "VAERS_ID", "foreignField": "VAERS_ID", "as": "sym"}},
        {"$unwind": "$sym"},
        {"$project": {"pt": ["$sym.SYMPTOM1", "$sym.SYMPTOM2", "$sym.SYMPTOM3", "$sym.SYMPTOM4", "$sym.SYMPTOM5"]}},
        {"$unwind": "$pt"},
        {"$match": {"pt": {"$ne": None, "$ne": ""}}},
    ]
    if symptom_term:
        pipeline.append({"$match": {"pt": symptom_term.strip()}})

    pipeline.append({"$group": {"_id": "$pt", "sym_total": {"$sum": 1}}})

    out: Dict[str, int] = {}
    for doc in db["vaers_data"].aggregate(pipeline, allowDiskUse=True):
        out[doc["_id"]] = int(doc["sym_total"])
    return out


def _build_pairs(base_ids: List[int], join_filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    db = get_db()
    vax_type = join_filters.get("vax_type")
    vax_manu = join_filters.get("vax_manu")
    symptom_term = join_filters.get("symptom_term")

    pipeline: List[Dict[str, Any]] = [
        {"$match": {"VAERS_ID": {"$in": base_ids}}},
        {"$lookup": {"from": "vaers_vax", "localField": "VAERS_ID", "foreignField": "VAERS_ID", "as": "vax"}},
        {"$unwind": "$vax"},
        {"$project": {"vax_type": "$vax.VAX_TYPE", "vax_manu": "$vax.VAX_MANU", "VAERS_ID": 1}},
        {"$match": {"vax_type": {"$ne": None}}},
    ]
    if vax_type or vax_manu:
        cond: Dict[str, Any] = {}
        if vax_type: cond["vax_type"] = vax_type
        if vax_manu: cond["vax_manu"] = vax_manu
        pipeline.append({"$match": cond})

    pipeline += [
        {"$lookup": {"from": "vaers_symptoms", "localField": "VAERS_ID", "foreignField": "VAERS_ID", "as": "sym"}},
        {"$unwind": "$sym"},
        {"$project": {"vax_type": 1, "vax_manu": 1,
                      "pt": ["$sym.SYMPTOM1", "$sym.SYMPTOM2", "$sym.SYMPTOM3", "$sym.SYMPTOM4", "$sym.SYMPTOM5"]}},
        {"$unwind": "$pt"},
        {"$match": {"pt": {"$ne": None, "$ne": ""}}},
    ]

    if symptom_term:
        pipeline.append({"$match": {"pt": symptom_term.strip()}})

    pipeline.append(
        {"$group": {"_id": {"vax_type": "$vax_type", "vax_manu": "$vax_manu", "pt": "$pt"}, "a": {"$sum": 1}}})

    return list(db["vaers_data"].aggregate(pipeline, allowDiskUse=True))


@bp.get("/signals")
def signals():
    """
    /api/signals
    Calculates statistical signals (PRR, ROR).
    Filters: Standard, Manual, AND Onset Days.
    Safety: Enforces 50k hard cap.
    """
    f, data_match, join_filters = build_filters(request)

    # 1. --- Manual Filter Logic ---
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
    # ------------------------------

    # 2. Extract Onset Filters (Missing Link Fixed)
    onset_min_raw = request.args.get("onset_days_min", "").strip()
    onset_max_raw = request.args.get("onset_days_max", "").strip()

    onset_min = None
    if onset_min_raw:
        try:
            onset_min = float(onset_min_raw)
        except ValueError:
            pass

    onset_max = None
    if onset_max_raw:
        try:
            onset_max = float(onset_max_raw)
        except ValueError:
            pass

    # 3. Parameters
    min_count = max(1, int(request.args.get("min_count", "5") or 5))
    min_vax_total = int(request.args.get("min_vax_total", "20") or 20)
    min_sym_total = int(request.args.get("min_sym_total", "20") or 20)
    limit = max(10, min(200, int(request.args.get("limit", "50") or 50)))
    cc = float(request.args.get("cc", "0.5") or 0.5)

    sort_by = (request.args.get("sort_by") or "prr").lower()
    if sort_by not in ("prr", "ror", "a"):
        sort_by = "prr"

    base_id_cap = 50000  # Hard safety limit

    cache_key = stable_hash({
        "endpoint": "signals_v4",
        "args": request.args.to_dict(flat=True),
        "hard_cap": base_id_cap
    })

    cached = CACHE.get(cache_key)
    if cached is not None:
        return jsonify({**cached, "cached": True})

    def compute():
        # Pass onset filters to ID fetcher
        base_ids = _get_base_ids(
            data_match,
            join_filters,
            onset_min=onset_min,
            onset_max=onset_max,
            base_id_cap=base_id_cap
        )
        N = len(base_ids)

        if N == 0:
            return {
                "time_utc": datetime.utcnow().isoformat() + "Z",
                "cached": False,
                "filters": {"parsed": f.__dict__, "vaers_data_match": data_match, "join_filters": join_filters},
                "N": 0,
                "rows": [],
                "message": "No reports matched the filters.",
            }

        vax_marg = _build_vax_marginals(base_ids, join_filters)
        sym_marg = _build_sym_marginals(base_ids, join_filters)
        pair_docs = _build_pairs(base_ids, join_filters)

        top_symptoms: List[Dict[str, Any]] = []
        if not join_filters.get("symptom_term"):
            sorted_symptoms = sorted(sym_marg.items(), key=lambda x: x[1], reverse=True)[:3]
            top_symptoms = [{"symptom": sym, "count": count} for sym, count in sorted_symptoms]

        rows: List[Dict[str, Any]] = []
        for doc in pair_docs:
            _id = doc["_id"]
            a = int(doc.get("a", 0))
            if a < min_count: continue

            vax_type = _id.get("vax_type") or ""
            vax_manu = _id.get("vax_manu") or ""
            pt = _id.get("pt") or ""

            vax_total = vax_marg.get((vax_type, vax_manu), 0)
            sym_total = sym_marg.get(pt, 0)

            if vax_total < min_vax_total or sym_total < min_sym_total: continue

            metrics = _compute_metrics(N=N, a=a, vax_total=vax_total, sym_total=sym_total, cc=cc)

            rows.append({
                "vax_type": vax_type,
                "vax_manu": vax_manu,
                "symptom": pt,
                "a": metrics["a"],
                "b": metrics["b"],
                "c": metrics["c"],
                "d": metrics["d"],
                "vax_total": vax_total,
                "sym_total": sym_total,
                "cc_applied": metrics["cc_applied"],
                "prr": metrics["prr"],
                "prr_ci": metrics["prr_ci"],
                "ror": metrics["ror"],
                "ror_ci": metrics["ror_ci"],
            })

        def sk(row):
            if sort_by == "a": return (-row["a"], row["symptom"])
            if sort_by == "ror": return (-(row["ror"] or 0.0), row["symptom"])
            return (-(row["prr"] or 0.0), row["symptom"])

        rows.sort(key=sk)
        rows = rows[:limit]

        result_dict = {
            "time_utc": datetime.utcnow().isoformat() + "Z",
            "cached": False,
            "filters": {"parsed": f.__dict__, "vaers_data_match": data_match, "join_filters": join_filters},
            "N": N,
            "params": {
                "min_count": min_count,
                "min_vax_total": min_vax_total,
                "min_sym_total": min_sym_total,
                "sort_by": sort_by,
                "limit": limit,
                "cc": cc,
                "base_id_cap": base_id_cap,
            },
            "rows": rows,
        }
        if top_symptoms: result_dict["top_symptoms"] = top_symptoms
        return result_dict

    result = compute()
    CACHE.set(cache_key, result, ttl_seconds=45)
    return jsonify(result)


def main() -> None:
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(bp)
    app.run(host="127.0.0.1", port=5002, debug=True)


if __name__ == "__main__":
    main()