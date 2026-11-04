**DataTidy Agent**

A trustworthy data-cleaning agent for messy CSV files, built around one idea: the gap between a system that works and a system you can trust.

Status: Day 1 of 4 (deterministic core). The profiler, safe operation library, executor and change log are done and tested. The LLM planner, evaluation benchmark and UI come next. See the roadmap.

**The idea**

Most "AI data cleaning" demos let a model write and run code on your data, then show it working once. DataTidy takes the opposite approach:

The model never runs code. It will only be allowed to choose from a small, fixed library of safe cleaning operations.
Plan, review, then execute. A cleaning plan is shown to the user as readable steps, each with a reason, before anything changes.
Everything is logged. Every step reports exactly how many cells or rows it changed, and warns when values could not be converted.
Success is measured, not claimed. Day 3 adds a benchmark with ground truth, including a damage rate: how often the cleaner breaks values that were already correct.

**Day 1 builds the part that has to be right regardless of which model is used later: the deterministic core.**

**What works today**
Component	File	What it does
Profiler	datatidy/profiler.py	Describes a dataset and flags likely problems (see below)
Operations	datatidy/operations.py	Six safe cleaning operations, each returning a precise change report
Executor	datatidy/executor.py	Runs a plan on a copy of the data, logs every step, skips failed steps
CSV I/O	datatidy/io.py	Loads CSVs without silently hiding N/A-style tokens
CLI	datatidy/__main__.py	profile and apply commandsF
What the profiler detects
Issue	Example
Duplicate rows	11 fully duplicated rows
Missing values	12% of age is empty
Hidden missing tokens	N/A, ?, null, - used instead of empty cells
Numbers stored as text	"$1,200", "12%", "(500)"
Dates stored as text	"2024-01-05", "Mar 5, 2024"
Mixed date formats	2024-01-05 and 03/04/2024 in one column
Inconsistent categories	Female, FEMALE, female  in one column
Stray whitespace	leading, trailing or doubled spaces
Numeric outliers	values outside 1.5 x IQR (a flag, not a verdict)

**Operations**
Operation	What it does	Safety behaviour
drop_duplicates	Removes duplicate rows (all columns or a subset)	Reports rows removed
fill_missing	Fills nulls with mean, median, mode or a constant	Refuses mean/median on non-numeric columns
cast_type	Converts to int, float, str, bool or category	Refuses to truncate 2.7 to 2; counts values that fail to convert
normalise_text	Trims, collapses spaces, lowercases	Leaves missing values untouched
strip_symbols	Turns "$1,200", "12%", "(500)" into numbers	1.2k suffixes are opt-in; unparseable values are counted, not hidden
standardize_missing	Turns N/A, ?, null into real missing values	Custom token list supported

Design rules that apply to every operation:

Operations never modify their input.
Unknown parameters raise an error instead of being silently ignored, so a misspelled or invented parameter fails loudly.
Anything that cannot be converted is counted and reported, never dropped quietly.
Quickstart

Requires Python 3.10+.

bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/download_datasets.py     # tips, penguins, titanic (public datasets)
python scripts/make_messy_samples.py    # seeded, reproducible corrupted versions

pytest                                  # 36 tests
1. Profile a messy file
bash
python -m datatidy profile data/messy/tips_messy.csv
text
Dataset: 254 rows x 7 columns; 11 duplicate rows.
Columns:
- total_bill [str, text] missing 0.0%, 229 unique, e.g. ['$16.99', '$10.34', '$21.01']
- tip [str, text] missing 0.0%, 113 unique, e.g. ['1.01', '1.66', '3.5']
- sex [str, text] missing 0.0%, 10 unique, e.g. ['Female', 'Male', '  Female ']
...
Detected issues:
- [high] (dataset): duplicate_rows - 11 fully duplicated row(s)
- [high] total_bill: numbers_stored_as_text - 100% of values look numeric
- [high] tip: hidden_missing_tokens - 22 cell(s) use tokens like ['N/A']
- [high] tip: numbers_stored_as_text - 100% of values look numeric
- [low] sex: whitespace - 30 cell(s) with leading/trailing/double spaces
- [medium] sex: inconsistent_categories - 2 group(s) differ only by case/spacing
...
2. Apply a cleaning plan

A plan is a JSON list of steps. Each step names an operation, a column, parameters and a reason:

