# Week 2 log

## Done
- 6 more operations (12 total, now frozen): parse_dates, map_values, clip_outliers, drop_missing_rows, rename_column, drop_column
- Pydantic schema: per-operation parameter models, unknown parameters rejected, column tracking through renames/drops, all errors collected in one pass
- One LLM backend for Groq, OpenAI, Gemini and Ollama (OpenAI-compatible API) with token + latency tracking
- Planner: system prompt with operation catalogue and rules, JSON extraction, validation, one retry with error feedback, rule-based fallback
- `plan` and `clean` CLI commands with an approval step
- 81 tests, including a mock HTTP server that checks the real OpenAI SDK request format

## Design decisions
1. **Plain SDK instead of LangChain.** One small dependency, and full control over prompts and retries. A LangChain version could be a v2 comparison.
2. **Fallback = baseline.** The rule-based plan (profiler flags only) is also the Week 3 rule-based baseline.
3. **Order rule enforced in code**, not only in the prompt (`move_dedupe_last`).
4. **Token usage and latency are logged** on every call, for the Week 3 cost metric.

## Not yet verified
- Real calls to Groq / OpenAI / Gemini / Ollama (needs your key). First thing to do: run `python -m datatidy plan data/messy/tips_messy.csv --provider groq` and read the plan critically.

## Week 3 TODO
- [ ] Corruption generator with ground truth (8-10 datasets)
- [ ] Baselines: rule-based (exists) and single-prompt
- [ ] Metrics: cell accuracy, issue fix rate, damage rate, plan validity, cost, latency
- [ ] Streamlit UI with plan review checkboxes
