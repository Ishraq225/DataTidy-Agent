# DataTidy Agent

### A Trustworthy AI-Powered CSV Data Cleaning Agent

DataTidy Agent is an intelligent data-cleaning system designed to transform messy CSV datasets into clean, structured, and reliable data.

Unlike conventional AI agents that directly execute generated code, DataTidy follows a **Plan → Review → Execute** architecture. An LLM proposes a cleaning plan, the user reviews and approves it, and a deterministic execution engine applies changes using a fixed library of 12 safe operations.

Every modification is validated, tracked, and recorded in a detailed change log.

**Core Philosophy: The model never executes code. It only proposes actions.**

---

## Table of Contents

1. [Features](#features)
2. [System Architecture](#system-architecture)
3. [How It Works](#how-it-works)
4. [Supported Cleaning Operations](#supported-cleaning-operations)
5. [Technology Stack](#technology-stack)
6. [Installation](#installation)
7. [Usage](#usage)
8. [LLM Provider Configuration](#llm-provider-configuration)
9. [Web Interface](#web-interface)
10. [Evaluation and Benchmark](#evaluation-and-benchmark)
11. [Benchmark Results](#benchmark-results)
12. [Project Structure](#project-structure)
13. [Limitations](#limitations)
14. [Future Improvements](#future-improvements)
15. [License](#license)

---

## Features

- **AI-Powered Cleaning Plans:** Uses LLMs to analyze dataset profiles and suggest appropriate cleaning operations.
- **Safety-First Architecture:** The model cannot execute arbitrary code. It can only select from 12 predefined operations.
- **Human-in-the-Loop:** Review, edit, approve, or reject cleaning steps before execution.
- **Deterministic Execution:** Executes validated operations on a copy of the original dataset.
- **Automatic Issue Detection:** Identifies missing values, duplicates, inconsistent categories, formatting issues, and potential outliers.
- **Validation and Fallback:** Invalid LLM-generated plans are retried once before switching to a deterministic rule-based plan.
- **Detailed Change Logs:** Tracks modified cells, removed rows, failed conversions, and execution results.
- **Multiple LLM Providers:** Supports Groq, Gemini, Ollama, and OpenAI.
- **Interactive Web Interface:** Built with Streamlit for uploading, reviewing, cleaning, and downloading datasets.
- **Ground-Truth Evaluation:** Measures cleaning accuracy, recovery rates, and unintended data damage.

---

## System Architecture

DataTidy follows a structured pipeline that separates AI reasoning from actual data execution.

```text
              Messy CSV Dataset
                      |
                      v
               Dataset Profiler
              (Rule-Based Analysis)
                      |
                      v
                 LLM Planner
             (Cleaning Suggestions)
                      |
                      v
               Plan Validation
                      |
               +------+------+
               |             |
               v             v
           Valid Plan    Invalid Plan
               |          Retry Once
               |             |
               |       Rule-Based Fallback
               +------+------+
                      |
                      v
                Human Review
               (Edit / Approve)
                      |
                      v
            Deterministic Executor
                      |
               +------+------+
               |             |
               v             v
           Cleaned CSV   Change Log
```

## How It Works

1. **Profiling:** Analyzes the dataset without using an LLM and detects potential data-quality issues.
2. **Planning:** Sends the dataset profile to an LLM, which generates a structured JSON cleaning plan.
3. **Validation:** Validates operation names, parameters, and column references using Pydantic.
4. **Retry and Fallback:** Retries an invalid plan once, then uses a rule-based fallback if necessary.
5. **Human Review:** Allows users to inspect, modify, or reject proposed cleaning steps.
6. **Execution:** Applies approved operations deterministically on a copy of the dataset.
7. **Reporting:** Produces the cleaned CSV, execution report, and detailed change log.

---

## Supported Cleaning Operations

DataTidy provides 12 predefined operations:

| Operation | Description |
|---|---|
| `standardize_missing` | Converts tokens such as `N/A`, `?`, and `null` into missing values. |
| `strip_symbols` | Removes currency symbols, percentages, and numeric formatting. |
| `parse_dates` | Parses mixed-format date strings. |
| `cast_type` | Converts columns into specified data types. |
| `normalise_text` | Trims whitespace, collapses spaces, and normalizes text case. |
| `map_values` | Standardizes inconsistent categorical values. |
| `rename_column` | Renames dataset columns safely. |
| `drop_duplicates` | Removes duplicate records. |
| `fill_missing` | Handles missing values using mean, median, mode, or constants. |
| `clip_outliers` | Handles outliers using IQR or Z-score methods. |
| `drop_missing_rows` | Removes rows with missing values according to selected rules. |
| `drop_column` | Removes unnecessary or unusable columns. |

### Safety Guarantees

- Original input data is never modified.
- Unknown parameters raise validation errors.
- Failed conversions are counted and reported.
- Every execution step is recorded.

---

## Technology Stack

| Category | Technologies |
|---|---|
| Programming Language | Python |
| Data Processing | Pandas, NumPy |
| AI Integration | Groq, Gemini, OpenAI, Ollama |
| Data Validation | Pydantic |
| Web Interface | Streamlit |
| Testing | Pytest |
| Data Visualization | Matplotlib |
| Version Control | Git and GitHub |

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Ishraq225/DataTidy-Agent.git
cd DataTidy-Agent
```

### 2. Create a Virtual Environment

**Windows:**

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
python -m pip install -r requirements.txt
```

### 4. Download Sample Datasets

```bash
python scripts/download_datasets.py
```

### 5. Generate Messy Sample Datasets

```bash
python scripts/make_messy_samples.py
```

### 6. Run Tests

```bash
pytest
```

The project currently includes 113 tests and does not require an API key to run the test suite.

---

## Usage

### 1. Profile a Dataset

Analyze a CSV file and identify potential data-quality issues:

```bash
python -m datatidy profile data/messy/tips_messy.csv
```

### 2. Generate a Cleaning Plan

Generate and save a proposed cleaning plan:

```bash
python -m datatidy plan data/messy/tips_messy.csv --provider groq
```

### 3. Clean a Dataset

Generate a plan, request user approval, and execute the cleaning operations:

```bash
python -m datatidy clean data/messy/tips_messy.csv --provider groq
```

### 4. Apply a Manual Cleaning Plan

Execute a predefined JSON cleaning plan without using an LLM:

```bash
python -m datatidy apply data/messy/tips_messy.csv examples/plans/tips_plan.json -o cleaned.csv --log change_log.csv
```

### 5. Launch the Web Application

```bash
streamlit run app.py
```

---

## LLM Provider Configuration

DataTidy supports multiple LLM providers through a unified OpenAI-compatible client.

| Provider | Configuration |
|---|---|
| Groq | Free tier with rate limits |
| Gemini | Free tier with rate limits |
| Ollama | Local model execution |
| OpenAI | Paid API access |

### Configure Environment Variables

Create a `.env` file using the provided example:

```bash
cp .env.example .env
```

For Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Example configuration:

```env
DATATIDY_PROVIDER=groq
GROQ_API_KEY=your_api_key_here
```

Never commit your `.env` file or expose API keys publicly.

### Privacy

The LLM receives a dataset profile containing column statistics and selected sample values rather than the entire CSV file.

For sensitive datasets, Ollama can be used for local model execution.

---

## Web Interface

The Streamlit interface provides an interactive environment for dataset cleaning.

Users can:

- Upload CSV datasets or select sample datasets.
- Inspect detected data-quality issues.
- Generate AI-powered cleaning plans.
- Review and edit proposed operations.
- Approve and execute cleaning steps.
- Compare before-and-after dataset metrics.
- Inspect execution logs.
- Download cleaned CSV files, change logs, and cleaning plans.

A rule-based cleaning option is also available without requiring an API key.

---

## Evaluation and Benchmark

DataTidy includes a ground-truth evaluation framework designed to measure both cleaning effectiveness and unintended data damage.

### Benchmark Dataset

The benchmark contains 10 public datasets with three random seeds each, producing 30 evaluation cases.

Datasets include:

- Tips
- Penguins
- Titanic
- MPG
- Planets
- Health Expenditure
- Exercise
- Diamonds
- Dow Jones
- Sea Ice

### Simulated Data Corruptions

| Corruption | Type | Example |
|---|---|---|
| Numbers stored as text | Recoverable | `$1,234.5`, `12.5%` |
| Mixed date formats | Recoverable | `2024-03-05`, `05 Mar 2024` |
| Case and spacing noise | Recoverable | `FEMALE`, ` female` |
| Duplicate rows | Recoverable | Repeated records |
| Hidden missing tokens | Lossy | `N/A`, `?`, `-` |
| Outliers | Lossy | Values multiplied by 10 |

Recoverable corruptions can be restored to their original values. Lossy corruptions destroy information, so their handling is evaluated differently.

### Systems Compared

1. **Do Nothing:** Uses the original messy dataset without cleaning.
2. **Rule-Based:** Generates a cleaning plan using profiler results without an LLM.
3. **Single Prompt:** Uses a basic LLM prompt without validation, retries, fallback, or safety ordering.
4. **DataTidy Agent:** Uses validation, retry, rule-based fallback, and execution-order safeguards.

### Evaluation Metrics

- Cell Accuracy
- Damage Rate
- Fix Rate by Corruption Type
- Duplicate Removal Rate
- Rows and Columns Lost
- Missing Cells Filled
- LLM Reliability
- Token Usage and Latency

---

## Benchmark Results

The following results represent averages across 30 benchmark cases per system.

| System | Cell Accuracy | Recoverable Fixed | Duplicates Removed | Damage Rate |
|---|---:|---:|---:|---:|
| Do Nothing | 53.4% | 0.0% | 0.0% | 0.0% |
| Rule-Based | 97.8% | 100.0% | 77.2% | 0.0% |
| Single Prompt | Pending | Pending | Pending | Pending |
| DataTidy Agent | Pending | Pending | Pending | Pending |

### Key Observations

- The rule-based baseline achieved 97.8% cell accuracy on the current benchmark.
- All recoverable corruptions were successfully fixed by the rule-based system.
- Duplicate removal reached 77.2%, limited by exact matching.
- The system deliberately avoids automatically modifying flagged outliers because they may represent legitimate observations.
- LLM-based benchmark results are pending.

The rule-based baseline performs particularly well because the injected corruption types overlap with the issues the profiler was designed to detect. Therefore, these results should not be interpreted as proof that rule-based cleaning solves every data-quality problem.

---

## Project Structure

```text
DataTidy-Agent/
│
├── datatidy/
│   ├── profiler.py
│   ├── operations.py
│   ├── schema.py
│   ├── llm.py
│   ├── planner.py
│   ├── executor.py
│   ├── pipeline.py
│   ├── io.py
│   └── __main__.py
│
├── eval/
│   ├── datasets.py
│   ├── corrupt.py
│   ├── metrics.py
│   ├── baselines.py
│   ├── run_eval.py
│   ├── report.py
│   └── results/
│
├── tests/
│
├── scripts/
│   ├── download_datasets.py
│   └── make_messy_samples.py
│
├── examples/
│   └── plans/
│
├── docs/
│
├── data/
│
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Limitations

- LLM-based benchmark results are still pending.
- Only exact duplicate matching is currently supported.
- The benchmark corruption types overlap with profiler detection capabilities.
- The benchmark currently uses 10 datasets and three random seeds.
- CSV files are currently the only supported input format.
- Semantic data validation, such as identifying impossible ages or logically inconsistent records, is not currently implemented.

---

## Future Improvements

- Complete the full benchmark evaluation for LLM-based systems.
- Analyze and compare LLM-generated cleaning plans.
- Introduce a multi-agent architecture with specialized profiler, planner, critic, and verifier agents.
- Explore fuzzy duplicate detection.
- Introduce semantic data validation.
- Expand support for additional data formats.
- Improve evaluation across more diverse datasets.

---

## License

This project is licensed under the MIT License.

---

## Author

**Ishraq Sajid**

BS Artificial Intelligence Student | AI/ML Developer

- GitHub: [Ishraq225](https://github.com/Ishraq225)
- LinkedIn: [Ishraq Sajid](https://www.linkedin.com/in/ishraq-sajid-44b372352/)

---

*DataTidy Agent: Making data cleaning safer, measurable, and more reliable.*
