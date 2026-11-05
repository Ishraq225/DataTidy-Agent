# DataTidy Agent 🧹

### An LLM-powered CSV data-cleaning agent built with safety, transparency, and reliability in mind.

DataTidy Agent helps identify and clean messy CSV datasets using a combination of data profiling, rule-based operations, and Large Language Models (LLMs).

Instead of allowing an AI model to generate and execute arbitrary Python code, DataTidy uses a controlled workflow: the LLM proposes a cleaning plan, the application validates it, and a deterministic executor applies approved operations.

**Core idea: AI suggests. Validation checks. Deterministic code executes.**

---

## 🚀 Project Overview

Real-world datasets are rarely perfect. They often contain:

- Missing values and inconsistent missing-value tokens.
- Duplicate records.
- Numbers stored as text.
- Inconsistent categories and unnecessary whitespace.
- Mixed date formats.
- Suspicious numerical outliers.

Manually identifying and fixing these problems can be time-consuming.

DataTidy Agent aims to automate this process without sacrificing control over the data.

### Key Features

- **Automated Data Profiling:** Inspects CSV files and identifies potential data-quality issues.
- **LLM-Based Planning:** Uses AI models to suggest cleaning operations based on profiling results.
- **Schema Validation:** Validates AI-generated plans before execution.
- **Safe Execution:** Uses a predefined library of approved cleaning operations.
- **Human Approval:** Allows users to review a cleaning plan before applying it.
- **Change Logging:** Records operations, changes, and conversion failures.
- **Multiple LLM Providers:** Supports Groq, Gemini, OpenAI, and Ollama.
- **Rule-Based Fallback:** Provides a deterministic fallback when the LLM produces an invalid plan.

---

## 🏗️ Architecture

DataTidy follows a structured pipeline:

```text
       Input CSV Dataset
               |
               v
        Data Profiler
               |
               v
      Dataset Issue Report
               |
               v
         LLM Planner
               |
               v
      Plan Validation
               |
               v
       Human Approval
               |
               v
     Safe Plan Executor
               |
         +-----+------+
         |            |
         v            v
   Cleaned CSV    Change Log
```

### How It Works

1. **Profile:** The profiler examines the dataset and identifies potential data-quality issues.
2. **Plan:** The LLM receives a profile summary and proposes suitable cleaning operations.
3. **Validate:** The generated plan is checked against a predefined schema, supported operations, parameters, and column names.
4. **Review:** The user can inspect the suggested operations and their explanations.
5. **Execute:** The executor applies validated operations using deterministic Python functions.
6. **Report:** The application produces a cleaned dataset and an execution log.

---

## 🛡️ Safety-First Design

Trustworthy data cleaning is more than simply making a dataset look clean.

DataTidy follows several safety principles:

| Principle | Implementation |
|---|---|
| No arbitrary AI code execution | The LLM can only select approved operations. |
| Plan before execution | Cleaning plans can be reviewed before execution. |
| Strict validation | Invalid operations and parameters are rejected. |
| Non-destructive operations | Cleaning operations work on copies of the input data. |
| Transparent failures | Unconvertible values are counted and reported. |
| Traceable changes | Each executed operation generates a report. |
| Controlled fallback | Invalid LLM plans can fall back to rule-based planning. |

The goal is to make every cleaning decision understandable and traceable.

---

## 🔍 Data Profiling

The profiler examines a dataset and identifies potential quality issues.

| Issue | Example |
|---|---|
| Duplicate rows | Repeated customer records |
| Missing values | Empty cells in important columns |
| Hidden missing tokens | `N/A`, `?`, `null`, `-` |
| Numbers stored as text | `"$1,200"` or `"12%"` |
| Mixed date formats | `"2024-01-05"` and `"Mar 5, 2024"` |
| Category inconsistencies | `Female`, `FEMALE`, `female` |
| Whitespace problems | `" Monday "` |
| Numeric outliers | Values outside an expected statistical range |

**Important:** An outlier is flagged for investigation, not automatically treated as an incorrect value.

---

## 🧰 Supported Cleaning Operations

DataTidy includes a predefined library of cleaning operations.

| Operation | Purpose |
|---|---|
| `drop_duplicates` | Remove duplicate records |
| `fill_missing` | Fill missing values using mean, median, mode, or a constant |
| `cast_type` | Convert values into supported data types |
| `normalise_text` | Trim whitespace, collapse spaces, and normalize case |
| `strip_symbols` | Remove currency symbols and other numeric formatting |
| `standardize_missing` | Convert tokens such as `N/A` and `?` into missing values |
| `parse_dates` | Convert date strings into date values |
| `map_values` | Standardize categories using explicit mappings |
| `clip_outliers` | Handle outliers using supported statistical methods |
| `drop_missing_rows` | Remove rows according to missing-value rules |
| `rename_column` | Rename dataset columns |
| `drop_column` | Remove selected columns |

Operations use strict parameter validation and report their changes instead of silently ignoring errors.

---

## 🤖 LLM Provider Support

DataTidy supports four LLM providers.

| Provider | Configuration | Cost |
|---|---|---|
| Groq | API key | Free tier available, rate limited |
| Google Gemini | API key | Free tier available, rate limited |
| OpenAI | API key | Paid usage |
| Ollama | Local installation | Runs locally |

Provider pricing, free-tier limits, and available model names can change.

### Configure Your Provider

Create a `.env` file in the project root using `.env.example` as a template.

Example:

```env
DATATIDY_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=
OPENAI_API_KEY=
OLLAMA_HOST=http://localhost:11434
```

For local inference with Ollama:

