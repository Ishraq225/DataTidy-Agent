"""Corruption generator with ground truth.

`make_case(dataset, seed)` returns a Case holding:
  clean     the ground-truth table (what a perfect cleaner would output)
  messy     the corrupted table exactly as it is written to CSV
  row_map   for each messy row position, the id (row of `clean`) it came from
  primary_pos  for each id, the messy row position of its primary (non-duplicate) copy
  injected  {corruption_type: {column: [row ids]}}  what was injected where

Corruption types
  RECOVERABLE (an exact inverse exists, so "fixed" can be checked exactly)
    numeric_text   numbers turned into text with a symbol: "$1,234.5", "12.5%"
    date_format    ISO dates rewritten in mixed formats
    case_space     category values with random case / padding
    dup_rows       the same record entered again, corrupted independently of the original
  LOSSY (information is destroyed, so only "handled" can be checked)
    missing_token  real values replaced by "N/A", "?", "-" ...
    outlier        values multiplied by 10
"""

from __future__ import annotations

import io
import json
import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

from datatidy.io import load_csv
from .datasets import DATASETS, load_base

RECOVERABLE = ("numeric_text", "date_format", "case_space")
LOSSY = ("missing_token", "outlier")
ALL_TYPES = RECOVERABLE + ("dup_rows",) + LOSSY

