"""End-to-end: profile -> plan -> (approval) -> execute -> report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from .executor import run_plan
from .llm import LLMBackend
from .planner import PlannerResult, make_plan
from .profiler import profile_dataframe


@dataclass
class CleanResult:
    cleaned: pd.DataFrame | None
    log: list[dict]
    planner: PlannerResult
    profile_before: dict
    profile_after: dict | None
    approved: bool


def format_plan(plan: list[dict]) -> str:
    if not plan:
        return "(empty plan: nothing to clean)"
    lines = []
    for i, s in enumerate(plan, 1):
        target = f" on '{s['column']}'" if s.get("column") else ""
        params = f" {s['params']}" if s.get("params") else ""
        lines.append(f"{i:>2}. {s['op']}{target}{params}\n      why: {s['reason']}")
    return "\n".join(lines)


def clean_dataframe(df: pd.DataFrame, backend: LLMBackend,
                    approve: Callable[[list[dict]], list[dict] | bool] | None = None) -> CleanResult:
    """Plan and (if approved) execute.

    `approve` receives the plan and returns True/False, or a (possibly edited) list of steps.
    With approve=None the plan runs automatically.
    """
    before = profile_dataframe(df)
    planner = make_plan(df, backend, profile=before)
    plan = planner.plan

    if approve is not None:
        decision = approve(plan)
        if decision is False:
            return CleanResult(None, [], planner, before, None, approved=False)
        if isinstance(decision, list):
            plan = decision
            planner.plan = plan

    cleaned, log = run_plan(df, plan)
    return CleanResult(cleaned, log, planner, before, profile_dataframe(cleaned), approved=True)


# ---------------------------------------------------------------------------
# helpers for the plan-review table in the UI
# ---------------------------------------------------------------------------

def plan_to_table(plan: list[dict]) -> pd.DataFrame:
    """Plan as an editable table: tick/untick steps, edit params as JSON."""
    import json
    return pd.DataFrame([{
        "apply": True, "op": s["op"], "column": s.get("column") or "",
        "params": json.dumps(s.get("params") or {}, ensure_ascii=False), "reason": s.get("reason", ""),
    } for s in plan], columns=["apply", "op", "column", "params", "reason"])


def table_to_plan(table: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """Ticked rows back to plan steps. Returns (steps, errors); invalid JSON params are reported."""
    import json
    steps, errors = [], []
    for i, row in enumerate(table.to_dict("records"), start=1):
        if not row.get("apply"):
            continue
        try:
            params = json.loads(row.get("params") or "{}")
            if not isinstance(params, dict):
                raise ValueError("params must be a JSON object")
        except ValueError as exc:
            errors.append(f"row {i} ({row.get('op')}): params is not valid JSON - {exc}")
            continue
        steps.append({"op": row["op"], "column": row.get("column") or None, "params": params,
                      "reason": row.get("reason") or "edited by user"})
    return steps, errors