```bash
ollama pull llama3.2
```

Set:

```env
DATATIDY_PROVIDER=ollama
```

**Security:** Never commit your `.env` file or expose API keys in source code, screenshots, or public repositories.

### Privacy Considerations

The LLM planner uses a dataset profile summary and selected sample values rather than sending the entire CSV file.

For sensitive datasets, prefer a locally running provider such as Ollama and review what information is included in the profile before using any AI provider.

---

## ⚡ Getting Started

### Prerequisites

- Python 3.10 or later
- pip
- Git
- An API key for a supported cloud provider, or a local Ollama installation

### 1. Clone the Repository

```bash
git clone https://github.com/Ishraq225/DataTidy-Agent.git

cd DataTidy-Agent
```

### 2. Create a Virtual Environment

**Windows PowerShell:**

```powershell
python -m venv .venv

.venv\Scripts\Activate.ps1
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

This downloads the example Tips, Penguins, and Titanic datasets.

### 5. Generate Messy Datasets

```bash
python scripts/make_messy_samples.py
```

The script creates reproducible, intentionally corrupted dataset samples.

### 6. Run the Tests

```bash
pytest
```

---

## 💻 Using the CLI

DataTidy provides commands for profiling, planning, cleaning, and applying cleaning plans.

### 1. Profile a Dataset

```bash
python -m datatidy profile data/messy/tips_messy.csv
```

This displays dataset information and detected issues.

### 2. Generate an AI Cleaning Plan

```bash
python -m datatidy plan data/messy/tips_messy.csv --provider groq
```

This generates a proposed cleaning plan for review or saving.

### 3. Run the Cleaning Pipeline

```bash
python -m datatidy clean data/messy/tips_messy.csv --provider groq
```

This runs the planning and cleaning workflow, including the approval step.

### 4. Apply an Existing Cleaning Plan

```bash
python -m datatidy apply data/messy/tips_messy.csv examples/plans/tips_plan.json -o cleaned.csv --log change_log.csv
```

This executes a predefined JSON cleaning plan and saves the cleaned dataset and change log.

---

## 📂 Project Structure

```text
DataTidy-Agent/
│
├── datatidy/
│   ├── __init__.py
│   ├── __main__.py
│   ├── profiler.py
│   ├── operations.py
│   ├── executor.py
│   ├── io.py
│   ├── llm.py
│   ├── planner.py
│   ├── pipeline.py
│   └── schema.py
│
├── scripts/
│   ├── download_datasets.py
│   └── make_messy_samples.py
│
├── examples/
│   ├── plans/
│   └── output/
│
├── tests/
│
├── docs/
│   ├── datasets.md
│   ├── week1_log.md
│   └── week2_log.md
│
├── eval/
│
├── .env.example
├── .gitignore
├── requirements.txt
├── LICENSE
└── README.md
```

### Important Modules

| Module | Responsibility |
|---|---|
| `profiler.py` | Dataset inspection and issue detection |
| `operations.py` | Approved data-cleaning functions |
| `executor.py` | Executes cleaning plans and records changes |
| `llm.py` | Integrates supported LLM providers |
| `planner.py` | Generates, validates, and retries AI cleaning plans |
| `schema.py` | Validates cleaning plan structure |
| `pipeline.py` | Coordinates profiling, planning, approval, and execution |
| `__main__.py` | Command-line interface |

---

## 🧪 Testing and Reliability

Testing is an important part of DataTidy's development.

The test suite covers:

- Data profiling and issue detection.
- Individual cleaning operations.
- Invalid operation parameters.
- Schema validation.
- LLM planner behavior.
- Provider backend behavior.
- Pipeline execution.
- Failure handling and logging.

Run the complete suite with:

```bash
pytest
```

The project also includes example datasets and reproducible corruption scripts to support practical testing.

---

## 🗺️ Development Roadmap

| Stage | Focus | Status |
|---|---|---|
| Week 1 | Deterministic cleaning core, profiler, executor, CLI | Completed |
| Week 2 | LLM integrations, plan validation, retry and fallback | Completed |
| Week 3 | Evaluation benchmark, ground truth, metrics, Streamlit UI | Planned |
| Week 4 | Failure analysis, results, demo, and documentation | Planned |
| V2 | Multi-agent architecture with profiler, planner, verifier, and critic | Future |

The next major goal is to evaluate cleaning quality using measurable results, including a **damage rate** that tracks how often correct values are changed unnecessarily.

---

## 🔮 Future Improvements

- Ground-truth-based cleaning evaluation.
- Precision and recall for issue detection.
- Data damage-rate measurement.
- Interactive Streamlit interface.
- Multi-agent architecture.
- Improved cleaning-plan verification.
- More datasets and advanced data-quality checks.

---

## 🧠 Technologies Used

- **Language:** Python
- **Data Processing:** Pandas
- **AI / LLM Integration:** Groq, Google Gemini, OpenAI, Ollama
- **Validation:** Pydantic
- **Testing:** Pytest
- **Configuration:** Environment variables and `.env`
- **Version Control:** Git and GitHub

---

## 👩‍💻 Author

**Ishraq Sajid**

BS Artificial Intelligence Student | AI/ML Developer

- GitHub: [@Ishraq225](https://github.com/Ishraq225)
- Project Repository: [DataTidy-Agent](https://github.com/Ishraq225/DataTidy-Agent)
- LinkedIn: [Ishraq Sajid](https://www.linkedin.com/in/ishraq-sajid-44b372352/)

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

*DataTidy Agent is an ongoing learning and engineering project focused on building safer, more transparent, and measurable AI-powered data-cleaning systems.*
