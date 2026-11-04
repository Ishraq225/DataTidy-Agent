# DataTidy Agent

A **trustworthy LLM agent for cleaning messy CSV files**. The LLM proposes a cleaning
plan; a deterministic executor applies it using a fixed library of safe operations;
every change is logged. Success is *measured* against ground truth, not just demoed.

> **Status: Week 1 of 4 complete (deterministic core).** The LLM planner, evaluation
> benchmark and UI come next. See the [roadmap](#roadmap).

## Why

An agent that "works" is not the same as an agent you can trust. DataTidy is built around
that gap:

- **The LLM never runs code.** It can only choose from a fixed operation library.
- **Plan, review, then execute.** The user sees and approves the plan.
- **Every change is logged**, including warnings when values could not be converted.
- **Measured, not claimed.** Week 3 adds a benchmark with a *damage rate* metric
  (how often the cleaner breaks values that were already correct).

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_datasets.py                    # tips, penguins, titanic
python scripts/make_messy_samples.py                   # seeded corrupted versions

python -m datatidy profile data/messy/tips_messy.csv   # what is wrong with this file?
python -m datatidy apply data/messy/tips_messy.csv examples/plans/tips_plan.json \
       -o cleaned.csv --log change_log.csv             # apply a cleaning plan
pytest                                                 # 36 tests
```

## What exists so far

| Module | Purpose |
|---|---|
| `datatidy/profiler.py` | Describes a dataset and flags issues: duplicates, missing values, hidden missing tokens (`N/A`, `?`), numbers/dates stored as text, mixed date formats, inconsistent categories, whitespace, outliers |
| `datatidy/operations.py` | Safe operation library (below) |
| `datatidy/executor.py` | Runs a plan on a *copy* of the data, logs each step, skips failed steps |
| `datatidy/__main__.py` | CLI: `profile` and `apply` |

### Operations (v0.1)

| Operation | What it does |
|---|---|
| `drop_duplicates` | Remove duplicate rows (all columns or a subset) |
| `fill_missing` | Fill nulls with mean / median / mode / constant |
| `cast_type` | Convert to int / float / str / bool / category; refuses to truncate 2.7 to 2 |
| `normalise_text` | Trim, collapse spaces, lowercase |
| `strip_symbols` | `"$1,200"`, `"12%"`, `"(500)"` to numbers; `1.2k` suffixes are opt-in |
| `standardize_missing` | Turn hidden tokens like `N/A` and `?` into real missing values |

Design rules: operations never modify their input; unknown parameters raise an error
instead of being ignored; values that cannot be converted are counted and reported.

### Plan format

```json
[
  {"op": "strip_symbols", "column": "total_bill", "reason": "100% of values carry a '$' sign"},
  {"op": "fill_missing", "column": "tip", "params": {"strategy": "median"}, "reason": "right-skewed"}
]
```

## Roadmap

- [x] **Week 1** - profiler, 6 operations, executor, change log, CLI, tests, 3 datasets
- [ ] **Week 2** - Pydantic plan schema, LLM planner (OpenAI + Ollama), validation + retry, remaining operations (`parse_dates`, `map_values`, `clip_outliers`, `drop_missing_rows`, `rename_column`)
- [ ] **Week 3** - corruption generator with ground truth, baselines, metrics, Streamlit UI
- [ ] **Week 4** - failure analysis, results, demo video, write-up
- [ ] **v2** - multi-agent upgrade (profiler / planner / verifier / critic), measured against the v1 benchmark

## Known limitations (Week 1)

- Outlier *detection* exists, but there is no outlier *treatment* yet. Flagged outliers are often
  legitimate (e.g. a very high ticket fare), so the planner must not clip blindly.
- Exact-duplicate removal can delete legitimate identical records; this is a case the Week 3
  damage metric is designed to catch.
- Date parsing is not implemented yet (the profiler detects date columns and mixed formats).

## License

MIT
