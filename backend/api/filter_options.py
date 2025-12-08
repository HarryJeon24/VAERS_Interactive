"""
API endpoints for fetching unique filter option values.
These endpoints provide autocomplete data for filter fields.
"""

from flask import Blueprint, jsonify
from backend.db.mongo import get_db

bp = Blueprint("filter_options", __name__, url_prefix="/api/filter-options")


def _split_and_clean(values):
    """
    Split comma-separated values and clean them.
    Returns a sorted list of unique individual items.
    """
    items = set()
    for val in values:
        if not val or not str(val).strip():
            continue
        # Split by comma and clean each item
        parts = str(val).split(',')
        for part in parts:
            cleaned = part.strip()
            if cleaned:
                items.add(cleaned)
    return sorted(list(items))


@bp.get("/vax_type")
def get_vax_types():
    """Get unique vaccine types from vaers_vax collection."""
    try:
        db = get_db()
        values = db["vaers_vax"].distinct("VAX_TYPE")
        # Filter out None/empty values, convert to uppercase, and sort
        values = sorted(list(set([str(v).upper().strip() for v in values if v and str(v).strip()])))
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500


@bp.get("/vax_manu")
def get_vax_manufacturers():
    """Get unique vaccine manufacturers from vaers_vax collection."""
    try:
        db = get_db()
        values = db["vaers_vax"].distinct("VAX_MANU")
        # Filter out None/empty values and sort
        values = sorted([v for v in values if v and str(v).strip()])
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500


@bp.get("/symptom_term")
def get_symptom_terms():
    """Get unique symptom terms from vaers_symptoms collection."""
    try:
        db = get_db()
        # Try multiple possible field name variations
        symptoms = set()

        # Check which fields exist in the collection
        sample = db["vaers_symptoms"].find_one()
        if not sample:
            return jsonify({"values": []})

        # Look for symptom fields (try different naming conventions)
        symptom_fields = []
        for key in sample.keys():
            if 'SYMPTOM' in key.upper() and key != 'SYMPTOM_TEXT':
                symptom_fields.append(key)

        # If no symptom fields found, try standard names
        if not symptom_fields:
            symptom_fields = ["SYMPTOM1", "SYMPTOM2", "SYMPTOM3", "SYMPTOM4", "SYMPTOM5"]

        # Get all documents and extract symptom fields
        for field in symptom_fields:
            try:
                values = db["vaers_symptoms"].distinct(field)
                symptoms.update([v for v in values if v and str(v).strip()])
            except:
                continue

        values = sorted(list(symptoms))
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500


@bp.get("/other_meds")
def get_other_meds():
    """Get unique other medications from vaers_data collection (split comma-separated)."""
    try:
        db = get_db()
        raw_values = db["vaers_data"].distinct("OTHER_MEDS")
        # Split comma-separated values into individual items
        values = _split_and_clean(raw_values)
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500


@bp.get("/cur_ill")
def get_cur_ill():
    """Get unique current illnesses from vaers_data collection (split comma-separated)."""
    try:
        db = get_db()
        raw_values = db["vaers_data"].distinct("CUR_ILL")
        # Split comma-separated values into individual items
        values = _split_and_clean(raw_values)
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500


@bp.get("/history")
def get_history():
    """Get unique medical history values from vaers_data collection (split comma-separated)."""
    try:
        db = get_db()
        raw_values = db["vaers_data"].distinct("HISTORY")
        # Split comma-separated values into individual items
        values = _split_and_clean(raw_values)
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500


@bp.get("/prior_vax")
def get_prior_vax():
    """Get unique prior vaccination values from vaers_data collection (split comma-separated)."""
    try:
        db = get_db()
        raw_values = db["vaers_data"].distinct("PRIOR_VAX")
        # Split comma-separated values into individual items
        values = _split_and_clean(raw_values)
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500


@bp.get("/allergies")
def get_allergies():
    """Get unique allergy values from vaers_data collection (split comma-separated)."""
    try:
        db = get_db()
        raw_values = db["vaers_data"].distinct("ALLERGIES")
        # Split comma-separated values into individual items
        values = _split_and_clean(raw_values)
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500


@bp.get("/state")
def get_states():
    """Get unique state codes from vaers_data collection."""
    try:
        db = get_db()
        values = db["vaers_data"].distinct("STATE")
        # Filter out None/empty values and sort
        values = sorted([v for v in values if v and str(v).strip()])
        return jsonify({"values": values})
    except Exception as e:
        return jsonify({"error": str(e), "values": []}), 500
