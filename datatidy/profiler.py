"""Dataset profiler (no LLM).

Computes a compact, structured description of a DataFrame and a list of
likely problems ("issues"). In Week 2 the planner LLM receives this summary
instead of the raw data, which keeps cost low and limits data exposure.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

from .operations import is_missing_token

_DATE_RE = re.compile(
    r"^\s*(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}"
    r"|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}"
    r"|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4})(\s+\d{1,2}:\d{2}(:\d{2})?)?\s*$"
)
# Only text that strip_symbols can convert safely: optional currency symbol, digits with commas,
# optional percent sign, accounting parentheses. Unit suffixes ("30 min", "5 kg") are NOT numbers
# we can clean, so they must not be flagged (found by the Week 3 benchmark on the exercise data).
_NUMERIC_CHARS = re.compile(r"^\(?[-+]?[$€£¥]?\s*[-+]?\d[\d,]*\.?\d*\s*%?\)?$")


def _texty(s: pd.Series) -> bool:
    return not (ptypes.is_numeric_dtype(s) or ptypes.is_bool_dtype(s)
                or ptypes.is_datetime64_any_dtype(s))


def _shape(value: str) -> str:
    """'12/03/2021' -> '99/99/9999', 'Mar 3' -> 'Aaa 9' (format fingerprint)."""
    v = re.sub(r"\d", "9", value.strip())
    return re.sub(r"[A-Za-z]", "a", v)


def _norm_key(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _json_safe(x: Any) -> Any:
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return None if np.isnan(x) else float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def _profile_numeric(s: pd.Series) -> dict:
    v = s.dropna().astype(float)
    if v.empty:
        return {}
    q1, q3 = v.quantile(0.25), v.quantile(0.75)
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    n_out = int(((v < low) | (v > high)).sum()) if iqr > 0 else 0
    return {
        "min": _json_safe(v.min()), "max": _json_safe(v.max()),
        "mean": round(float(v.mean()), 4), "median": _json_safe(v.median()),
        "std": round(float(v.std(ddof=0)), 4),
        "outliers_iqr": n_out,
        "skew": round(float(v.skew()), 3) if len(v) > 2 else 0.0,
    }


def _profile_text(s: pd.Series) -> dict:
    vals = [v for v in s.dropna() if isinstance(v, str)]
    info: dict[str, Any] = {}
    if not vals:
        return info

    info["whitespace_issues"] = sum(1 for v in vals if v != v.strip() or "  " in v)
    info["hidden_missing"] = sum(1 for v in vals if is_missing_token(v))
    info["hidden_missing_tokens"] = sorted({v.strip() for v in vals if is_missing_token(v)})[:5]

    # inconsistent spellings / casing of the same category
    unique_raw = set(vals)
    if len(unique_raw) <= max(50, int(0.5 * len(vals))):
        groups: dict[str, set] = {}
        for v in unique_raw:
            groups.setdefault(_norm_key(v), set()).add(v)
        variants = {k: sorted(g) for k, g in groups.items() if len(g) > 1}
        info["category_variants"] = len(variants)
        info["category_variant_examples"] = list(variants.values())[:3]
    else:
        info["category_variants"] = 0

    real = [v for v in vals if not is_missing_token(v)]
    if real:
        info["numeric_like_pct"] = round(sum(bool(_NUMERIC_CHARS.match(v.strip())) for v in real) / len(real), 3)
        info["date_like_pct"] = round(sum(bool(_DATE_RE.match(v)) for v in real) / len(real), 3)
        if info["date_like_pct"] >= 0.8:
            shapes = Counter(_shape(v) for v in real)
            info["date_formats"] = [
                {"pattern": p, "count": c} for p, c in shapes.most_common(5)
            ]
    return info


def profile_dataframe(df: pd.DataFrame, n_samples: int = 5) -> dict:
    """Return a JSON-serialisable profile with columns and a list of issues."""
    n_rows = len(df)
    columns = []
    issues: list[dict] = []

    for name in df.columns:
        s = df[name]
        n_missing = int(s.isna().sum())
        col: dict[str, Any] = {
            "name": str(name),
            "dtype": str(s.dtype),
            "n_missing": n_missing,
            "missing_pct": round(100 * n_missing / n_rows, 2) if n_rows else 0.0,
            "n_unique": int(s.nunique(dropna=True)),
            "samples": [_json_safe(v) for v in s.dropna().astype(object).unique()[:n_samples]],
        }
        if ptypes.is_numeric_dtype(s) and not ptypes.is_bool_dtype(s):
            col["kind"] = "numeric"
            col.update(_profile_numeric(s))
        elif _texty(s):
            col["kind"] = "text"
            col.update(_profile_text(s))
        else:
            col["kind"] = "other"

        def flag(issue: str, detail: str, severity: str = "medium") -> None:
            issues.append({"column": str(name), "issue": issue,
                           "detail": detail, "severity": severity})

        if n_missing:
            flag("missing_values", f"{n_missing} missing ({col['missing_pct']}%)",
                 "high" if col["missing_pct"] >= 20 else "medium")
        if col.get("hidden_missing"):
            flag("hidden_missing_tokens",
                 f"{col['hidden_missing']} cell(s) use tokens like {col['hidden_missing_tokens']}", "high")
        if col.get("whitespace_issues"):
            flag("whitespace", f"{col['whitespace_issues']} cell(s) with leading/trailing/double spaces", "low")
        if col.get("category_variants"):
            flag("inconsistent_categories",
                 f"{col['category_variants']} group(s) differ only by case/spacing, e.g. {col['category_variant_examples'][:2]}")
        if col.get("numeric_like_pct", 0) >= 0.8 and col["kind"] == "text":
            flag("numbers_stored_as_text", f"{int(col['numeric_like_pct'] * 100)}% of values look numeric", "high")
        if col.get("date_like_pct", 0) >= 0.8:
            flag("dates_stored_as_text", f"{int(col['date_like_pct'] * 100)}% of values look like dates")
            fmts = col.get("date_formats", [])
            significant = [f for f in fmts if f["count"] >= 0.05 * max(n_rows - n_missing, 1)]
            if len(significant) > 1:
                flag("mixed_date_formats", f"{len(significant)} different formats: {[f['pattern'] for f in significant]}", "high")
        if col.get("outliers_iqr"):
            flag("numeric_outliers", f"{col['outliers_iqr']} value(s) outside 1.5*IQR (range {col['min']}..{col['max']})")
        columns.append(col)

    n_dupes = int(df.duplicated().sum())
    if n_dupes:
        issues.insert(0, {"column": None, "issue": "duplicate_rows",
                          "detail": f"{n_dupes} fully duplicated row(s)", "severity": "high"})

    return {
        "n_rows": n_rows,
        "n_cols": len(df.columns),
        "n_duplicate_rows": n_dupes,
        "columns": columns,
        "issues": issues,
    }


def profile_to_text(profile: dict, max_columns: int = 60) -> str:
    """Compact plain-text rendering of a profile (the planner's input in Week 2)."""
    lines = [f"Dataset: {profile['n_rows']} rows x {profile['n_cols']} columns; "
             f"{profile['n_duplicate_rows']} duplicate rows."]
    lines.append("Columns:")
    for c in profile["columns"][:max_columns]:
        extra = ""
        if c["kind"] == "numeric" and "min" in c:
            extra = f", range {c['min']}..{c['max']}, median {c['median']}"
        lines.append(f"- {c['name']} [{c['dtype']}, {c['kind']}] missing {c['missing_pct']}%, "
                     f"{c['n_unique']} unique{extra}, e.g. {c['samples'][:3]}")
    if len(profile["columns"]) > max_columns:
        lines.append(f"... {len(profile['columns']) - max_columns} more columns omitted")
    lines.append("Detected issues:")
    if not profile["issues"]:
        lines.append("- none")
    for i in profile["issues"]:
        where = i["column"] or "(dataset)"
        lines.append(f"- [{i['severity']}] {where}: {i['issue']} - {i['detail']}")
    return "\n".join(lines)
