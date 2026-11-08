"""Evaluation metrics.

Terminology (all computed against the ground-truth table `case.clean`):

  cell_accuracy       correct cells / ALL cells of the clean table (lost rows or columns count as wrong)
  baseline_accuracy   the same number for the untouched messy file ("do nothing")
  damage_rate         cells that were correct in the messy file and are WRONG after cleaning
                      (only counted where the truth is a real value)
  fabrication_rate    cells whose truth is *missing* but which now hold a value (imputation)
  row_loss_rate       original rows that no longer exist after cleaning
  col_loss_rate       original columns that no longer exist after cleaning
  dup_removal_rate    share of injected duplicate rows that were removed

Per corruption type (fix rates):
  numeric_text, date_format   exact value restored
  case_space                  value now identical to its un-corrupted siblings in the output
  missing_token               hidden token is gone (turned into a real missing value or filled)
  outlier                     at least half of the error removed (or value set to missing)

Text cells are compared after trimming and case-folding, so a cleaner that lowercases
categories is not punished for the convention; case_space is judged separately.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime

import numpy as np
import pandas as pd

from datatidy.operations import is_missing_token
from .corrupt import RECOVERABLE, Case


def canon(v):
    """Canonical comparable form of a cell value."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, (bool, np.bool_)):
        return float(v)
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    if isinstance(v, (pd.Timestamp, datetime, np.datetime64)):
        ts = pd.Timestamp(v)
        if (ts.hour, ts.minute, ts.second, ts.microsecond) == (0, 0, 0, 0):
            return ts.strftime("%Y-%m-%d")
        return ts.isoformat()
    return " ".join(str(v).split()).casefold()


def cells_equal(a, b) -> bool:
    ca, cb = canon(a), canon(b)
    if ca is None or cb is None:
        return ca is None and cb is None
    if isinstance(ca, float) and isinstance(cb, float):
        return math.isclose(ca, cb, rel_tol=1e-6, abs_tol=1e-9)
    return ca == cb


def _first_positions(case: Case, df: pd.DataFrame) -> tuple[dict[int, object], Counter]:
    """id -> the row label that represents it (primary copy if it survives, else the earliest
    surviving copy); plus the number of surviving copies per id."""
    first: dict[int, object] = {}
    copies: Counter = Counter()
    for label in df.index:
        try:
            rid = case.row_map[int(label)]
        except (IndexError, ValueError, TypeError):
            continue
        copies[rid] += 1
        if case.primary_pos and label == case.primary_pos[rid]:
            first[rid] = label                       # the primary copy always wins when it survives
        else:
            first.setdefault(rid, label)
    return first, copies


def grid(case: Case, df: pd.DataFrame):
    """(correct[n, m], present[n, m], first_label, copies) against the clean table."""
    n, m = case.clean.shape
    correct = np.zeros((n, m), dtype=bool)
    present = np.zeros((n, m), dtype=bool)
    first, copies = _first_positions(case, df)
    ids = sorted(first)
    labels = [first[i] for i in ids]
    for j, col in enumerate(case.clean.columns):
        if col not in df.columns or not ids:
            continue
        out = df[col].loc[labels].tolist()
        truth = case.clean[col].iloc[ids].tolist()
        for rid, t, o in zip(ids, truth, out):
            present[rid, j] = True
            correct[rid, j] = cells_equal(t, o)
    return correct, present, first, copies


def _cell(case: Case, df: pd.DataFrame, first: dict, rid: int, col: str):
    if rid not in first or col not in df.columns:
        return None, False
    return df.at[first[rid], col], True


def evaluate(case: Case, cleaned: pd.DataFrame, messy_loaded: pd.DataFrame,
             before_cache: tuple | None = None) -> dict:
    """Compute every metric for one cleaned output."""
    n, m = case.clean.shape
    total = n * m
    truth_missing = case.clean.isna().to_numpy()

    after, present, first, copies = grid(case, cleaned)
    before, _, _, _ = before_cache or grid(case, messy_loaded)

    correct_before = before & ~truth_missing
    res: dict = {
        "cell_accuracy": after.sum() / total,
        "baseline_accuracy": before.sum() / total,
        "damage_rate": (correct_before & present & ~after).sum() / max(correct_before.sum(), 1),
        "fabrication_rate": (truth_missing & present & ~after).sum() / max(truth_missing.sum(), 1)
        if truth_missing.any() else 0.0,
        "row_loss_rate": sum(1 for i in range(n) if i not in first) / n,
        "col_loss_rate": sum(1 for c in case.clean.columns if c not in cleaned.columns) / m,
        "rows_out": len(cleaned),
    }
    res["accuracy_gain"] = res["cell_accuracy"] - res["baseline_accuracy"]

    # duplicates
    n_dups = case.n_dup_rows
    remaining = sum(max(c - 1, 0) for c in copies.values())
    res["dup_removal_rate"] = max(0.0, 1 - remaining / n_dups) if n_dups else np.nan

    # per-type fix rates
    fixed: dict[str, list[int]] = {}

    def tally(kind: str, ok: bool):
        t = fixed.setdefault(kind, [0, 0])
        t[0] += int(ok)
        t[1] += 1

    for kind, cols in case.injected.items():
        if kind == "dup_rows":
            continue
        for col, ids in cols.items():
            if kind in ("numeric_text", "date_format"):
                for rid in ids:
                    o, ok = _cell(case, cleaned, first, rid, col)
                    tally(kind, ok and cells_equal(case.clean[col].iloc[rid], o))
            elif kind == "missing_token":
                for rid in ids:
                    o, ok = _cell(case, cleaned, first, rid, col)
                    tally(kind, ok and not (isinstance(o, str) and is_missing_token(o)))
            elif kind == "outlier":
                for rid in ids:
                    o, ok = _cell(case, cleaned, first, rid, col)
                    if not ok:
                        tally(kind, False)
                        continue
                    t = case.clean[col].iloc[rid]
                    messy_val = float(t) * 10
                    if pd.isna(o):
                        tally(kind, True)
                    else:
                        try:
                            # must remove at least half of the error (ignores float noise)
                            tally(kind, abs(float(o) - float(t)) <= 0.5 * abs(messy_val - float(t)))
                        except (TypeError, ValueError):
                            tally(kind, False)
            elif kind == "case_space":
                injected_ids = set(ids)
                refs: dict = {}
                for rid in range(n):
                    if rid in injected_ids:
                        continue
                    o, ok = _cell(case, cleaned, first, rid, col)
                    if ok and not pd.isna(o):
                        refs.setdefault(canon(case.clean[col].iloc[rid]), Counter())[str(o)] += 1
                for rid in ids:
                    o, ok = _cell(case, cleaned, first, rid, col)
                    ref = refs.get(canon(case.clean[col].iloc[rid]))
                    if not ref:
                        continue                       # no un-corrupted sibling to compare with
                    tally(kind, ok and not pd.isna(o) and str(o) == ref.most_common(1)[0][0])

    for kind in ("numeric_text", "date_format", "case_space", "missing_token", "outlier"):
        ok, tot = fixed.get(kind, [0, 0])
        res[f"fix_{kind}"] = ok / tot if tot else np.nan
        res[f"n_{kind}"] = tot
    rec_ok = sum(fixed.get(k, [0, 0])[0] for k in RECOVERABLE)
    rec_tot = sum(fixed.get(k, [0, 0])[1] for k in RECOVERABLE)
    res["recoverable_fix_rate"] = rec_ok / rec_tot if rec_tot else np.nan
    return {k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer,)) else v)
            for k, v in res.items()}
