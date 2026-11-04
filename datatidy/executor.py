"""Deterministic plan executor (no LLM).

A plan is a list of steps:
    {"op": "fill_missing", "column": "age",
     "params": {"strategy": "median"}, "reason": "..."}

The executor runs the steps in order on a COPY of the data and records a
change log entry per step. A failing step is logged and skipped by default,
so one bad step never destroys the whole run.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .operations import OPERATIONS, OperationError


def run_plan(df: pd.DataFrame, plan: list[dict[str, Any]],
             stop_on_error: bool = False) -> tuple[pd.DataFrame, list[dict]]:
    """Apply `plan` to `df`. Returns (cleaned_df, log). Input is never modified."""
    current = df.copy()
    log: list[dict] = []

    for i, step in enumerate(plan, start=1):
        op = step.get("op")
        column = step.get("column")
        params = step.get("params") or {}
        entry = {
            "step": i, "op": op, "column": column, "params": params,
            "reason": step.get("reason", ""),
            "status": "ok", "rows_before": len(current), "rows_after": len(current),
            "cells_changed": 0, "message": "",
        }
        try:
            if op not in OPERATIONS:
                raise OperationError(f"Unknown operation '{op}'. Allowed: {sorted(OPERATIONS)}")
            outcome = OPERATIONS[op](current, column=column, **params)
            current = outcome.df
            entry.update(rows_after=len(current), cells_changed=outcome.cells_changed,
                         message=outcome.message)
        except OperationError as exc:
            entry.update(status="failed", message=str(exc))
            log.append(entry)
            if stop_on_error:
                break
            continue
        except TypeError as exc:                     # unknown / misspelled parameter
            entry.update(status="failed", message=f"Invalid parameters for '{op}': {exc}")
            log.append(entry)
            if stop_on_error:
                break
            continue
        log.append(entry)

    return current, log


def log_to_dataframe(log: list[dict]) -> pd.DataFrame:
    """Change log as a tidy table (for the UI and for saving to CSV)."""
    cols = ["step", "op", "column", "status", "rows_before", "rows_after",
            "cells_changed", "message", "reason"]
    return pd.DataFrame(log, columns=cols)
