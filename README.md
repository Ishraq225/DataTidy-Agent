<<<<<<< HEAD
# DataTidy Agent

A **trustworthy LLM agent for cleaning messy CSV files**. The LLM proposes a cleaning
plan; a deterministic executor applies it using a fixed library of safe operations;
every change is logged. Success is *measured* against ground truth, not just demoed.

> **Status: Week 2 of 4 complete (LLM planner).** The evaluation benchmark and UI come next.
> See the [roadmap](#roadmap).

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
pytest                                                 # 81 tests
```

### Using the LLM planner

Pick one provider and put its key in a `.env` file (copy `.env.example`; never commit `.env`):

| Provider | Cost | Setup |
|---|---|---|
| `groq` | Free tier (rate limited) | key from console.groq.com |
| `gemini` | Free tier (rate limited) | key from aistudio.google.com |
| `ollama` | Free, runs locally | install Ollama, then `ollama pull llama3.2` |
| `openai` | Paid (prepaid credits) | key from platform.openai.com |

```bash
python -m datatidy plan  data/messy/tips_messy.csv --provider groq     # just show/save the plan
python -m datatidy clean data/messy/tips_messy.csv --provider groq     # plan, ask approval, clean
python -m datatidy clean data/messy/tips_messy.csv --provider ollama --model llama3.2 --yes
```

Free-tier limits and model names change often; check the provider's console and override the
model with `--model` or `DATATIDY_MODEL` if the default is unavailable.

**Privacy:** the LLM receives a profile summary (column stats and a few sample values), not the
whole file. Do not use sensitive data with cloud providers; use Ollama for that.

## What exists so far

| Module | Purpose |
|---|---|
| `datatidy/profiler.py` | Describes a dataset and flags issues: duplicates, missing values, hidden missing tokens (`N/A`, `?`), numbers/dates stored as text, mixed date formats, inconsistent categories, whitespace, outliers |
| `datatidy/operations.py` | Safe operation library (below) |
| `datatidy/executor.py` | Runs a plan on a *copy* of the data, logs each step, skips failed steps |
| `datatidy/schema.py` | Pydantic validation of LLM plans: operations, parameters, column names (tracks renames/drops) |
| `datatidy/llm.py` | One backend class for Groq / OpenAI / Gemini / Ollama, plus a fake backend for tests |
| `datatidy/planner.py` | Prompt, JSON extraction, validate, one retry with error feedback, rule-based fallback |
| `datatidy/pipeline.py` | Profile, plan, approval hook, execute, before/after report |
| `datatidy/__main__.py` | CLI: `profile`, `plan`, `clean`, `apply` |

### Operations (12, frozen)

| Operation | What it does |
|---|---|
| `drop_duplicates` | Remove duplicate rows (all columns or a subset) |
| `fill_missing` | Fill nulls with mean / median / mode / constant |
| `cast_type` | Convert to int / float / str / bool / category; refuses to truncate 2.7 to 2 |
| `normalise_text` | Trim, collapse spaces, lowercase |
| `strip_symbols` | `"$1,200"`, `"12%"`, `"(500)"` to numbers; `1.2k` suffixes are opt-in |
| `standardize_missing` | Turn hidden tokens like `N/A` and `?` into real missing values |
| `parse_dates` | Mixed-format date text to real dates; ambiguous `03/04/2024` follows `dayfirst` |
| `map_values` | Merge category spellings with an explicit mapping |
| `clip_outliers` | IQR or z-score; clip or set to missing |
| `drop_missing_rows` | Drop rows missing one column, or mostly empty rows |
| `rename_column` / `drop_column` | Rename or remove a column |

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
- [x] **Week 2** - Pydantic plan schema, LLM planner (Groq / Gemini / Ollama / OpenAI), validation + retry + fallback, 12 operations
- [ ] **Week 3** - corruption generator with ground truth, baselines, metrics, Streamlit UI
- [ ] **Week 4** - failure analysis, results, demo video, write-up
- [ ] **v2** - multi-agent upgrade (profiler / planner / verifier / critic), measured against the v1 benchmark

## Safety design

1. The LLM chooses from a fixed operation list and never writes code.
2. Its output is untrusted: structure, operation, parameters and column names are validated.
3. Invalid plans get **one retry** with the exact errors; after that a deterministic rule-based plan is used.
4. `drop_duplicates` is always moved to the end, because rows only become identical after normalising.
5. The user sees every step and its reason, and can reject the plan before anything runs.

## Known limitations

- Outlier *detection* exists, but there is no outlier *treatment* yet. Flagged outliers are often
  legitimate (e.g. a very high ticket fare), so the planner must not clip blindly.
- Exact-duplicate removal can delete legitimate identical records; this is a case the Week 3
  damage metric is designed to catch.
- Ambiguous dates (`03/04/2024`) are parsed month-first unless `dayfirst` is set; the log states the assumption.
- The LLM planner has been verified against a mock server and a fake backend, and still needs a measured evaluation (Week 3).

## License

MIT
=======
# DataTidy Agent 🧹

**A trustworthy data-cleaning agent for messy CSV files.**

DataTidy is built around one idea: the gap between a system that works and a system you can trust.

**Project Status:** Day 1 of 4 | Deterministic Core Completed

The profiler, safe operation library, executor, CLI, and change log are implemented and tested. The LLM planner, evaluation benchmark, and user interface are planned for the next stages.

See the [Project Roadmap](#roadmap).

---

## 💡 The Idea

Most "AI data-cleaning" demos allow a model to write and execute code directly on your data, then demonstrate that it works once.

DataTidy takes a different approach.

Instead of allowing an LLM to execute arbitrary code, DataTidy will restrict it to selecting operations from a small, predefined library of safe cleaning functions.

The project follows four core principles:

- **The model never executes code:** It can only propose a cleaning plan using approved operations.
- **Plan, review, then execute:** Every cleaning plan is presented as readable steps, each with a reason, before any changes are applied.
- **Everything is logged:** Each operation reports exactly how many cells or rows it changed and identifies values that could not be converted.
- **Success is measured, not claimed:** Day 3 introduces a benchmark with ground truth and a damage-rate metric to measure how often the cleaner changes values that were already correct.

**Day 1 focuses on building the part that must remain reliable regardless of which LLM is used later: the deterministic core.**

---

## ⚙️ What Works Today

| Component | File | Description |
|---|---|---|
| Profiler | `datatidy/profiler.py` | Profiles datasets and detects potential data quality issues. |
| Operations | `datatidy/operations.py` | Provides six safe cleaning operations with precise change reports. |
| Executor | `datatidy/executor.py` | Executes cleaning plans on a copy of the data and logs every step. |
| CSV I/O | `datatidy/io.py` | Loads and saves CSV files without silently hiding missing-value tokens. |
| CLI | `datatidy/__main__.py` | Provides `profile` and `apply` commands. |

## 🔍 What the Profiler Detects

The profiler examines a dataset and identifies potential problems before cleaning begins.

| Issue | Example |
|---|---|
| Duplicate rows | 11 fully duplicated rows |
| Missing values | 12% of the age column is empty |
| Hidden missing tokens | `N/A`, `?`, `null`, `-` |
| Numbers stored as text | `"$1,200"`, `"12%"`, `"(500)"` |
| Dates stored as text | `"2024-01-05"`, `"Mar 5, 2024"` |
| Mixed date formats | `2024-01-05` and `03/04/2024` |
| Inconsistent categories | `Female`, `FEMALE`, `female` |
| Stray whitespace | Leading, trailing, or doubled spaces |
| Numeric outliers | Values outside the 1.5 × IQR range |

**Important:** Outliers are flagged for investigation, not automatically treated as incorrect values.

---

## 🛠️ Safe Cleaning Operations

DataTidy currently provides six cleaning operations.

| Operation | What It Does | Safety Behaviour |
|---|---|---|
| `drop_duplicates` | Removes duplicate rows, using all columns or a selected subset. | Reports the number of rows removed. |
| `fill_missing` | Fills missing values using mean, median, mode, or a constant. | Refuses mean/median on non-numeric columns. |
| `cast_type` | Converts values to `int`, `float`, `str`, `bool`, or `category`. | Refuses to truncate values such as `2.7` to `2` and counts conversion failures. |
| `normalise_text` | Trims whitespace, collapses spaces, and normalises letter case. | Leaves missing values untouched. |
| `strip_symbols` | Converts values such as `"$1,200"`, `"12%"`, and `"(500)"` into numbers. | Optional suffix handling; unparseable values are counted, not silently hidden. |
| `standardize_missing` | Converts tokens such as `N/A`, `?`, and `null` into actual missing values. | Supports custom missing-value token lists. |

### Design Rules

Every cleaning operation follows these rules:

1. **Non-destructive:** Operations never modify their original input data.
2. **Strict parameter validation:** Unknown parameters raise errors instead of being silently ignored.
3. **Transparent conversion:** Values that cannot be converted are counted and reported, never quietly dropped.
4. **Traceable execution:** Every operation produces a report describing what changed.

---

## 🚀 Quickstart

### Requirements

- Python 3.10+
- pip

### 1. Clone the Repository

```bash
git clone https://github.com/Ishraq225/DataTidy-Agent.git

cd DataTidy-Agent
```

### 2. Create a Virtual Environment

**Windows (PowerShell):**

```powershell
python -m venv .venv

.venv\Scripts\activate
```

**Linux / macOS:**

```bash
python -m venv .venv

source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Download Example Datasets

```bash
python scripts/download_datasets.py
```

Downloads three public datasets:

- Tips
- Penguins
- Titanic

### 5. Generate Messy Samples

```bash
python scripts/make_messy_samples.py
```

Creates intentionally corrupted versions of the datasets using a fixed random seed for reproducibility.

### 6. Run Tests

```bash
pytest
```

**Current result: 36 tests passed.**

---

## 📊 Using DataTidy

### 1. Profile a Messy Dataset

The profiler examines a CSV file and reports its structure, data types, missing values, duplicates, and potential quality issues.

```bash
python -m datatidy profile data/messy/tips_messy.csv
```

**Example output:**

```text
Dataset: 254 rows x 7 columns; 11 duplicate rows.

Columns:
- total_bill [str, text] missing 0.0%, 229 unique
- tip [str, text] missing 0.0%, 113 unique
- sex [str, text] missing 0.0%, 10 unique
- smoker [str, text] missing 0.0%, 2 unique
- day [str, text] missing 0.0%, 18 unique
- time [str, text] missing 0.0%, 2 unique
- size [int64, numeric] missing 0.0%

Detected issues:
- [high] duplicate_rows: 11 fully duplicated rows
- [high] total_bill: numbers stored as text
- [high] tip: 22 hidden missing tokens
- [high] tip: numbers stored as text
- [low] sex: whitespace inconsistencies
- [medium] sex: inconsistent categories
- [low] day: whitespace inconsistencies
- [medium] day: inconsistent categories
- [medium] size: numeric outliers
```

The profiler helps identify what needs attention before a cleaning plan is applied.

### 2. Apply a Cleaning Plan

A cleaning plan is a JSON list of steps.

Each step specifies:

- The operation to perform.
- The target column.
- Optional parameters.
- A reason explaining why the operation is needed.

**Example: `tips_plan.json`**

```json
[
  {
    "op": "strip_symbols",
    "column": "total_bill",
    "reason": "100% of values contain a currency symbol"
  },
  {
    "op": "standardize_missing",
    "column": "tip",
    "reason": "22 cells contain the hidden missing token N/A"
  },
  {
    "op": "cast_type",
    "column": "tip",
    "params": {
      "target": "float"
    },
    "reason": "Convert numeric text into floating-point values"
  },
  {
    "op": "fill_missing",
    "column": "tip",
    "params": {
      "strategy": "median"
    },
    "reason": "Use the median to handle missing tips"
  },
  {
    "op": "normalise_text",
    "column": "sex",
    "reason": "Standardise case and whitespace"
  },
  {
    "op": "drop_duplicates",
    "reason": "Remove duplicates after normalisation"
  }
]
```

### 3. Execute the Cleaning Plan

```bash
python -m datatidy apply data/messy/tips_messy.csv examples/plans/tips_plan.json -o cleaned.csv --log change_log.csv
```

**Example execution report:**

| Step | Operation | Column | Cells Changed |
|---:|---|---|---:|
| 1 | `strip_symbols` | total_bill | 254 |
| 2 | `standardize_missing` | tip | 22 |
| 3 | `cast_type` | tip | 0 |
| 4 | `fill_missing` | tip | 22 |
| 5 | `normalise_text` | sex | 235 |
| 6 | `normalise_text` | day | 240 |
| 7 | `drop_duplicates` | Dataset | 0 |

```text
Rows: 254 -> 243

Saved cleaned.csv and change_log.csv
```

The execution report shows which operations succeeded, how many cells changed, and what happened at each step.

**Failure handling:** If a step contains an unknown operation, invalid parameter, or missing column, it is logged with `status: failed` and skipped. The remaining valid steps can still execute, and the original dataset remains untouched.

---

## 📁 Datasets

DataTidy uses three public datasets downloaded through `scripts/download_datasets.py` from the `seaborn-data` repository.

The original datasets are Git-ignored. Check the original dataset terms before redistributing copies.

| Dataset | Original Rows | Injected Corruptions (Seed 42) |
|---|---:|---|
| Tips | 244 | Currency prefixes, `N/A` tokens, case/whitespace noise, duplicates |
| Penguins | 344 | Case/whitespace noise, four impossible body masses (×10), duplicates |
| Titanic | 891 | Currency prefixes on fares, `?` in age, case/whitespace noise, duplicates |

The generated messy datasets are reproducible:

```bash
python scripts/make_messy_samples.py
```

Using the same fixed seed (`42`) produces the same corrupted samples.

---

## 🏗️ Project Structure

```text
DataTidy-Agent/
│
├── datatidy/
│   ├── __init__.py
│   ├── __main__.py
│   ├── executor.py
│   ├── io.py
│   ├── operations.py
│   └── profiler.py
│
├── data/
│   └── (downloaded and generated datasets)
│
├── docs/
│   ├── datasets.md
│   └── week1_log.md
│
├── eval/
│
├── examples/
│   ├── plans/
│   │   ├── tips_plan.json
│   │   ├── penguins_plan.json
│   │   └── titanic_plan.json
│   └── output/
│
├── scripts/
│   ├── download_datasets.py
│   └── make_messy_samples.py
│
├── tests/
│   ├── test_executor.py
│   ├── test_operations.py
│   └── test_profiler.py
│
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

---

## 🧪 Testing

Run the complete test suite:

```bash
pytest
```

**Day 1 Test Results: 36 Passed**

The tests cover:

- Every cleaning operation, including failure cases.
- Verification that operations never modify their original input.
- All implemented profiler detectors.
- Executor logging and failure handling.
- End-to-end execution on generated messy datasets.
- Verification that detected issues are resolved by the cleaning workflow.

The goal is not simply to demonstrate that the code runs, but to verify that the cleaning operations behave as expected.

---

## 📚 What Day 1 Taught Me

### 1. Order Matters

Deduplicating before normalising text can leave duplicates behind.

For example, `Female`, `female`, and ` FEMALE ` may represent the same category but are not identical strings.

Normalising first and deduplicating last produces better results.

Day 2 will enforce this rule through code rather than relying only on the cleaning plan.

### 2. Silent Failure Is the Enemy

Early versions of the operations ignored unknown parameters.

This could hide mistakes in a cleaning plan.

The operations now raise errors when they encounter unsupported parameters. For example, `cast_type` refuses to convert `2.7` into `2` through silent truncation.

### 3. Flagged Does Not Mean Wrong

The profiler identifies very high Titanic fares as outliers.

However, some of these values are legitimate.

An outlier should be investigated, not automatically deleted or modified.

### 4. Mean vs. Median Is a Real Decision

For the Tips dataset, filling 22 missing tip values gives approximately:

- Median: `2.94`
- Mean: `3.01`

Both are mathematically valid, but the choice changes 22 values in the dataset.

A cleaning operation should have a reason behind it.

---

## ⚠️ Known Limitations (Day 1)

The current version focuses on the deterministic cleaning core.

Some planned features are not implemented yet:

- **No LLM planner:** Cleaning plans are currently written manually rather than proposed by a language model.
- **Outlier treatment:** Outliers are detected but not automatically corrected.
- **Date parsing:** Date formats are detected but not yet parsed or standardised.
- **Duplicate ambiguity:** Exact-duplicate removal can delete legitimately identical records.
- **Limited evaluation:** The project has been tested using automated tests and three example datasets, but a ground-truth benchmark is not available yet.

These limitations will be addressed in upcoming development stages.

---

## 🗺️ Roadmap

| Day | Planned Work | Status |
|---|---|---|
| Day 1 | Profiler, six operations, executor, change log, CLI, 36 tests, three datasets | ✅ Completed |
| Day 2 | Plan schema validation, LLM planner (Groq / Gemini / Ollama / OpenAI), retry and fallback, additional operations | 🔜 Planned |
| Day 3 | Ground-truth benchmark, baseline comparisons, evaluation metrics (including damage rate), Streamlit UI | 🔜 Planned |
| Day 4 | Failure analysis, final results, demo video, project write-up | 🔜 Planned |
| V2 | Multi-agent architecture: profiler, planner, verifier, critic; evaluated against the V1 benchmark | 🔮 Future |

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

**Built by [Ishraq Sajid](https://github.com/Ishraq225)**

*Building AI systems that are not just capable, but trustworthy.*
>>>>>>> 1cd048273e899c9cfef0050d522a8bb3c029c006
