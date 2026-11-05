"""The planner: profile in, validated cleaning plan out.

    profile text --LLM--> JSON --validate--> (retry once with errors) --> fallback

The LLM only ever sees the profile summary (never the full file), and its output
is untrusted until it passes `validate_plan`. If it still fails after the retry,
a deterministic rule-based plan is used, so the pipeline never breaks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import pandas as pd

from .llm import LLMBackend
from .profiler import profile_dataframe, profile_to_text
from .schema import OP_DOCS, move_dedupe_last, validate_plan

ORDER_OF_OPERATIONS = [
    "standardize_missing", "strip_symbols", "parse_dates", "cast_type",
    "normalise_text", "map_values", "rename_column",
    "fill_missing", "clip_outliers", "drop_missing_rows", "drop_column",
    "drop_duplicates",
]


def build_system_prompt() -> str:
    catalogue = "\n".join(f"- {op}: {OP_DOCS[op]}" for op in ORDER_OF_OPERATIONS)
    return f"""You are a careful data-cleaning planner. You receive a PROFILE of a CSV file and
must propose a cleaning plan. You never see or write code: you only choose from the operations below.

OPERATIONS (use only these):
{catalogue}

OUTPUT: a single JSON object, nothing else: {{"plan": [ {{"op": "...", "column": "...", "params": {{...}}, "reason": "..."}} ]}}

RULES:
1. Every step needs a "reason" that cites evidence from the profile (a number, a percentage, an example value).
2. Only fix problems the profile shows. If a column looks fine, do nothing to it. An empty plan is valid.
3. Use exact column names from the profile. Never invent columns.
4. Order steps like the list above: hidden-missing tokens first, then conversions (symbols, dates, types),
   then text normalisation / mapping, then filling or dropping, and drop_duplicates ALWAYS LAST
   (rows that differ only by case, spacing or symbols only become identical after normalising).
5. fill_missing: use median for skewed numeric columns (check median vs mean/range), mean only if clearly
   symmetric, mode for categories. If a column is more than ~50% missing, prefer drop_column over filling.
6. "Outliers" in the profile are only statistical flags. Natural skew (e.g. prices, fares) is NOT an error.
   Use clip_outliers only for values that are physically implausible for what the column measures.
