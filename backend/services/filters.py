# backend/services/filters.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from flask import Request


def _parse_int(x: Optional[str]) -> Optional[int]:
    if x is None:
        return None
    x = x.strip()
    if not x:
        return None
    try:
        return int(x)
    except ValueError:
        return None


def _parse_float(x: Optional[str]) -> Optional[float]:
    if x is None:
        return None
    x = x.strip()
    if not x:
        return None
    try:
        return float(x)
    except ValueError:
        return None


def _parse_date_yyyy_mm_dd(x: Optional[str]) -> Optional[datetime]:
    """
    Expect YYYY-MM-DD from UI. Return datetime object.
    NOTE: This only works for range queries if the corresponding Mongo field is a Date type.
    """
    if x is None:
        return None
    x = x.strip()
    if not x:
        return None
    try:
        return datetime.strptime(x, "%Y-%m-%d")
    except ValueError:
        return None


def _truthy(x: Optional[str]) -> bool:
    return (x or "").strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass(frozen=True)
class FilterSpec:
    """
    Parsed filter options from request args.

    Report-level filters apply to vaers_data directly.
    Vax/symptom filters will be used later in $lookup pipelines.
    """
    year: Optional[int] = None
    sex: Optional[str] = None              # "M" / "F" / "U"
    state: Optional[str] = None            # e.g. "GA"
    age_min: Optional[float] = None
    age_max: Optional[float] = None
    onset_start: Optional[datetime] = None
    onset_end: Optional[datetime] = None

    serious_only: bool = False             # any serious outcome flag == "Y"
    died_only: bool = False
    hospital_only: bool = False

    # Medical history filters
    other_meds: Optional[str] = None       # OTHER_MEDS field
    cur_ill: Optional[str] = None          # CUR_ILL field
    history: Optional[str] = None          # HISTORY field
    prior_vax: Optional[str] = None        # PRIOR_VAX field
    allergies: Optional[str] = None        # ALLERGIES field

    # Join-side filters (used in later feature endpoints)
    vax_type: Optional[str] = None
    vax_manu: Optional[str] = None
    symptom_term: Optional[str] = None     # MedDRA PT term in SYMPTOM1-5
    symptom_text: Optional[str] = None     # free-text SYMPTOM_TEXT (expensive)


def from_request(req: Request) -> FilterSpec:
    args = req.args

    year = _parse_int(args.get("year"))

    sex = (args.get("sex") or "").strip().upper() or None
    if sex not in (None, "M", "F", "U"):
        sex = None

    state = (args.get("state") or "").strip().upper() or None
    if state is not None and len(state) != 2:
        state = None

    age_min = _parse_float(args.get("age_min"))
    age_max = _parse_float(args.get("age_max"))

    onset_start = _parse_date_yyyy_mm_dd(args.get("onset_start"))
    onset_end = _parse_date_yyyy_mm_dd(args.get("onset_end"))

    serious_only = _truthy(args.get("serious_only"))
    died_only = _truthy(args.get("died_only"))
    hospital_only = _truthy(args.get("hospital_only"))

    # Medical history filters (case-insensitive substring search)
    other_meds = (args.get("other_meds") or "").strip() or None
    cur_ill = (args.get("cur_ill") or "").strip() or None
    history = (args.get("history") or "").strip() or None
    prior_vax = (args.get("prior_vax") or "").strip() or None
    allergies = (args.get("allergies") or "").strip() or None

    vax_type = (args.get("vax_type") or "").strip().upper() or None
    vax_manu = (args.get("vax_manu") or "").strip() or None

    symptom_term = (args.get("symptom_term") or "").strip() or None
    symptom_text = (args.get("symptom_text") or "").strip() or None

    return FilterSpec(
        year=year,
        sex=sex,
        state=state,
        age_min=age_min,
        age_max=age_max,
        onset_start=onset_start,
        onset_end=onset_end,
        serious_only=serious_only,
        died_only=died_only,
        hospital_only=hospital_only,
        other_meds=other_meds,
        cur_ill=cur_ill,
        history=history,
        prior_vax=prior_vax,
        allergies=allergies,
        vax_type=vax_type,
        vax_manu=vax_manu,
        symptom_term=symptom_term,
        symptom_text=symptom_text,
    )


