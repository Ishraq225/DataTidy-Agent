"""The safe operation library.

The LLM planner may ONLY choose from these operations. Nothing here executes
arbitrary code, and every operation reports exactly what it changed.

Unknown parameters are rejected (no **kwargs), so a hallucinated parameter
fails loudly instead of being silently ignored.

Row-removing operations keep the original index labels, so every surviving row can be
traced back to the input (the Week 3 benchmark relies on this).

Each operation has the signature:

    fn(df, column=None, **params) -> OperationOutcome

and must never modify the input DataFrame in place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd
from pandas.api import types as ptypes


class OperationError(ValueError):
    """Raised when an operation cannot be applied (bad column, bad params)."""


@dataclass
class OperationOutcome:
    df: pd.DataFrame
    cells_changed: int = 0
    rows_removed: int = 0
    message: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

MISSING_TOKENS = {
    "", "na", "n/a", "nan", "null", "none", "nil", "missing", "unknown",
    "-", "--", "?", "#n/a",
}


def is_missing_token(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in MISSING_TOKENS


def _require_column(df: pd.DataFrame, column: str | None) -> str:
    if column is None:
        raise OperationError("This operation needs a 'column'.")
    if column not in df.columns:
        raise OperationError(f"Column '{column}' does not exist.")
    return column


def _same(x: Any, y: Any) -> bool:
    x_na, y_na = bool(pd.isna(x)), bool(pd.isna(y))
    if x_na or y_na:
        return x_na and y_na
    try:
        return bool(x == y)
    except Exception:
        return False


def count_changed_cells(before: pd.Series, after: pd.Series) -> int:
    """Number of positions whose value differs (NaN == NaN, 3 == 3.0)."""
    return sum(0 if _same(x, y) else 1 for x, y in zip(before, after))


def _texty(series: pd.Series) -> bool:
    return not (
        ptypes.is_numeric_dtype(series)
        or ptypes.is_bool_dtype(series)
        or ptypes.is_datetime64_any_dtype(series)
    )


# --------------------------------------------------------------------------
# operations
# --------------------------------------------------------------------------

def drop_duplicates(df, column=None, subset=None, keep="first"):
    """Remove duplicate rows (all columns, or only `subset`)."""
    if keep not in ("first", "last"):
        raise OperationError("keep must be 'first' or 'last'.")
    if subset is not None:
        missing = [c for c in subset if c not in df.columns]
        if missing:
            raise OperationError(f"Unknown columns in subset: {missing}")
    out = df.drop_duplicates(subset=subset, keep=keep)      # index kept: rows stay traceable
    removed = len(df) - len(out)
    where = f" using columns {subset}" if subset else ""
    return OperationOutcome(out, rows_removed=removed,
                            message=f"Removed {removed} duplicate row(s){where}.")


def fill_missing(df, column=None, strategy="median", value=None):
    """Fill missing values in one column.

    strategy: mean | median | mode | constant (needs `value`)
    """
    column = _require_column(df, column)
    s = df[column]
    n_missing = int(s.isna().sum())
    if n_missing == 0:
        return OperationOutcome(df.copy(), message=f"'{column}' has no missing values.")

    if strategy in ("mean", "median"):
        if not ptypes.is_numeric_dtype(s):
            raise OperationError(f"'{strategy}' needs a numeric column; '{column}' is {s.dtype}.")
        fill = s.mean() if strategy == "mean" else s.median()
        if pd.isna(fill):
            raise OperationError(f"Cannot compute {strategy} of '{column}' (all values missing).")
    elif strategy == "mode":
        modes = s.dropna().mode()
        if modes.empty:
            raise OperationError(f"Cannot compute mode of '{column}' (all values missing).")
        fill = modes.iloc[0]
    elif strategy == "constant":
        if value is None:
            raise OperationError("strategy 'constant' needs a 'value'.")
        fill = value
    else:
        raise OperationError("strategy must be one of: mean, median, mode, constant.")

    fill = fill.item() if hasattr(fill, "item") else fill      # numpy scalar -> plain Python
    out = df.copy()
    out[column] = s.fillna(fill)
    return OperationOutcome(
        out, cells_changed=n_missing,
        message=f"Filled {n_missing} missing value(s) in '{column}' with {strategy} ({fill!r}).",
        extra={"fill_value": fill},
    )


_BOOL_MAP = {"true": True, "yes": True, "y": True, "1": True, "t": True,
             "false": False, "no": False, "n": False, "0": False, "f": False}


def cast_type(df, column=None, target="float"):
    """Convert a column to int | float | str | bool | category.

    Values that cannot be converted become missing and are counted in the log.
    Integers use pandas' nullable Int64 so missing values are preserved.
    """
    column = _require_column(df, column)
    s = df[column]
    before_dtype = str(s.dtype)
    already_missing = int(s.isna().sum())

    if target in ("int", "float"):
        cleaned = s.map(lambda v: v.strip() if isinstance(v, str) else v)
        num = pd.to_numeric(cleaned, errors="coerce")
        if target == "int":
            non_integer = num.notna() & (num != num.round())
            num = num.where(~non_integer)           # refuse to truncate 3.7 -> 3
            result = num.round().astype("Int64")
        else:
            result = num.astype("float64")
    elif target == "str":
        result = s.map(lambda v: v if pd.isna(v) else str(v))
    elif target == "bool":
        def to_bool(v):
            if pd.isna(v):
                return pd.NA
            if isinstance(v, (bool, np.bool_)):
                return bool(v)
            return _BOOL_MAP.get(str(v).strip().lower(), pd.NA)
        result = s.map(to_bool).astype("boolean")
    elif target == "category":
        result = s.astype("category")
    else:
        raise OperationError("target must be one of: int, float, str, bool, category.")

    newly_missing = int(result.isna().sum()) - already_missing
    out = df.copy()
    out[column] = result
    msg = f"Converted '{column}' from {before_dtype} to {result.dtype}."
    if newly_missing > 0:
        msg += f" WARNING: {newly_missing} value(s) could not be converted and became missing."
    return OperationOutcome(out, cells_changed=max(newly_missing, 0), message=msg,
                            extra={"newly_missing": newly_missing,
                                   "from": before_dtype, "to": str(result.dtype)})


def normalise_text(df, column=None, lowercase=True, strip=True,
                   collapse_spaces=True):
    """Trim, collapse repeated spaces and (optionally) lowercase a text column."""
    column = _require_column(df, column)
    s = df[column]
    if not _texty(s):
        raise OperationError(f"'{column}' is {s.dtype}, not a text column.")

    def fix(v):
        if not isinstance(v, str):
            return v
        if collapse_spaces:
            v = re.sub(r"\s+", " ", v)
        if strip:
            v = v.strip()
        if lowercase:
            v = v.lower()
        return v

    new = s.map(fix)
    changed = count_changed_cells(s, new)
    out = df.copy()
    out[column] = new
    return OperationOutcome(out, cells_changed=changed,
                            message=f"Normalised text in '{column}' ({changed} cell(s) changed).")


_SUFFIX = {"k": 1e3, "m": 1e6, "b": 1e9}


def strip_symbols(df, column=None, symbols="$€£¥%,", expand_suffixes=False):
    """Turn text like '$1,200', '12%' or '(500)' into numbers.

    * characters in `symbols` and whitespace are removed
    * '(500)' is read as -500 (accounting style)
    * with expand_suffixes=True, '1.2k' -> 1200, '3m' -> 3,000,000
    * values that still cannot be parsed become missing and are counted
    """
    column = _require_column(df, column)
    s = df[column]
    if ptypes.is_numeric_dtype(s):
        return OperationOutcome(df.copy(), message=f"'{column}' is already numeric.")
    drop = set(symbols) | set(" \t\u00a0")

    def parse(v):
        if pd.isna(v):
            return np.nan
        if isinstance(v, (int, float, np.number)):
            return float(v)
        t = "".join(ch for ch in str(v) if ch not in drop)
        negative = t.startswith("(") and t.endswith(")")
        t = t.strip("()")
        mult = 1.0
        if expand_suffixes and t and t[-1].lower() in _SUFFIX:
            mult = _SUFFIX[t[-1].lower()]
            t = t[:-1]
        try:
            x = float(t) * mult
        except ValueError:
            return np.nan
        return -x if negative else x

    new = s.map(parse).astype("float64")
    newly_missing = int(new.isna().sum()) - int(s.isna().sum())
    out = df.copy()
    out[column] = new
    changed = count_changed_cells(s, new)
    msg = f"Converted '{column}' to numbers ({changed} cell(s) changed)."
    if newly_missing > 0:
        msg += f" WARNING: {newly_missing} value(s) could not be parsed and became missing."
    return OperationOutcome(out, cells_changed=changed, message=msg,
                            extra={"newly_missing": newly_missing})


def standardize_missing(df, column=None, tokens=None):
    """Replace hidden-missing tokens ('N/A', '?', 'null', ...) with real missing values.

    Uses a default token list unless `tokens` is given. Pass column=None to
    apply to every text column.
    """
    token_set = {t.strip().lower() for t in tokens} if tokens else MISSING_TOKENS
    cols = [_require_column(df, column)] if column else [c for c in df.columns if _texty(df[c])]
    out = df.copy()
    total = 0
    for c in cols:
        mask = out[c].map(lambda v: isinstance(v, str) and v.strip().lower() in token_set)
        n = int(mask.sum())
        if n:
            out[c] = out[c].mask(mask, np.nan)
            total += n
    return OperationOutcome(out, cells_changed=total,
                            message=f"Replaced {total} hidden-missing token(s) with real missing values.")


def parse_dates(df, column=None, format=None, dayfirst=False):
    """Parse date-like text (mixed formats allowed) into real datetimes.

    Ambiguous dates such as 03/04/2024 follow `dayfirst` (False = month first).
    Values that cannot be parsed become missing and are counted.
    """
    column = _require_column(df, column)
    s = df[column]
    if ptypes.is_datetime64_any_dtype(s):
        return OperationOutcome(df.copy(), message=f"'{column}' is already a datetime column.")
    cleaned = s.map(lambda v: v.strip() if isinstance(v, str) else v)
    parsed = pd.to_datetime(cleaned, format=format or "mixed", dayfirst=dayfirst, errors="coerce")
    failed = int((parsed.isna() & s.notna() & ~s.map(is_missing_token)).sum())
    out = df.copy()
    out[column] = parsed
    msg = (f"Parsed '{column}' as dates (assuming {'day' if dayfirst else 'month'} first "
           f"for ambiguous values like 03/04/2024).")
    if failed:
        msg += f" WARNING: {failed} value(s) could not be parsed and became missing."
    return OperationOutcome(out, cells_changed=int(parsed.notna().sum()), message=msg,
                            extra={"newly_missing": failed})


def map_values(df, column=None, mapping=None, case_insensitive=False):
    """Replace category values using an explicit mapping, e.g. {"khi": "Karachi"}.

    Keys are matched after trimming spaces. Values not in the mapping are kept.
    """
    column = _require_column(df, column)
    if not mapping or not isinstance(mapping, dict):
        raise OperationError("map_values needs a non-empty 'mapping' dictionary.")
    if len(mapping) > 500:
        raise OperationError("mapping is too large (max 500 entries).")
    lookup = {(str(k).strip().lower() if case_insensitive else str(k).strip()): v
              for k, v in mapping.items()}

    def fix(v):
        if not isinstance(v, str):
            return v
        key = v.strip().lower() if case_insensitive else v.strip()
        return lookup.get(key, v)

    new = df[column].map(fix)
    changed = count_changed_cells(df[column], new)
    out = df.copy()
    out[column] = new
    return OperationOutcome(out, cells_changed=changed,
                            message=f"Mapped {changed} value(s) in '{column}' using {len(lookup)} rule(s).")


def clip_outliers(df, column=None, method="iqr", factor=1.5, threshold=3.0, action="clip"):
    """Handle extreme numeric values. method: iqr | zscore. action: clip | set_missing.

    Use only when values are implausible; a flagged outlier is not necessarily an error.
    """
    column = _require_column(df, column)
    s = df[column]
    if not ptypes.is_numeric_dtype(s) or ptypes.is_bool_dtype(s):
        raise OperationError(f"'{column}' is {s.dtype}, not numeric.")
    if method not in ("iqr", "zscore") or action not in ("clip", "set_missing"):
        raise OperationError("method must be iqr|zscore and action must be clip|set_missing.")
    v = s.dropna().astype(float)
    if v.empty:
        raise OperationError(f"'{column}' has no values.")
    if method == "iqr":
        q1, q3 = v.quantile(0.25), v.quantile(0.75)
        iqr = q3 - q1
        low, high = q1 - factor * iqr, q3 + factor * iqr
    else:
        mu, sd = v.mean(), v.std(ddof=0)
        low, high = mu - threshold * sd, mu + threshold * sd
    if method == "iqr" and iqr == 0 or (method == "zscore" and sd == 0):
        return OperationOutcome(df.copy(), message=f"'{column}' has no spread; nothing to clip.")
    outside = (s < low) | (s > high)
    n = int(outside.sum())
    out = df.copy()
    out[column] = s.clip(lower=low, upper=high) if action == "clip" else s.mask(outside, np.nan)
    verb = "Clipped" if action == "clip" else "Set to missing"
    return OperationOutcome(out, cells_changed=n,
                            message=f"{verb} {n} value(s) in '{column}' outside [{low:.4g}, {high:.4g}] ({method}).",
                            extra={"low": float(low), "high": float(high)})


def drop_missing_rows(df, column=None, threshold=0.5):
    """Drop rows missing a value in `column`, or (no column) rows where at least
    `threshold` of all cells are missing."""
    if column is not None:
        _require_column(df, column)
        mask = df[column].isna()
        what = f"missing '{column}'"
    else:
        if not 0 < threshold <= 1:
            raise OperationError("threshold must be in (0, 1].")
        mask = df.isna().mean(axis=1) >= threshold
        what = f"at least {threshold:.0%} of cells missing"
    out = df[~mask]                                          # index kept: rows stay traceable
    return OperationOutcome(out, rows_removed=int(mask.sum()),
                            message=f"Dropped {int(mask.sum())} row(s) with {what}.")


def rename_column(df, column=None, new_name=None):
    """Rename one column."""
    column = _require_column(df, column)
    if not isinstance(new_name, str) or not new_name.strip():
        raise OperationError("rename_column needs a non-empty 'new_name'.")
    if new_name != column and new_name in df.columns:
        raise OperationError(f"Column '{new_name}' already exists.")
    return OperationOutcome(df.rename(columns={column: new_name}),
                            message=f"Renamed '{column}' to '{new_name}'.")


def drop_column(df, column=None):
    """Remove a column (e.g. one that is mostly missing and unusable)."""
    column = _require_column(df, column)
    return OperationOutcome(df.drop(columns=[column]), message=f"Dropped column '{column}'.")


OPERATIONS: dict[str, Callable[..., OperationOutcome]] = {
    "drop_duplicates": drop_duplicates,
    "fill_missing": fill_missing,
    "cast_type": cast_type,
    "normalise_text": normalise_text,
    "strip_symbols": strip_symbols,
    "standardize_missing": standardize_missing,
    "parse_dates": parse_dates,
    "map_values": map_values,
    "clip_outliers": clip_outliers,
    "drop_missing_rows": drop_missing_rows,
    "rename_column": rename_column,
    "drop_column": drop_column,
}
