#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Set

import numpy as np
import pandas as pd


# ----------------------------
# Repo root + config import
# ----------------------------

def repo_root_from_this_file() -> Path:
    # backend/scripts/make_subsample.py -> repo root is parents[2]
    return Path(__file__).resolve().parents[2]


ROOT = repo_root_from_this_file()

# Ensure "backend" package can be imported when running as a script
import sys  # noqa: E402
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import SUBSAMPLE  # noqa: E402


RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "subsample"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SERIOUS_FLAG_COLS = ["DIED", "HOSPITAL", "L_THREAT", "DISABLE", "BIRTH_DEFECT"]


# ----------------------------
# Robust CSV reader (encoding fallback)
# ----------------------------

def _read_csv_retry(path: Path, *, preferred_encoding: str = "", **kwargs):
    """
    Pandas read_csv with encoding fallback, to avoid UnicodeDecodeError on VAERS files.
    - If preferred_encoding is set (e.g., from .env), try it first.
    - Then try common fallbacks: utf-8, utf-8-sig, cp1252, latin1.
    """
    tried: list[str] = []
    encodings = []
    if preferred_encoding:
        encodings.append(preferred_encoding)

    for e in ["utf-8", "utf-8-sig", "cp1252", "latin1"]:
        if e not in encodings:
            encodings.append(e)

    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except UnicodeDecodeError as e:
            tried.append(enc)
            last_err = e

    # Last resort: latin1 with replacement (if pandas supports encoding_errors)
    try:
        return pd.read_csv(path, encoding="latin1", encoding_errors="replace", **kwargs)
    except TypeError:
        # older pandas without encoding_errors
        raise UnicodeDecodeError(
            "utf-8", b"", 0, 1,
            f"Failed decoding {path.name}. Tried: {tried}. Last error: {last_err}"
        )


# ----------------------------
# File naming (matches your dir)
# ----------------------------

def year_file(year: int, kind: str) -> Path:
    # e.g. 2016VAERSDATA.csv
    p = RAW_DIR / f"{year}{kind}.csv"
    if not p.exists():
        raise FileNotFoundError(f"Missing file: {p}")
    return p


def existing_columns(csv_path: Path, csv_encoding: str) -> Set[str]:
    return set(_read_csv_retry(csv_path, preferred_encoding=csv_encoding, nrows=0).columns)


def coerce_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


# ----------------------------
# Streaming sampling (works for huge years)
# ----------------------------

def sample_ids_stream_random_keys(
    data_csv: Path,
    k: int,
    seed: int,
    serious_only: bool = False,
    chunksize: int = 200_000,
    csv_encoding: str = "",
) -> Set[int]:
    """
    Stream sample k VAERS_IDs from VAERSDATA using the "random key" method:
      assign each row a random U~(0,1), keep k rows with smallest U.
    Uniform without replacement (practically), streaming + memory-safe.
    """
    if k <= 0:
        return set()

    cols = existing_columns(data_csv, csv_encoding)
    usecols = ["VAERS_ID"]
    available_serious = [c for c in SERIOUS_FLAG_COLS if c in cols]
    if serious_only:
        if not available_serious:
            return set()
        usecols += available_serious

    rng = np.random.default_rng(seed)

    res_keys = np.empty(0, dtype=np.float64)
    res_ids = np.empty(0, dtype=np.int64)

    reader = _read_csv_retry(
        data_csv,
        preferred_encoding=csv_encoding,
        usecols=usecols,
        chunksize=chunksize,
        low_memory=False,
    )

    for chunk in reader:
        ids = coerce_int(chunk["VAERS_ID"])
        mask = ids.notna()

        if serious_only:
            ser = pd.Series(False, index=chunk.index)
            for c in available_serious:
                ser = ser | (chunk[c] == "Y")
            mask = mask & ser

        if not mask.any():
            continue

        ids_arr = ids.loc[mask].astype("int64").to_numpy()
        if ids_arr.size == 0:
            continue

        keys_arr = rng.random(ids_arr.size)

        if res_ids.size == 0:
            res_ids, res_keys = ids_arr, keys_arr
        else:
            res_ids = np.concatenate([res_ids, ids_arr])
            res_keys = np.concatenate([res_keys, keys_arr])

        if res_ids.size > k:
            idx = np.argpartition(res_keys, k - 1)[:k]
            res_ids = res_ids[idx]
            res_keys = res_keys[idx]

    return set(int(x) for x in res_ids.tolist())


