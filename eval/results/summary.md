# DataTidy benchmark results

### Did it fix things?

| System | Runs | Start accuracy | Cell accuracy | Recoverable fixed | Duplicates removed |
|---|---|---|---|---|---|
| Do nothing | 30 | 53.4% | 53.4% | 0.0% | 0.0% |
| Rule-based | 30 | 53.4% | 97.8% | 100.0% | 77.2% |

### Did it break things?

| System | Runs | Damage (correct cells broken) | Rows lost | Columns lost | Missing cells filled |
|---|---|---|---|---|---|
| Do nothing | 30 | 0.0% | 0.0% | 0.0% | 0.0% |
| Rule-based | 30 | 0.0% | 0.0% | 0.0% | 24.9% |

### Fix rate by corruption type

| System | Runs | numbers as text | date formats | case / spacing | hidden missing | outliers |
|---|---|---|---|---|---|---|
| Do nothing | 30 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| Rule-based | 30 | 100.0% | 100.0% | 100.0% | 99.7% | 0.0% |

### Reliability and cost (LLM systems)

| System | Runs | Valid plan 1st try | Fallback used | Failed steps / run | Prompt tokens | Completion tokens | Latency |
|---|---|---|---|---|---|---|---|
| Do nothing | 30 | - | 0.0% | 0.0 | 0 | 0 | 0.0s |
| Rule-based | 30 | 100.0% | 0.0% | 0.0 | 0 | 0 | 0.0s |

Notes: accuracy counts lost rows/columns as wrong. Damage is measured only on cells that were correct before cleaning. Missing cells filled = imputation of cells whose true value is missing. Averages over all datasets and seeds.