from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


# Project root: VAERS_Interactive/
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def _as_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _as_int(v: str | None, default: int) -> int:
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default


def _as_int_list(v: str | None, default: list[int]) -> list[int]:
    if not v:
        return default
    out: list[int] = []
    for part in v.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out or default


def _as_str_list(v: str | None, default: list[str]) -> list[str]:
    if not v:
        return default
    return [x.strip() for x in v.split(",") if x.strip()]


SUBSAMPLE = {
    "years": _as_int_list(os.getenv("VAERS_DEV_YEARS"), [2016, 2018, 2023]),
    "n_random_per_year": _as_int(os.getenv("VAERS_DEV_N_RANDOM"), 10000),
    "n_serious_per_year": _as_int(os.getenv("VAERS_DEV_N_SERIOUS"), 2000),
    "combine": _as_bool(os.getenv("VAERS_DEV_COMBINE"), True),
    "prefix": os.getenv("VAERS_DEV_PREFIX", "dev"),
    "chunksize": _as_int(os.getenv("VAERS_DEV_CHUNKSIZE"), 200_000),
    "ensure_vax_types": _as_str_list(os.getenv("VAERS_DEV_ENSURE_VAX_TYPES"), []),
    "min_per_vax_type": _as_int(os.getenv("VAERS_DEV_MIN_PER_VAX_TYPE"), 0),
    "csv_encoding": os.getenv("VAERS_CSV_ENCODING", "").strip(),
}