def sample_ids_for_year(
    data_csv: Path,
    n_random: int,
    n_serious: int,
    seed: int,
    chunksize: int,
    csv_encoding: str,
) -> Set[int]:
    ids_random = sample_ids_stream_random_keys(
        data_csv=data_csv,
        k=n_random,
        seed=seed,
        serious_only=False,
        chunksize=chunksize,
        csv_encoding=csv_encoding,
    )
    ids_serious = sample_ids_stream_random_keys(
        data_csv=data_csv,
        k=n_serious,
        seed=seed + 999,
        serious_only=True,
        chunksize=chunksize,
        csv_encoding=csv_encoding,
    )
    return ids_random | ids_serious


# ----------------------------
# Optional top-up by VAX_TYPE for better UI demos
# ----------------------------

def topup_ids_by_vax_type(
    vax_csv: Path,
    ids_set: Set[int],
    ensure_vax_types: Iterable[str],
    min_per_vax_type: int,
    seed: int,
    chunksize: int,
    csv_encoding: str,
) -> Set[int]:
    ensure_vax_types = [t.strip() for t in ensure_vax_types if t.strip()]
    if not ensure_vax_types or min_per_vax_type <= 0:
        return ids_set

    cols = existing_columns(vax_csv, csv_encoding)
    if "VAERS_ID" not in cols or "VAX_TYPE" not in cols:
        return ids_set

    have = {t: set() for t in ensure_vax_types}

    reader1 = _read_csv_retry(
        vax_csv,
        preferred_encoding=csv_encoding,
        usecols=["VAERS_ID", "VAX_TYPE"],
        chunksize=chunksize,
        low_memory=False,
    )
    for chunk in reader1:
        ids = coerce_int(chunk["VAERS_ID"])
        chunk = chunk.loc[ids.notna(), ["VAX_TYPE"]].copy()
        chunk.insert(0, "VAERS_ID", ids.loc[ids.notna()].astype("int64").to_numpy())

        in_set = chunk[chunk["VAERS_ID"].isin(ids_set)]
        if in_set.empty:
            continue

        for t in ensure_vax_types:
            have[t].update(in_set.loc[in_set["VAX_TYPE"] == t, "VAERS_ID"].unique().tolist())

    need = {t: max(0, min_per_vax_type - len(have[t])) for t in ensure_vax_types}
    if all(v == 0 for v in need.values()):
        return ids_set

    candidates = {t: set() for t in ensure_vax_types}
    reader2 = _read_csv_retry(
        vax_csv,
        preferred_encoding=csv_encoding,
        usecols=["VAERS_ID", "VAX_TYPE"],
        chunksize=chunksize,
        low_memory=False,
    )
    for chunk in reader2:
        ids = coerce_int(chunk["VAERS_ID"])
        chunk = chunk.loc[ids.notna(), ["VAX_TYPE"]].copy()
        chunk.insert(0, "VAERS_ID", ids.loc[ids.notna()].astype("int64").to_numpy())

        not_in = chunk[~chunk["VAERS_ID"].isin(ids_set)]
        if not_in.empty:
            continue

        for t in ensure_vax_types:
            if need[t] <= 0:
                continue
            candidates[t].update(not_in.loc[not_in["VAX_TYPE"] == t, "VAERS_ID"].unique().tolist())

    rng = np.random.default_rng(seed)
    for t in ensure_vax_types:
        if need[t] <= 0:
            continue
        cand = sorted(candidates[t])
        if not cand:
            continue
        take = min(need[t], len(cand))
        pick = rng.choice(np.array(cand, dtype=np.int64), size=take, replace=False)
        ids_set.update(int(x) for x in pick.tolist())

    return ids_set


# ----------------------------
# Stream filter writers
# ----------------------------

def filter_csv_by_ids(
    in_csv: Path,
    out_csv: Path,
    ids_set: Set[int],
    chunksize: int,
    add_year: Optional[int] = None,
    write_header: bool = True,
    csv_encoding: str = "",
) -> int:
    rows_written = 0
    mode = "a" if out_csv.exists() else "w"
    first_write = not out_csv.exists()

    reader = _read_csv_retry(
        in_csv,
        preferred_encoding=csv_encoding,
        chunksize=chunksize,
        low_memory=False,
    )

    for chunk in reader:
        if "VAERS_ID" not in chunk.columns:
            continue

        ids = coerce_int(chunk["VAERS_ID"])
        kept = chunk.loc[ids.notna()].copy()
        kept["VAERS_ID"] = ids.loc[ids.notna()].astype("int64").to_numpy()

        kept = kept[kept["VAERS_ID"].isin(ids_set)]
        if kept.empty:
            continue

        if add_year is not None and "YEAR" not in kept.columns:
            kept.insert(0, "YEAR", int(add_year))

        kept.to_csv(out_csv, index=False, mode=mode, header=(write_header and first_write))
        mode = "a"
        first_write = False
        rows_written += len(kept)

    return rows_written


