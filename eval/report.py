"""Summaries and charts from runs.csv."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ORDER = ["noop", "rules", "single", "agent"]
LABELS = {"noop": "Do nothing", "rules": "Rule-based", "single": "Single prompt", "agent": "DataTidy agent"}
FIX_COLS = ["fix_numeric_text", "fix_date_format", "fix_case_space", "fix_missing_token", "fix_outlier"]
FIX_NAMES = ["numbers as text", "date formats", "case / spacing", "hidden missing", "outliers"]


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if "error" in df:
        df = df[df["error"].isna() | (df["error"] == "")]
    return df.copy()


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    df = _clean(df)
    cols = ["cell_accuracy", "baseline_accuracy", "accuracy_gain", "damage_rate", "fabrication_rate",
            "row_loss_rate", "col_loss_rate", "dup_removal_rate", "recoverable_fix_rate", *FIX_COLS,
            "prompt_tokens", "completion_tokens", "latency_s", "failed_steps", "n_steps", "issues_after"]
    cols = [c for c in cols if c in df]
    g = df.groupby("system")
    out = g[cols].mean(numeric_only=True)
    out.insert(0, "runs", g.size())
    if "plan_valid_first_try" in df:
        valid = df.assign(v=df["plan_valid_first_try"].map({True: 1.0, False: 0.0, "True": 1.0, "False": 0.0}))
        out["valid_first_try"] = valid.groupby("system")["v"].mean()
    if "source" in df:
        out["fallback_rate"] = g["source"].apply(lambda s: (s == "fallback").mean())
    order = [s for s in ORDER if s in out.index] + [s for s in out.index if s not in ORDER]
    return out.loc[order]


def _pct(x):
    return "-" if pd.isna(x) else f"{100 * x:.1f}%"


def to_markdown(summary: pd.DataFrame) -> str:
    def table(cols: list[tuple[str, str, callable]], title: str) -> str:
        cols = [c for c in cols if c[0] in summary]
        lines = [f"### {title}", "", "| System | Runs | " + " | ".join(c[1] for c in cols) + " |",
                 "|---|---|" + "---|" * len(cols)]
        for sys_, r in summary.iterrows():
            lines.append(f"| {LABELS.get(sys_, sys_)} | {int(r['runs'])} | " +
                         " | ".join(c[2](r[c[0]]) for c in cols) + " |")
        return "\n".join(lines)

    num = lambda x: "-" if pd.isna(x) else f"{x:,.0f}"
    sec = lambda x: "-" if pd.isna(x) else f"{x:.1f}s"
    parts = [
        "# DataTidy benchmark results", "",
        table([("baseline_accuracy", "Start accuracy", _pct), ("cell_accuracy", "Cell accuracy", _pct),
               ("recoverable_fix_rate", "Recoverable fixed", _pct), ("dup_removal_rate", "Duplicates removed", _pct)],
              "Did it fix things?"), "",
        table([("damage_rate", "Damage (correct cells broken)", _pct), ("row_loss_rate", "Rows lost", _pct),
               ("col_loss_rate", "Columns lost", _pct), ("fabrication_rate", "Missing cells filled", _pct)],
              "Did it break things?"), "",
        table(list(zip(FIX_COLS, FIX_NAMES, [_pct] * 5)), "Fix rate by corruption type"), "",
        table([("valid_first_try", "Valid plan 1st try", _pct), ("fallback_rate", "Fallback used", _pct),
               ("failed_steps", "Failed steps / run", lambda x: f"{x:.1f}"),
               ("prompt_tokens", "Prompt tokens", num), ("completion_tokens", "Completion tokens", num),
               ("latency_s", "Latency", sec)], "Reliability and cost (LLM systems)"), "",
        "Notes: accuracy counts lost rows/columns as wrong. Damage is measured only on cells that were "
        "correct before cleaning. Missing cells filled = imputation of cells whose true value is missing. "
        "Averages over all datasets and seeds.",
    ]
    return "\n".join(parts)


def worst_cases(df: pd.DataFrame, k: int = 12) -> str:
    df = _clean(df)
    df = df[df["system"].isin(["rules", "single", "agent"])].copy()
    df["harm"] = df["damage_rate"] + df["row_loss_rate"] + df["col_loss_rate"]
    top = df.sort_values("harm", ascending=False).head(k)
    lines = ["# Worst cases (most harm)", "", "| System | Dataset | Seed | Damage | Rows lost | Cols lost | Accuracy |", "|---|---|---|---|---|---|---|"]
    for _, r in top.iterrows():
        lines.append(f"| {LABELS.get(r['system'], r['system'])} | {r['dataset']} | {int(r['seed'])} | "
                     f"{_pct(r['damage_rate'])} | {_pct(r['row_loss_rate'])} | {_pct(r['col_loss_rate'])} | {_pct(r['cell_accuracy'])} |")
    lines += ["", "Open `plans/<system>_<dataset>_s<seed>.json` to see exactly what the system did."]
    return "\n".join(lines)


def charts(summary: pd.DataFrame, out: Path) -> list[Path]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    paths = []
    names = [LABELS.get(s, s) for s in summary.index]
    colors = ["#9aa5b1", "#4f8ef7", "#f5a623", "#2bb673", "#8e6bd8"][: len(names)]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(names, 100 * summary["cell_accuracy"], color=colors)
    ax.set_ylabel("Cell accuracy (%)"); ax.set_ylim(0, 105)
    ax.set_title("Cell accuracy against ground truth")
    for b, v in zip(bars, summary["cell_accuracy"]):
        ax.text(b.get_x() + b.get_width() / 2, 100 * v + 1, f"{100 * v:.1f}", ha="center", fontsize=9)
    fig.tight_layout(); p = out / "accuracy.png"; fig.savefig(p, dpi=160); plt.close(fig); paths.append(p)

    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(names)); w = 0.26
    for i, (col, lab) in enumerate([("damage_rate", "Damage"), ("row_loss_rate", "Rows lost"), ("fabrication_rate", "Missing filled")]):
        if col in summary:
            ax.bar(x + (i - 1) * w, 100 * summary[col], w, label=lab)
    ax.set_xticks(x, names); ax.set_ylabel("% of cells / rows"); ax.legend()
    ax.set_title("Harm: what the cleaner broke")
    fig.tight_layout(); p = out / "harm.png"; fig.savefig(p, dpi=160); plt.close(fig); paths.append(p)

    cols = [c for c in FIX_COLS if c in summary]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = np.arange(len(cols)); w = 0.8 / max(len(names), 1)
    for i, (sys_, name) in enumerate(zip(summary.index, names)):
        ax.bar(x + i * w - 0.4 + w / 2, 100 * summary.loc[sys_, cols].astype(float).fillna(0), w, label=name, color=colors[i])
    ax.set_xticks(x, [FIX_NAMES[FIX_COLS.index(c)] for c in cols]); ax.set_ylabel("Fix rate (%)"); ax.legend(fontsize=8)
    ax.set_title("Fix rate by corruption type")
    fig.tight_layout(); p = out / "by_type.png"; fig.savefig(p, dpi=160); plt.close(fig); paths.append(p)
    return paths


def write_report(df: pd.DataFrame, out: str | Path) -> None:
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    summary = summarise(df)
    summary.to_csv(out / "summary.csv")
    (out / "summary.md").write_text(to_markdown(summary), encoding="utf-8")
    (out / "worst_cases.md").write_text(worst_cases(df), encoding="utf-8")
    charts(summary, out)