7. Hidden missing tokens ("N/A", "?") must be converted with standardize_missing BEFORE any numeric conversion.
8. Do not use map_values unless the profile lists concrete variant spellings that normalise_text cannot fix.
"""


def build_user_prompt(profile_text: str, errors: list[str] | None = None) -> str:
    msg = f"PROFILE:\n{profile_text}\n\nReturn the cleaning plan as JSON."
    if errors:
        msg += ("\n\nYour previous plan was REJECTED for these reasons:\n- " + "\n- ".join(errors[:15])
                + "\nReturn a corrected, complete plan as JSON.")
    return msg


def extract_json(text: str):
    """Parse JSON from an LLM reply, tolerating code fences and surrounding prose."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for m in re.finditer(r"[\[{]", text):
        try:
            obj, _ = decoder.raw_decode(text[m.start():])
            return obj
        except json.JSONDecodeError:
            continue
    raise ValueError("The reply did not contain valid JSON.")


def _unwrap(obj):
    if isinstance(obj, dict) and "plan" in obj:
        return obj["plan"]
    return obj


# ---------------------------------------------------------------------------
# deterministic fallback (also the Week 3 "rule-based baseline")
# ---------------------------------------------------------------------------

def rule_based_plan(profile: dict) -> list[dict]:
    """Conservative plan built only from profiler flags. No LLM involved."""
    n_rows = max(profile["n_rows"], 1)
    steps: list[dict] = []
    numeric_after: set[str] = set()

    for c in profile["columns"]:
        name = c["name"]
        if c.get("hidden_missing"):
            steps.append({"op": "standardize_missing", "column": name, "params": {},
                          "reason": f"{c['hidden_missing']} cell(s) use tokens like {c.get('hidden_missing_tokens')}"})
    for c in profile["columns"]:
        name = c["name"]
        if c["kind"] == "text" and c.get("numeric_like_pct", 0) >= 0.8:
            steps.append({"op": "strip_symbols", "column": name, "params": {},
                          "reason": f"{int(c['numeric_like_pct'] * 100)}% of values look numeric but are stored as text"})
            numeric_after.add(name)
        elif c["kind"] == "text" and c.get("date_like_pct", 0) >= 0.8:
            steps.append({"op": "parse_dates", "column": name, "params": {},
                          "reason": f"{int(c['date_like_pct'] * 100)}% of values look like dates stored as text"})
    for c in profile["columns"]:
        name = c["name"]
        if (c["kind"] == "text" and name not in numeric_after and c.get("date_like_pct", 0) < 0.8
                and (c.get("category_variants") or c.get("whitespace_issues"))):
            steps.append({"op": "normalise_text", "column": name, "params": {},
                          "reason": "case/spacing variants or stray whitespace detected"})
    for c in profile["columns"]:
        name = c["name"]
        missing = c["n_missing"] + c.get("hidden_missing", 0)
        if not missing:
            continue
        if missing / n_rows >= 0.5:
            continue                      # too sparse to fill safely; leave for a human
        if c["kind"] == "numeric" or name in numeric_after:
            steps.append({"op": "fill_missing", "column": name, "params": {"strategy": "median"},
                          "reason": f"{missing} missing numeric value(s); median is robust to skew"})
        elif c["kind"] == "text":
            steps.append({"op": "fill_missing", "column": name, "params": {"strategy": "mode"},
                          "reason": f"{missing} missing categorical value(s)"})
    if profile["n_duplicate_rows"]:
        steps.append({"op": "drop_duplicates", "column": None, "params": {},
                      "reason": f"{profile['n_duplicate_rows']} duplicate row(s); run last"})
    return steps


# ---------------------------------------------------------------------------
# planner
# ---------------------------------------------------------------------------

@dataclass
class PlannerResult:
    plan: list[dict]
    source: str                         # "llm" | "llm_retry" | "fallback"
    attempts: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)       # last validation errors, if any
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    raw_responses: list[str] = field(default_factory=list)


def make_plan(df: pd.DataFrame, backend: LLMBackend, profile: dict | None = None,
              max_retries: int = 1, fallback: bool = True) -> PlannerResult:
    profile = profile or profile_dataframe(df)
    profile_text = profile_to_text(profile)
    system = build_system_prompt()
    columns = [str(c) for c in df.columns]

    result = PlannerResult(plan=[], source="llm")
    errors: list[str] | None = None

    for attempt in range(1, max_retries + 2):
        result.attempts = attempt
        resp = backend.complete(system, build_user_prompt(profile_text, errors))
        result.prompt_tokens += resp.prompt_tokens
        result.completion_tokens += resp.completion_tokens
        result.latency_s += resp.latency_s
        result.raw_responses.append(resp.text)

        try:
            raw = _unwrap(extract_json(resp.text))
        except ValueError as exc:
            errors = [str(exc)]
            continue

        validation = validate_plan(raw, columns)
        if validation.ok:
            steps, moved = move_dedupe_last(validation.steps)
            result.plan = steps
            result.warnings = validation.warnings + (
                ["drop_duplicates was moved to the end of the plan (safety rule)."] if moved else [])
            result.source = "llm" if attempt == 1 else "llm_retry"
            result.errors = []
            return result
        errors = validation.errors

    result.errors = errors or []
    if not fallback:
        result.source = "failed"
        return result
    result.source = "fallback"
    result.plan = rule_based_plan(profile)
    result.warnings.append("The LLM plan was invalid after retrying; a rule-based fallback plan is used.")
    return result
