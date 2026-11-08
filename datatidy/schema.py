"""Plan schema and validation.

An LLM plan is untrusted input. Before anything runs it must pass:
  1. structure   - a list of steps with op / column / params / reason
  2. operation   - op must be in the fixed library
  3. parameters  - validated per operation; unknown parameters are rejected
  4. columns     - referenced columns must exist (tracking renames and drops)

`validate_plan` collects ALL errors, so they can be fed back to the LLM in one go.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DropDuplicatesParams(_Params):
    subset: list[str] | None = None
    keep: Literal["first", "last"] = "first"


class FillMissingParams(_Params):
    strategy: Literal["mean", "median", "mode", "constant"] = "median"
    value: str | int | float | bool | None = None

    @model_validator(mode="after")
    def _constant_needs_value(self):
        if self.strategy == "constant" and self.value is None:
            raise ValueError("strategy 'constant' requires 'value'")
        return self


class CastTypeParams(_Params):
    target: Literal["int", "float", "str", "bool", "category"]


class NormaliseTextParams(_Params):
    lowercase: bool = True
    strip: bool = True
    collapse_spaces: bool = True


class StripSymbolsParams(_Params):
    symbols: str = "$€£¥%,"
    expand_suffixes: bool = False


class StandardizeMissingParams(_Params):
    tokens: list[str] | None = None


class ParseDatesParams(_Params):
    format: str | None = None
    dayfirst: bool = False


class MapValuesParams(_Params):
    mapping: dict[str, str | int | float | bool] = Field(min_length=1, max_length=500)
    case_insensitive: bool = False


class ClipOutliersParams(_Params):
    method: Literal["iqr", "zscore"] = "iqr"
    factor: float = Field(1.5, gt=0)
    threshold: float = Field(3.0, gt=0)
    action: Literal["clip", "set_missing"] = "clip"


class DropMissingRowsParams(_Params):
    threshold: float = Field(0.5, gt=0, le=1)


class RenameColumnParams(_Params):
    new_name: str = Field(min_length=1)


class DropColumnParams(_Params):
    pass


PARAM_MODELS: dict[str, type[_Params]] = {
    "drop_duplicates": DropDuplicatesParams,
    "fill_missing": FillMissingParams,
    "cast_type": CastTypeParams,
    "normalise_text": NormaliseTextParams,
    "strip_symbols": StripSymbolsParams,
    "standardize_missing": StandardizeMissingParams,
    "parse_dates": ParseDatesParams,
    "map_values": MapValuesParams,
    "clip_outliers": ClipOutliersParams,
    "drop_missing_rows": DropMissingRowsParams,
    "rename_column": RenameColumnParams,
    "drop_column": DropColumnParams,
}

# "required": needs a column | "optional": column may be omitted | "none": must not have one
COLUMN_RULE = {
    "drop_duplicates": "none", "standardize_missing": "optional", "drop_missing_rows": "optional",
}

# Human-readable catalogue used in the planner prompt.
OP_DOCS: dict[str, str] = {
    "standardize_missing": 'Turn hidden missing tokens ("N/A", "?", "null", "-") into real missing values. column optional (omit = all text columns). params: tokens (list, optional).',
    "strip_symbols": 'Convert text like "$1,200", "12%", "(500)" into numbers. column required. params: symbols (str), expand_suffixes (bool, for 1.2k / 3m).',
    "parse_dates": 'Parse date text (mixed formats OK) into real dates. column required. params: format (str, optional), dayfirst (bool).',
    "cast_type": 'Convert a column type. column required. params: target = int | float | str | bool | category.',
    "normalise_text": 'Trim, collapse repeated spaces, lowercase text. column required. params: lowercase, strip, collapse_spaces (bools).',
    "map_values": 'Merge category spellings with an explicit mapping. column required. params: mapping {"old": "new"} (required), case_insensitive (bool).',
    "fill_missing": 'Fill missing values. column required. params: strategy = mean | median | mode | constant; value (required for constant).',
    "clip_outliers": 'Handle implausible numeric extremes. column required. params: method = iqr | zscore, factor (iqr, default 1.5), threshold (zscore, default 3), action = clip | set_missing.',
    "drop_missing_rows": 'Drop rows missing a value in column, or (no column) rows with >= threshold fraction of cells missing. params: threshold (0-1, default 0.5).',
    "rename_column": 'Rename a column. column required. params: new_name (required).',
    "drop_column": 'Remove a column that is mostly missing or unusable. column required. params: none.',
    "drop_duplicates": 'Remove exact duplicate rows. NO column. params: subset (list of column names, optional), keep = first | last. Run AFTER all conversion/normalising steps and BEFORE fill_missing / clip_outliers.',
}


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: str
    column: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=3)


@dataclass
class ValidationResult:
    steps: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _fmt_pydantic(exc: ValidationError) -> str:
    parts = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e["loc"]) or "(value)"
        parts.append(f"{loc}: {e['msg']}")
    return "; ".join(parts)


def validate_plan(raw: Any, columns: list[str] | None = None) -> ValidationResult:
    """Validate a raw plan (list of dicts). Returns normalised steps plus all problems."""
    res = ValidationResult()
    if not isinstance(raw, list):
        res.errors.append("The plan must be a JSON list of steps.")
        return res
    if not raw:
        res.warnings.append("The plan is empty (no cleaning steps).")
        return res

    current = list(columns) if columns is not None else None

    for i, item in enumerate(raw, start=1):
        tag = f"step {i}"
        if not isinstance(item, dict):
            res.errors.append(f"{tag}: must be an object, got {type(item).__name__}.")
            continue
        try:
            step = PlanStep(**item)
        except ValidationError as exc:
            res.errors.append(f"{tag}: {_fmt_pydantic(exc)}")
            continue
        if step.op not in PARAM_MODELS:
            res.errors.append(f"{tag}: unknown operation '{step.op}'. Allowed: {sorted(PARAM_MODELS)}")
            continue
        tag = f"step {i} ({step.op})"

        rule = COLUMN_RULE.get(step.op, "required")
        if rule == "required" and not step.column:
            res.errors.append(f"{tag}: 'column' is required.")
            continue
        if rule == "none" and step.column:
            res.errors.append(f"{tag}: takes no 'column' (use params.subset instead).")
            continue

        try:
            params = PARAM_MODELS[step.op](**step.params).model_dump(exclude_unset=True)
        except ValidationError as exc:
            res.errors.append(f"{tag}: invalid params - {_fmt_pydantic(exc)}")
            continue

        if current is not None:
            if step.column and step.column not in current:
                shown = current if len(current) <= 30 else current[:30] + ["..."]
                res.errors.append(f"{tag}: column '{step.column}' does not exist. Columns: {shown}")
                continue
            if step.op == "drop_duplicates" and params.get("subset"):
                bad = [c for c in params["subset"] if c not in current]
                if bad:
                    res.errors.append(f"{tag}: subset has unknown columns {bad}.")
                    continue
            if step.op == "rename_column":
                new = params["new_name"]
                if new in current and new != step.column:
                    res.errors.append(f"{tag}: column '{new}' already exists.")
                    continue
                current = [new if c == step.column else c for c in current]
            elif step.op == "drop_column":
                current = [c for c in current if c != step.column]

        res.steps.append({"op": step.op, "column": step.column, "params": params, "reason": step.reason})

    return res


# Steps that make rows comparable. Deduplication must come AFTER these...
CLEANUP_OPS = {"standardize_missing", "strip_symbols", "parse_dates", "cast_type",
               "normalise_text", "map_values", "rename_column"}


def place_dedupe(steps: list[dict]) -> tuple[list[dict], bool]:
    """Safety rule (found by the Week 1 and Week 3 experiments).

    Deduplicate AFTER normalising / converting (rows that differ only by case, spacing or
    symbols are not identical yet) but BEFORE filling missing values or clipping outliers
    (imputing the same median into two different rows can make them look identical, and
    dedupe would then delete a real record).

    Moves every drop_duplicates step to just after the last cleanup step. Other steps are never
    reordered (the prompt and the rule-based plan are responsible for their order).
    Returns (steps, changed).
    """
    others = [x for x in steps if x["op"] != "drop_duplicates"]
    dedupes = [x for x in steps if x["op"] == "drop_duplicates"]
    last = max((i for i, x in enumerate(others) if x["op"] in CLEANUP_OPS), default=-1)
    new = others[: last + 1] + dedupes + others[last + 1:]
    return new, new != steps