json
[
  {"op": "strip_symbols", "column": "total_bill", "reason": "100% of values carry a '$' sign"},
  {"op": "standardize_missing", "column": "tip", "reason": "22 cells use the token 'N/A'"},
  {"op": "cast_type", "column": "tip", "params": {"target": "float"}, "reason": "numbers stored as text"},
  {"op": "fill_missing", "column": "tip", "params": {"strategy": "median"}, "reason": "tips are right-skewed"},
  {"op": "normalise_text", "column": "sex", "reason": "case and spacing variants"},
  {"op": "drop_duplicates", "reason": "run last: rows differing only by case or symbols become identical after normalising"}
]
bash
python -m datatidy apply data/messy/tips_messy.csv examples/plans/tips_plan.json \
    -o cleaned.csv --log change_log.csv
text
 step                  op     column status  cells_changed                                                       message
    1       strip_symbols total_bill     ok            254      Converted 'total_bill' to numbers (254 cell(s) changed).
    2 standardize_missing        tip     ok             22 Replaced 22 hidden-missing token(s) with real missing values.
    3           cast_type        tip     ok              0                          Converted 'tip' from str to float64.
    4        fill_missing        tip     ok             22       Filled 22 missing value(s) in 'tip' with median (2.94).
    5      normalise_text        sex     ok            235               Normalised text in 'sex' (235 cell(s) changed).
    6      normalise_text        day     ok            240               Normalised text in 'day' (240 cell(s) changed).
    7     drop_duplicates        NaN     ok              0                          Removed 11 duplicate row(s).

Rows: 254 -> 243. Saved cleaned.csv and change_log.csv

A step that fails (unknown operation, bad parameter, missing column) is logged with status: failed and skipped; the rest of the plan still runs and the original data is never modified.

Datasets

Three public datasets, downloaded by scripts/download_datasets.py from seaborn-data. They are git-ignored; check each dataset's terms before redistributing any copy.

Dataset	Rows	Injected corruptions (seed 42)
tips	244	$ prefix on bills, N/A in tips, case/space noise, duplicates
penguins	344	case/space noise, 4 impossible body masses (x10), duplicates
titanic	891	£ prefix on fares, ? in age, case/space noise, duplicates

Messy versions are reproducible: python scripts/make_messy_samples.py always produces the same files.

Project structure
text
datatidy/
  profiler.py        dataset profile and issue detection
  operations.py      the six safe operations
  executor.py        runs a plan and writes the change log
  io.py              CSV loading/saving
  __main__.py        command line interface
tests/               36 tests: operations, profiler, executor, end-to-end
scripts/             dataset download and messy-sample generator
examples/plans/      example cleaning plans (one per dataset)
examples/output/     their cleaned results and change logs
docs/                dataset notes and the Day 1 log
Testing
bash
pytest

The 36 tests cover each operation (including its failure cases), a check that no operation modifies its input, every profiler detector, the executor's log and failure handling, and an end-to-end run on a generated messy dataset that confirms the issues actually disappear.

What Day 1 taught me
Order matters. Deduplicating before normalising left 37 duplicates in Titanic, because rows that differ only by case, spacing or currency symbols are not yet identical. Plans should normalise first and deduplicate last. Day 2 enforces this in code, not only in a prompt.
Silent failure is the enemy. Early operations ignored unknown parameters, hiding typos. They now raise errors. cast_type refuses to turn 2.7 into 2.
Flagged is not wrong. The profiler marks very high Titanic fares as outliers, but they are real. Outlier treatment has to be a deliberate decision with a reason, never automatic.
Mean vs median is a real decision. On the tips data, filling 22 missing tips gives 2.94 (median) versus about 3.01 (mean). Small, but it changes 22 cells.
Known limitations (Day 1)
There is no LLM yet: plans are written by hand (or by you), not proposed by a model.
Outliers are detected but not treated.
Dates are detected but not parsed.
Exact-duplicate removal can delete legitimately identical records. The Day 3 damage metric is designed to catch this kind of harm.
Evaluated only by tests and three example datasets so far; there is no benchmark yet.

Roadmap
 Day 1 - profiler, six operations, executor, change log, CLI, 36 tests, three datasets
 Day 2 - plan schema validation, LLM planner (Groq / Gemini / Ollama / OpenAI), retry and fallback, remaining operations
 Day 3 - benchmark with ground truth, baselines, metrics (including damage rate), Streamlit UI
 Day 4 - failure analysis, results, demo video, write-up
 v2 - multi-agent upgrade (profiler / planner / verifier / critic), measured against the v1 benchmark
License

MIT