TOKENS = ["N/A", "?", "-", "null", "unknown", "missing"]
SYMBOLS = ["$", "€", "£", "%"]
DATE_FORMATS = ["%Y-%m-%d", "%d %b %Y", "%b %d, %Y", "%m/%d/%Y"]   # all month-first / unambiguous
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Case:
    dataset: str
    seed: int
    clean: pd.DataFrame
    messy: pd.DataFrame
    row_map: list[int]
    primary_pos: list[int] = field(default_factory=list)   # id -> messy row position of its primary copy
    injected: dict[str, dict[str, list[int]]] = field(default_factory=dict)
    details: dict = field(default_factory=dict)

    @property
    def n_dup_rows(self) -> int:
        return len(self.row_map) - len(self.clean)

    def messy_csv(self) -> str:
        return self.messy.to_csv(index=False)

    def save(self, folder: str | Path) -> Path:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "messy.csv").write_text(self.messy_csv(), encoding="utf-8")
        self.clean.to_csv(folder / "clean.csv", index=False)
        manifest = {"dataset": self.dataset, "seed": self.seed, "row_map": self.row_map,
                    "primary_pos": self.primary_pos, "injected": self.injected, "details": self.details}
        (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return folder


def roundtrip(df: pd.DataFrame) -> pd.DataFrame:
    """Write to CSV text and load back, so types match what a real cleaner receives."""
    return load_csv(io.StringIO(df.to_csv(index=False)))


def _is_numeric(s: pd.Series) -> bool:
    return ptypes.is_numeric_dtype(s) and not ptypes.is_bool_dtype(s)


def _is_text(s: pd.Series) -> bool:
    return not (ptypes.is_numeric_dtype(s) or ptypes.is_bool_dtype(s) or ptypes.is_datetime64_any_dtype(s))


def _fmt_number(v, symbol: str) -> str:
    body = f"{abs(v):,}"                                   # exact round-trip precision
    sign = "-" if v < 0 else ""
    return f"{sign}{body}%" if symbol == "%" else f"{sign}{symbol}{body}"


def make_case(dataset: str, seed: int = 0) -> Case:
    clean = roundtrip(load_base(dataset))
    n = len(clean)
    rng = np.random.default_rng(seed * 100_003 + zlib.crc32(dataset.encode()))

    # Duplicates are the SAME record entered again, so each copy is corrupted INDEPENDENTLY
    # (different case/spacing/tokens). This is what makes dedupe-before-normalising fail.
    k_dup = max(2, int(round(0.05 * n)))
    src = sorted(int(i) for i in rng.choice(n, size=min(k_dup, n), replace=False))
    ids_all = list(range(n)) + src
    base = pd.concat([clean, clean.iloc[src]], ignore_index=True)       # truth for every stacked row
    N = len(base)
    messy = base.copy()
    injected: dict[str, dict[str, list[int]]] = {t: {} for t in ALL_TYPES}
    details: dict = {t: {} for t in ALL_TYPES}
    used: set[str] = set()

    def pick(cands: list[str], k: int) -> list[str]:
        cands = [c for c in cands if c not in used]
        chosen = list(rng.choice(cands, size=min(k, len(cands)), replace=False)) if cands else []
        used.update(chosen)
        return [str(c) for c in chosen]

    numeric_cols = [c for c in clean.columns if _is_numeric(clean[c]) and clean[c].nunique() >= 5]
    date_cols = [c for c in clean.columns if _is_text(clean[c]) and clean[c].notna().any()
                 and clean[c].dropna().map(lambda v: bool(_ISO.match(str(v)))).all()]
    cat_cols = [c for c in clean.columns if _is_text(clean[c]) and c not in date_cols
                and 2 <= clean[c].nunique() <= 30]
    any_cols = [c for c in clean.columns if not ptypes.is_bool_dtype(clean[c])]

    # 1. numbers stored as text with a symbol (whole column)
    for col in pick(numeric_cols, 1):
        symbol = str(rng.choice(SYMBOLS))
        vals = base[col].astype(object)
        messy[col] = pd.Series([_fmt_number(v, symbol) if pd.notna(v) else None for v in vals], dtype=object)
        injected["numeric_text"][col] = [i for i in range(N) if pd.notna(vals.iloc[i])]
        details["numeric_text"][col] = symbol

    # 2. dates rewritten in mixed formats
    for col in pick(date_cols, 1):
        fmts = rng.choice(DATE_FORMATS, size=N)
        out, ids = [], []
        for i, (v, f) in enumerate(zip(base[col], fmts)):
            if pd.isna(v):
                out.append(None)
                continue
            new = pd.Timestamp(v).strftime(str(f))
            out.append(new)
            if new != v:
                ids.append(i)
        messy[col] = pd.Series(out, dtype=object)
        injected["date_format"][col] = ids
        details["date_format"][col] = DATE_FORMATS

    # 3. category case / padding noise
    for col in pick(cat_cols, 2):
        out = list(messy[col].astype(object))
        ids = []
        for i in range(N):
            v = out[i]
            if pd.isna(v) or rng.random() > 0.25:
                continue
            variants = [str(v).upper(), str(v).lower(), f"  {v}", f"{v}  ", f" {str(v).upper()} "]
            new = next((x for x in rng.permutation(variants) if x != v), None)
            if new is not None:
                out[i] = str(new)
                ids.append(i)
        messy[col] = pd.Series(out, dtype=object)
        injected["case_space"][col] = ids

    # 4. hidden missing tokens
    for col in pick(any_cols, 2):
        candidates = [i for i in range(N) if pd.notna(base[col].iloc[i])]
        k = max(3, int(round(0.08 * len(candidates))))
        if len(candidates) <= k:
            used.discard(col)
            continue
        ids = sorted(int(i) for i in rng.choice(candidates, size=k, replace=False))
        token = str(rng.choice(TOKENS))
        col_vals = messy[col].astype(object)
        for i in ids:
            col_vals.iloc[i] = token
        messy[col] = col_vals
        injected["missing_token"][col] = ids
        details["missing_token"][col] = token

    # 5. outliers (x10)
    for col in pick([c for c in numeric_cols if ptypes.is_float_dtype(clean[c])] or numeric_cols, 1):
        candidates = [i for i in range(N) if pd.notna(base[col].iloc[i]) and base[col].iloc[i] != 0]
        k = max(2, int(round(0.01 * N)))
        if len(candidates) <= k:
            used.discard(col)
            continue
        ids = sorted(int(i) for i in rng.choice(candidates, size=k, replace=False))
        col_vals = messy[col].astype(float)
        for i in ids:
            col_vals.iloc[i] = col_vals.iloc[i] * 10
        messy[col] = col_vals
        injected["outlier"][col] = ids

    # shuffle so duplicates sit at random positions; remember where each original row went
    order = rng.permutation(N)
    messy_final = messy.iloc[order].reset_index(drop=True)
    row_map = [int(ids_all[i]) for i in order]
    new_pos = {int(old): new for new, old in enumerate(order)}
    primary_pos = [new_pos[i] for i in range(n)]                 # where each original row's primary copy is

    # cell-level injections are reported for the PRIMARY copy of each row (stacked position < n)
    injected = {t: {c: sorted(i for i in ids if i < n) for c, ids in cols.items()} for t, cols in injected.items()}
    injected = {t: {c: ids for c, ids in cols.items() if ids} for t, cols in injected.items()}
    injected["dup_rows"] = {"__rows__": src}
    injected = {t: v for t, v in injected.items() if v}
    details = {t: v for t, v in details.items() if v}
    return Case(dataset, seed, clean, messy_final, row_map, primary_pos, injected, details)


def all_cases(datasets: list[str] | None = None, seeds: list[int] | None = None):
    for name in datasets or sorted(DATASETS):
        for seed in seeds if seeds is not None else [0]:
            yield make_case(name, seed)