def build_vaers_data_match(f: FilterSpec) -> Dict[str, Any]:
    """
    Build a MongoDB $match dict for vaers_data.
    """
    m: Dict[str, Any] = {}

    # IMPORTANT: year now maps to your computed year field, not YEAR column.
    if f.year is not None:
        m["RECVDATE_YEAR"] = f.year

    if f.sex is not None:
        m["SEX"] = f.sex
    if f.state is not None:
        m["STATE"] = f.state

    if f.age_min is not None or f.age_max is not None:
        age_cond: Dict[str, Any] = {}
        if f.age_min is not None:
            age_cond["$gte"] = f.age_min
        if f.age_max is not None:
            age_cond["$lte"] = f.age_max
        m["AGE_YRS"] = age_cond

    # NOTE: this requires ONSET_DATE to be a Mongo Date type to work correctly.
    if f.onset_start is not None or f.onset_end is not None:
        dcond: Dict[str, Any] = {}
        if f.onset_start is not None:
            dcond["$gte"] = f.onset_start
        if f.onset_end is not None:
            dcond["$lte"] = f.onset_end
        m["ONSET_DATE"] = dcond

    # Serious flags
    # "serious_only" means ANY of the serious outcomes is Y
    if f.serious_only:
        m["$or"] = [
            {"DIED": "Y"},
            {"HOSPITAL": "Y"},
            {"L_THREAT": "Y"},
            {"DISABLE": "Y"},
            {"BIRTH_DEFECT": "Y"},
        ]

    if f.died_only:
        m["DIED"] = "Y"
    if f.hospital_only:
        m["HOSPITAL"] = "Y"

    # Medical history filters (case-insensitive substring search)
    if f.other_meds:
        m["OTHER_MEDS"] = {"$regex": f.other_meds, "$options": "i"}
    if f.cur_ill:
        m["CUR_ILL"] = {"$regex": f.cur_ill, "$options": "i"}
    if f.history:
        m["HISTORY"] = {"$regex": f.history, "$options": "i"}
    if f.prior_vax:
        m["PRIOR_VAX"] = {"$regex": f.prior_vax, "$options": "i"}
    if f.allergies:
        m["ALLERGIES"] = {"$regex": f.allergies, "$options": "i"}

    return m


def build_join_filters(f: FilterSpec) -> Dict[str, Any]:
    """
    Returns a small dict of filters intended for $lookup-side constraints.
    Not applied here; feature pipelines decide how to apply them efficiently.
    """
    return {
        "vax_type": f.vax_type,
        "vax_manu": f.vax_manu,
        "symptom_term": f.symptom_term,
        "symptom_text": f.symptom_text,
    }


def build_filters(req: Request) -> Tuple[FilterSpec, Dict[str, Any], Dict[str, Any]]:
    """
    Convenience: parse request -> (FilterSpec, data_match, join_filters)
    """
    f = from_request(req)
    return f, build_vaers_data_match(f), build_join_filters(f)


def main() -> None:
    """
    Quick self-test without running Flask:
    Creates a fake "args" dict and prints matches.

    Run:
      python backend/services/filters.py
    """
    class _FakeReq:
        def __init__(self, args: Dict[str, str]):
            self.args = args

    fake = _FakeReq(
        {
            "year": "2023",
            "sex": "F",
            "state": "GA",
            "age_min": "18",
            "age_max": "45",
            "onset_start": "2023-01-01",
            "onset_end": "2023-12-31",
            "serious_only": "true",
            "vax_type": "COVID19",
            "symptom_term": "Headache",
        }
    )

    f = from_request(fake)  # type: ignore[arg-type]
    data_match = build_vaers_data_match(f)
    join = build_join_filters(f)

    print("[TEST] FilterSpec:", f)
    print("[TEST] vaers_data $match:", data_match)
    print("[TEST] join filters:", join)


if __name__ == "__main__":
    main()
