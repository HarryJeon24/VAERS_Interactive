"""
backend/api/filter_options.py

Filter-option endpoints for UI dropdowns and typeahead.
- Supports ?q=<text>&limit=<n> on all endpoints.
- Uses caching via backend/services/cache.py (CACHE + stable_hash).
- For symptom terms:
    - If precomputed collection `symptom_terms` exists, uses it (FAST, indexed).
    - Otherwise falls back to aggregating from vaers_symptoms (SLOW, cached).

Response shape (backward compatible):
- Always returns {"values": [<string>...]}
- Also returns {"items": [{"value": str, "n": int, ...}, ...]} for typeahead UIs.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from backend.db.mongo import get_db
from backend.services.cache import CACHE, stable_hash

bp = Blueprint("filter_options", __name__, url_prefix="/api/filter-options")


# -------------------------
# Helpers
# -------------------------

def _clamp_int(x: Any, default: int, lo: int, hi: int) -> int:
    try:
        v = int(x)
    except Exception:
        v = int(default)
    return max(lo, min(hi, v))


def _norm_q(q: Any) -> str:
    return str(q or "").strip()


def _make_regex(q: str, mode: str = "prefix") -> str:
    """
    Build a safe regex string for MongoDB based on user input.
    mode="prefix"   -> ^<escaped>
    mode="contains" -> <escaped>
    """
    q = _norm_q(q)
    if not q:
        return ""
    esc = re.escape(q)
    return esc if mode == "contains" else "^" + esc


def _cache_key(endpoint: str, params: Dict[str, Any]) -> str:
    return stable_hash({"endpoint": endpoint, "params": params})


def _values_only(items: List[Dict[str, Any]]) -> List[str]:
    return [it["value"] for it in items if it.get("value")]


def _distinct_with_optional_q(coll, field: str, q: str, limit: int) -> List[str]:
    """
    For small-cardinality fields (STATE, VAX_TYPE, VAX_MANU).
    Uses distinct() and filters in Python.
    """
    raw = coll.distinct(field)
    vals: List[str] = []
    qn = q.lower()
    for v in raw:
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        if q and qn not in s.lower():
            continue
        vals.append(s)
    vals = sorted(list(set(vals)))
    if limit and limit > 0:
        vals = vals[:limit]
    return vals


def _split_field_suggestions(
    coll,
    field: str,
    q: str,
    limit: int,
    *,
    regex_mode: str = "prefix",
    max_item_len: int = 80,
) -> List[Dict[str, Any]]:
    """
    For comma-separated text fields in vaers_data:
      OTHER_MEDS, CUR_ILL, HISTORY, PRIOR_VAX, ALLERGIES

    Returns top N cleaned items with counts.
    Uses an aggregation pipeline (server-side split/unwind/group).
    """
    q = _norm_q(q)
    rx = _make_regex(q, mode=regex_mode) if q else ""

    pipeline: List[Dict[str, Any]] = [
        {"$match": {field: {"$type": "string", "$ne": ""}}},
        {
            "$project": {
                "_id": 0,
                "item": {
                    "$map": {
                        "input": {"$split": [f"${field}", ","]},
                        "as": "it",
                        "in": {"$trim": {"input": "$$it"}},
                    }
                },
            }
        },
        {"$unwind": "$item"},
        {"$match": {"item": {"$ne": "", "$ne": None}}},
        {"$match": {"$expr": {"$lte": [{"$strLenCP": "$item"}, max_item_len]}}},
    ]

    if rx:
        # contains or prefix depending on caller
        pipeline.append({"$match": {"item": {"$regex": rx, "$options": "i"}}})

    pipeline.extend(
        [
            {"$group": {"_id": "$item", "n": {"$sum": 1}}},
            {"$sort": {"n": -1, "_id": 1}},
            {"$limit": int(limit)},
        ]
    )

    docs = list(coll.aggregate(pipeline, allowDiskUse=True))
    return [{"value": str(d["_id"]), "n": int(d["n"])} for d in docs if d.get("_id")]


def _symptom_term_suggestions(
    db,
    q: str,
    limit: int,
    *,
    regex_mode: str = "prefix",
) -> List[Dict[str, Any]]:
    """
    Suggest MedDRA PT symptom terms.

    Fast path:
      If `symptom_terms` exists with docs like:
        { _id: "Syncope", term: "Syncope", term_lc: "syncope", n: 12345, versions: [...] }
      then query it using the indexed `term_lc`.

    Fallback path:
      Aggregate from `vaers_symptoms` by unwinding SYMPTOM1..5 (and versions).
    """
    q = _norm_q(q)
    rx = _make_regex(q, mode=regex_mode) if q else ""

    # ---------- Fast path: precomputed terms ----------
    if "symptom_terms" in db.list_collection_names():
        coll = db["symptom_terms"]

        query: Dict[str, Any] = {}
        q_lc = q.lower().strip()
        if q_lc:
            # IMPORTANT: query term_lc without $options:"i" so term_lc_idx can be used
            # Prefix search only.
            query["term_lc"] = {"$regex": "^" + re.escape(q_lc)}

        cursor = (
            coll.find(query, {"_id": 0, "term": 1, "n": 1, "versions": 1})
            .sort([("n", -1), ("term", 1)])
            .limit(int(limit))
        )

        items: List[Dict[str, Any]] = []
        for d in cursor:
            term = (d.get("term") or "").strip()
            if not term:
                continue
            versions = [str(v) for v in (d.get("versions") or []) if v is not None and str(v).strip()]
            items.append(
                {
                    "value": term,
                    "n": int(d.get("n") or 0),
                    "versions": sorted(set(versions)),
                }
            )
        return items

    # ---------- Fallback: aggregate from vaers_symptoms ----------
    coll = db["vaers_symptoms"]

    symptom_fields = ["SYMPTOM1", "SYMPTOM2", "SYMPTOM3", "SYMPTOM4", "SYMPTOM5"]
    version_fields = ["SYMPTOMVERSION1", "SYMPTOMVERSION2", "SYMPTOMVERSION3", "SYMPTOMVERSION4", "SYMPTOMVERSION5"]

    pairs = [{"term": f"${sf}", "ver": f"${vf}"} for sf, vf in zip(symptom_fields, version_fields)]

    pipeline: List[Dict[str, Any]] = [
        {"$project": {"_id": 0, "pair": pairs}},
        {"$unwind": "$pair"},
        {"$match": {"pair.term": {"$type": "string", "$ne": ""}}},
    ]

    if rx:
        pipeline.append({"$match": {"pair.term": {"$regex": rx, "$options": "i"}}})

    pipeline.extend(
        [
            {
                "$group": {
                    "_id": "$pair.term",
                    "n": {"$sum": 1},
                    "versions": {"$addToSet": "$pair.ver"},
                }
            },
            {"$sort": {"n": -1, "_id": 1}},
            {"$limit": int(limit)},
        ]
    )

    docs = list(coll.aggregate(pipeline, allowDiskUse=True))
    items: List[Dict[str, Any]] = []
    for d in docs:
        term = (d.get("_id") or "").strip()
        if not term:
            continue
        vers = [v for v in (d.get("versions") or []) if v and str(v).strip()]
        items.append({"value": term, "n": int(d.get("n") or 0), "versions": sorted(set(map(str, vers)))})
    return items


# -------------------------
# Routes
# -------------------------

@bp.get("/state")
def get_states():
    try:
        q = _norm_q(request.args.get("q"))
        limit = _clamp_int(request.args.get("limit"), default=60, lo=1, hi=200)

        key = _cache_key("state", {"q": q, "limit": limit})
        cached = CACHE.get(key)
        if cached is not None:
            return jsonify({"values": cached})

        db = get_db()
        values = _distinct_with_optional_q(db["vaers_data"], "STATE", q=q, limit=limit)

        CACHE.set(key, values, ttl_seconds=3600)
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500


@bp.get("/vax_type")
def get_vax_types():
    try:
        q = _norm_q(request.args.get("q"))
        limit = _clamp_int(request.args.get("limit"), default=100, lo=1, hi=500)

        key = _cache_key("vax_type", {"q": q, "limit": limit})
        cached = CACHE.get(key)
        if cached is not None:
            return jsonify({"values": cached})

        db = get_db()
        values = _distinct_with_optional_q(db["vaers_vax"], "VAX_TYPE", q=q, limit=limit)
        values = sorted(list({str(v).upper().strip() for v in values if str(v).strip()}))[:limit]

        CACHE.set(key, values, ttl_seconds=3600)
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500


@bp.get("/vax_manu")
def get_vax_manufacturers():
    try:
        q = _norm_q(request.args.get("q"))
        limit = _clamp_int(request.args.get("limit"), default=100, lo=1, hi=500)

        key = _cache_key("vax_manu", {"q": q, "limit": limit})
        cached = CACHE.get(key)
        if cached is not None:
            return jsonify({"values": cached})

        db = get_db()
        values = _distinct_with_optional_q(db["vaers_vax"], "VAX_MANU", q=q, limit=limit)

        CACHE.set(key, values, ttl_seconds=3600)
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500


@bp.get("/symptom_term")
def get_symptom_terms():
    """
    Typeahead:
      /api/filter-options/symptom_term?q=sync&limit=20

    Returns:
      {
        "values": ["Syncope", ...],
        "items": [{"value":"Syncope","n":1234,"versions":["25.0", ...]}, ...]
      }
    """
    try:
        q = _norm_q(request.args.get("q"))
        limit = _clamp_int(request.args.get("limit"), default=25, lo=1, hi=200)

        key = _cache_key("symptom_term", {"q": q, "limit": limit})
        cached = CACHE.get(key)
        if cached is not None:
            return jsonify({"values": _values_only(cached), "items": cached})

        db = get_db()
        items = _symptom_term_suggestions(db, q=q, limit=limit, regex_mode="prefix")

        CACHE.set(key, items, ttl_seconds=6 * 3600)
        return jsonify({"values": _values_only(items), "items": items})
    except Exception as e:
        return jsonify({"error": str(e), "values": [], "items": []}), 500


@bp.get("/other_meds")
def get_other_meds():
    try:
        q = _norm_q(request.args.get("q"))
        limit = _clamp_int(request.args.get("limit"), default=25, lo=1, hi=200)

        key = _cache_key("other_meds", {"q": q, "limit": limit})
        cached = CACHE.get(key)
        if cached is not None:
            return jsonify({"values": _values_only(cached), "items": cached})

        db = get_db()
        items = _split_field_suggestions(db["vaers_data"], "OTHER_MEDS", q=q, limit=limit, regex_mode="contains")

        CACHE.set(key, items, ttl_seconds=6 * 3600)
        return jsonify({"values": _values_only(items), "items": items})
    except Exception as e:
        return jsonify({"error": str(e), "values": [], "items": []}), 500


@bp.get("/cur_ill")
def get_cur_ill():
    try:
        q = _norm_q(request.args.get("q"))
        limit = _clamp_int(request.args.get("limit"), default=25, lo=1, hi=200)

        key = _cache_key("cur_ill", {"q": q, "limit": limit})
        cached = CACHE.get(key)
        if cached is not None:
            return jsonify({"values": _values_only(cached), "items": cached})

        db = get_db()
        items = _split_field_suggestions(db["vaers_data"], "CUR_ILL", q=q, limit=limit, regex_mode="contains")

        CACHE.set(key, items, ttl_seconds=6 * 3600)
        return jsonify({"values": _values_only(items), "items": items})
    except Exception as e:
        return jsonify({"error": str(e), "values": [], "items": []}), 500


@bp.get("/history")
def get_history():
    try:
        q = _norm_q(request.args.get("q"))
        limit = _clamp_int(request.args.get("limit"), default=25, lo=1, hi=200)

        key = _cache_key("history", {"q": q, "limit": limit})
        cached = CACHE.get(key)
        if cached is not None:
            return jsonify({"values": _values_only(cached), "items": cached})

        db = get_db()
        items = _split_field_suggestions(db["vaers_data"], "HISTORY", q=q, limit=limit, regex_mode="contains")

        CACHE.set(key, items, ttl_seconds=6 * 3600)
        return jsonify({"values": _values_only(items), "items": items})
    except Exception as e:
        return jsonify({"error": str(e), "values": [], "items": []}), 500


@bp.get("/prior_vax")
def get_prior_vax():
    try:
        q = _norm_q(request.args.get("q"))
        limit = _clamp_int(request.args.get("limit"), default=25, lo=1, hi=200)

        key = _cache_key("prior_vax", {"q": q, "limit": limit})
        cached = CACHE.get(key)
        if cached is not None:
            return jsonify({"values": _values_only(cached), "items": cached})

        db = get_db()
        items = _split_field_suggestions(db["vaers_data"], "PRIOR_VAX", q=q, limit=limit, regex_mode="contains")

        CACHE.set(key, items, ttl_seconds=6 * 3600)
        return jsonify({"values": _values_only(items), "items": items})
    except Exception as e:
        return jsonify({"error": str(e), "values": [], "items": []}), 500


@bp.get("/allergies")
def get_allergies():
    try:
        q = _norm_q(request.args.get("q"))
        limit = _clamp_int(request.args.get("limit"), default=25, lo=1, hi=200)

        key = _cache_key("allergies", {"q": q, "limit": limit})
        cached = CACHE.get(key)
        if cached is not None:
            return jsonify({"values": _values_only(cached), "items": cached})

        db = get_db()
        items = _split_field_suggestions(db["vaers_data"], "ALLERGIES", q=q, limit=limit, regex_mode="contains")

        CACHE.set(key, items, ttl_seconds=6 * 3600)
        return jsonify({"values": _values_only(items), "items": items})
    except Exception as e:
        return jsonify({"error": str(e), "values": [], "items": []}), 500
