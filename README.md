# DataTidy Agent

A **trustworthy LLM agent for cleaning messy CSV files**. The model proposes a cleaning plan, you review it,
and a deterministic executor applies it with a fixed library of safe operations and logs every change.
Success is **measured against ground truth**, not just demoed.

> **Status: Week 3 of 4 complete.** Deterministic core (Week 1), LLM planner (Week 2), benchmark and web UI
> (Week 3). Remaining: real LLM results and the write-up. See the [roadmap](#roadmap).

## Why

An agent that "works" is not the same as an agent you can trust. DataTidy is built around that gap:

- **The LLM never runs code.** It can only choose from 12 safe operations.
- **Its output is untrusted.** Plans are validated (operations, parameters, column names), retried once with the
  exact errors, and replaced by a rule-based fallback if still invalid.
- **Plan, review, execute.** You see every step and its reason, and can untick or edit steps first.
- **Everything is logged**, including warnings when values could not be converted.
- **Measured, not claimed.** A benchmark with ground truth reports fix rates *and* damage.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_datasets.py && python scripts/make_messy_samples.py
pytest                                                    # 113 tests, no API key needed

streamlit run app.py                                      # web UI
python -m datatidy profile data/messy/tips_messy.csv      # CLI: what is wrong with this file?
python -m datatidy clean   data/messy/tips_messy.csv --provider groq
```

Providers (put a key in `.env`, copied from `.env.example`; never commit it):

| Provider | Cost | Setup |
|---|---|---|
| `groq` | Free tier (rate limited) | key from console.groq.com |
| `gemini` | Free tier (rate limited) | key from aistudio.google.com |
| `ollama` | Free, local | install Ollama, `ollama pull llama3.2` |
| `openai` | Paid | key from platform.openai.com |
| *Rule-based* | Free, no key | UI option / `eval` baseline |

Free-tier limits and model names change; override with `--model` or `DATATIDY_MODEL`.
**Privacy:** the LLM receives a profile summary (stats and a few sample values), not the file.

## Web UI

`streamlit run app.py`: upload a CSV (or pick a sample), see the detected issues, click **Propose cleaning plan**,
then untick steps or edit their JSON parameters in the table, and **Run cleaning**. You get before/after metrics,
the cleaned data, a change log, remaining issues, and downloads for the CSV, log and plan.

## How it works

```
CSV -> profile (no LLM) -> planner (LLM) -> validate -> [retry once] -> [rule-based fallback]
    -> user review -> deterministic executor -> cleaned CSV + change log
```

| Module | Purpose |
|---|---|
| `datatidy/profiler.py` | Detects duplicates, missing values, hidden tokens (`N/A`, `?`), numbers/dates stored as text, mixed date formats, inconsistent categories, whitespace, outliers |
| `datatidy/operations.py` | 12 safe operations; never modify input; unknown parameters rejected; row removal keeps original index |
| `datatidy/schema.py` | Pydantic validation of plans, column tracking through renames/drops |
| `datatidy/llm.py` | One backend for Groq / OpenAI / Gemini / Ollama, with token and latency tracking |
| `datatidy/planner.py` | Prompt, JSON extraction, validation, retry, fallback |
| `datatidy/executor.py` | Runs a plan on a copy; a failing step is logged and skipped |
| `eval/` | Benchmark: corruption generator, baselines, metrics, runner, report |
| `app.py` | Streamlit UI |

Operations: `standardize_missing`, `strip_symbols`, `parse_dates`, `cast_type`, `normalise_text`, `map_values`,
`rename_column`, `drop_duplicates`, `fill_missing`, `clip_outliers`, `drop_missing_rows`, `drop_column`.

## Evaluation

### Benchmark design

10 public datasets (tips, penguins, titanic, mpg, planets, healthexp, exercise, diamonds, dowjones, seaice), each
corrupted with 3 seeds = **30 cases**. The clean table is the ground truth. Natural duplicates are removed first, because
they are indistinguishable from injected ones. Corruptions are recorded, so every injected cell is known.

| Corruption | Kind | Example |
|---|---|---|
| Numbers as text | recoverable | `$1,234.5`, `12.5%` |
| Mixed date formats | recoverable | `2024-03-05`, `05 Mar 2024`, `03/05/2024` |
| Case / spacing noise | recoverable | `FEMALE`, `  female ` |
| Duplicate rows | recoverable | the same record entered again, **corrupted independently** (near-duplicates) |
| Hidden missing tokens | lossy | `N/A`, `?`, `-` replace real values |
| Outliers | lossy | value x 10 |

### Systems compared

| System | Description |
|---|---|
| Do nothing | the messy file as-is |
| Rule-based | plan from profiler flags only, no LLM |
| Single prompt | one minimal LLM call: same operations and profile, but no rules, validation, retry, fallback or ordering fix |
| **DataTidy agent** | rules prompt + validation + retry + fallback + dedupe-placement safeguard |

"Single prompt" vs "agent" isolates what the scaffolding around the model is worth.

### Metrics

| Metric | Meaning |
|---|---|
| Cell accuracy | correct cells / all cells of the clean table (lost rows or columns count as wrong) |
| **Damage rate** | cells that were correct before cleaning and are wrong after |
| Fix rate per type | exact value restored (numbers, dates), consistent with siblings (case), token gone (hidden missing), error at least halved (outliers) |
| Duplicates removed | share of injected duplicate rows removed |
| Rows / columns lost | original rows or columns that no longer exist |
| Missing cells filled | cells whose true value is missing but now hold a value (imputation) |
| Valid first try, fallback rate, tokens, latency | reliability and cost of the LLM systems |

### Results so far (no LLM yet)

30 cases. The LLM columns are filled in by running the benchmark with a key (below).

| System | Cell accuracy | Recoverable fixed | Duplicates removed | Damage | Rows lost | Missing cells filled |
|---|---|---|---|---|---|---|
| Do nothing | 53.4% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| Rule-based | 97.8% | 100.0% | 77.2% | 0.0% | 0.0% | 24.9% |
| Single prompt | _run_ | | | | | |
| DataTidy agent | _run_ | | | | | |

**Read this honestly:** the rule-based baseline scores so high because every corruption I inject is something my profiler
is built to detect. It is a *ceiling-ish baseline for this benchmark*, not a claim that rules solve data cleaning.
It leaves outliers untouched (0%, a deliberate choice) and imputes 24.9% of genuinely missing cells. 77% duplicate removal
is the limit of exact matching: a duplicate pair that differs in a lossy cell (one copy has `N/A`) cannot be matched.

### Run the benchmark

```bash
python -m eval.run_eval --systems noop,rules                         # no key needed (about 10 s)
python -m eval.run_eval --systems noop,rules,single,agent --provider groq --seeds 0 --sleep 20
python -m eval.run_eval --systems noop,rules,single,agent --provider groq --seeds 1 2 --sleep 20 --resume
```

Results go to `eval/results/`: `runs.csv` (one row per run), `summary.md`, `worst_cases.md`, three charts, and
`plans/` (the plan every system produced, for failure analysis). Free tiers have per-minute and per-day token limits,
so start with one seed and use `--resume` to continue the next day.

## What the benchmark found (before any LLM ran)

1. **Dedupe order matters, and my first rule was wrong.** Week 1: deduplicating before normalising leaves near-duplicates.
   Week 3: deduplicating *after filling* deleted real rows, because filling two different rows with the same median made them
   identical. The enforced rule is **normalise, then dedupe, then fill**.
2. **The benchmark caught a bug in my own profiler.** `"30 min"` was classified as "numbers stored as text"; the cleaner turned every
   value into a missing value and filled the median (damage 24%). Unit suffixes are no longer flagged. A regression test pins it.
3. **My first metric could be fooled by float noise** (`59.400000000000006` vs `59.4`): an untouched outlier looked "improved".
   Outliers now need at least half the error removed.
4. **Exact duplicates were too easy.** Copying an already-corrupted row made dedupe-first look fine. Real duplicates are the same
   record entered differently, so each copy is now corrupted independently.

## Known limitations

- LLM results are not in yet; the LLM code paths are tested with scripted fake models and a mock HTTP server.
- Only exact duplicate matching; near-duplicate (fuzzy) matching is future work.
- The corruption types overlap with what the profiler detects, so the rule-based baseline is optimistic.
- Ten datasets, three seeds; averages hide per-dataset variation (see `runs.csv`).
- Text is compared case-insensitively in the accuracy grid, so lowercasing categories is not punished.
- Only CSV files, up to a few hundred thousand rows.

## Roadmap

- [x] **Week 1** - profiler, operations, executor, change log, CLI
- [x] **Week 2** - plan schema, LLM planner (Groq / Gemini / Ollama / OpenAI), validation, retry, fallback
- [x] **Week 3** - benchmark with ground truth, baselines, metrics, report, Streamlit UI
- [ ] **Week 4** - run the LLM systems, failure analysis, demo video, write-up
- [ ] **v2** - multi-agent upgrade (profiler / planner / verifier / critic), measured on this benchmark

## License

MIT