# ----------------------------
# Run
# ----------------------------

def main() -> None:
    years = SUBSAMPLE["years"]
    n_random = SUBSAMPLE["n_random_per_year"]
    n_serious = SUBSAMPLE["n_serious_per_year"]
    combine = SUBSAMPLE["combine"]
    prefix = SUBSAMPLE["prefix"]
    chunksize = SUBSAMPLE["chunksize"]
    ensure_types = SUBSAMPLE["ensure_vax_types"]
    min_per_type = SUBSAMPLE["min_per_vax_type"]
    csv_encoding = SUBSAMPLE.get("csv_encoding", "")

    if combine:
        out_data = OUT_DIR / f"{prefix}VAERSDATA.csv"
        out_vax = OUT_DIR / f"{prefix}VAERSVAX.csv"
        out_sym = OUT_DIR / f"{prefix}VAERSSYMPTOMS.csv"
        for p in (out_data, out_vax, out_sym):
            if p.exists():
                p.unlink()

    summary = []

    for year in years:
        data_csv = year_file(year, "VAERSDATA")
        vax_csv = year_file(year, "VAERSVAX")
        sym_csv = year_file(year, "VAERSSYMPTOMS")

        ids = sample_ids_for_year(
            data_csv=data_csv,
            n_random=n_random,
            n_serious=n_serious,
            seed=42 + year,
            chunksize=chunksize,
            csv_encoding=csv_encoding,
        )

        if ensure_types and min_per_type > 0:
            ids = topup_ids_by_vax_type(
                vax_csv=vax_csv,
                ids_set=ids,
                ensure_vax_types=ensure_types,
                min_per_vax_type=min_per_type,
                seed=4242 + year,
                chunksize=chunksize,
                csv_encoding=csv_encoding,
            )

        if combine:
            rows_d = filter_csv_by_ids(data_csv, out_data, ids, chunksize, add_year=year, write_header=True, csv_encoding=csv_encoding)
            rows_v = filter_csv_by_ids(vax_csv, out_vax, ids, chunksize, add_year=year, write_header=True, csv_encoding=csv_encoding)
            rows_s = filter_csv_by_ids(sym_csv, out_sym, ids, chunksize, add_year=year, write_header=True, csv_encoding=csv_encoding)
        else:
            y_data = OUT_DIR / f"{prefix}{year}VAERSDATA.csv"
            y_vax = OUT_DIR / f"{prefix}{year}VAERSVAX.csv"
            y_sym = OUT_DIR / f"{prefix}{year}VAERSSYMPTOMS.csv"
            for p in (y_data, y_vax, y_sym):
                if p.exists():
                    p.unlink()

            rows_d = filter_csv_by_ids(data_csv, y_data, ids, chunksize, add_year=None, write_header=True, csv_encoding=csv_encoding)
            rows_v = filter_csv_by_ids(vax_csv, y_vax, ids, chunksize, add_year=None, write_header=True, csv_encoding=csv_encoding)
            rows_s = filter_csv_by_ids(sym_csv, y_sym, ids, chunksize, add_year=None, write_header=True, csv_encoding=csv_encoding)

        summary.append((year, len(ids), rows_d, rows_v, rows_s))
        print(f"[OK] {year}: IDs={len(ids):,} | DATA={rows_d:,} VAX={rows_v:,} SYM={rows_s:,}")

    print("\n=== Summary ===")
    for year, n_ids, rd, rv, rs in summary:
        print(f"{year}: IDs={n_ids:,} | DATA={rd:,} | VAX={rv:,} | SYM={rs:,}")

    if combine:
        print("\nCombined outputs:")
        print(f"  - {(OUT_DIR / f'{prefix}VAERSDATA.csv').relative_to(ROOT)}")
        print(f"  - {(OUT_DIR / f'{prefix}VAERSVAX.csv').relative_to(ROOT)}")
        print(f"  - {(OUT_DIR / f'{prefix}VAERSSYMPTOMS.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
