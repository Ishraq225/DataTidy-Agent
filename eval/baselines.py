"""The systems being compared.

  noop    do nothing (the messy file as-is)
  rules   deterministic plan from profiler flags only (no LLM)
  single  ONE minimal LLM call. Same operations and same profile as the agent, but NO rules in the
          prompt, NO validation, NO retry, NO fallback and NO ordering safeguard.
  agent   DataTidy v1: rules prompt + validation + one retry + rule-based fallback + dedupe-last.

`single` vs `agent` isolates the value of the scaffolding around the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from datatidy.executor import run_plan
from datatidy.llm import LLMBackend
from datatidy.planner import ORDER_OF_OPERATIONS, extract_json, make_plan, rule_based_plan
from datatidy.profiler import profile_dataframe, profile_to_text
from datatidy.schema import OP_DOCS, validate_plan

SYSTEMS = ("noop", "rules", "single", "agent")
LLM_SYSTEMS = ("single", "agent")


@dataclass
class SystemResult:
    cleaned: pd.DataFrame
    plan: list[dict] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)
    source: str = ""
    attempts: int = 0
    plan_valid_first_try: bool | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    errors: list[str] = field(default_factory=list)


def run_noop(df: pd.DataFrame, backend=None) -> SystemResult:
    return SystemResult(cleaned=df.copy(), source="noop")


def run_rules(df: pd.DataFrame, backend=None) -> SystemResult:
    plan = rule_based_plan(profile_dataframe(df))
    cleaned, log = run_plan(df, plan)
    return SystemResult(cleaned, plan, log, source="rules", plan_valid_first_try=True)


SINGLE_SYSTEM = """You clean messy CSV files. You get a profile of a dataset. Reply with JSON only:
{"plan": [{"op": "...", "column": "...", "params": {...}, "reason": "..."}]}

Available operations:
""" + "\n".join(f"- {op}: {OP_DOCS[op]}" for op in ORDER_OF_OPERATIONS)


def run_single_prompt(df: pd.DataFrame, backend: LLMBackend) -> SystemResult:
    profile_text = profile_to_text(profile_dataframe(df))
    resp = backend.complete(SINGLE_SYSTEM, f"PROFILE:\n{profile_text}\n\nClean this dataset.")
    res = SystemResult(cleaned=df.copy(), source="single", attempts=1,
                       prompt_tokens=resp.prompt_tokens, completion_tokens=resp.completion_tokens,
                       latency_s=resp.latency_s)
    try:
        obj = extract_json(resp.text)
        raw = obj.get("plan") if isinstance(obj, dict) else obj
    except ValueError as exc:
        res.errors, res.plan_valid_first_try = [str(exc)], False
        return res                                       # no retry, no fallback: nothing happens
    if not isinstance(raw, list):
        res.errors, res.plan_valid_first_try = ["plan is not a list"], False
        return res
    check = validate_plan(raw, [str(c) for c in df.columns])       # measured, NOT enforced
    res.plan_valid_first_try, res.errors = check.ok, check.errors
    steps = [s for s in raw if isinstance(s, dict)]               # raw steps run as-is
    res.plan = steps
    res.cleaned, res.log = run_plan(df, steps)
    return res


def run_agent(df: pd.DataFrame, backend: LLMBackend) -> SystemResult:
    pr = make_plan(df, backend)
    cleaned, log = run_plan(df, pr.plan)
    return SystemResult(cleaned, pr.plan, log, source=pr.source, attempts=pr.attempts,
                        plan_valid_first_try=(pr.source == "llm"), prompt_tokens=pr.prompt_tokens,
                        completion_tokens=pr.completion_tokens, latency_s=pr.latency_s, errors=pr.errors)


RUNNERS = {"noop": run_noop, "rules": run_rules, "single": run_single_prompt, "agent": run_agent}
