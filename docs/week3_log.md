# Week 3 log

## Done
- Corruption generator with ground truth: 6 corruption types, 10 datasets, seeded, manifest of every injected cell
- Metrics: cell accuracy, damage, fabrication, row/column loss, per-type fix rates, duplicate removal
- Baselines: do-nothing, rule-based, single-prompt (no scaffolding), agent
- Runner with resume, per-run plans, summary tables, three charts, worst-cases report
- Streamlit UI with plan review (untick steps, edit JSON params), before/after metrics, downloads
- 113 tests (was 83 at the start of the week), including scripted fake-LLM comparisons and an AppTest of the UI

## Bugs found by the benchmark
1. Profiler flagged "30 min" as numbers-stored-as-text (exercise data) -> 24% damage. Fixed + regression test.
2. Dedupe after fill deleted distinct rows (planets, titanic). New rule: normalise, dedupe, fill (`place_dedupe`).
3. Outlier metric fooled by float noise. Now requires at least half the error removed.
4. Duplicates were exact copies, so the order problem was invisible. Now independently corrupted.
5. Evaluation used the earliest copy of a row, which could be an uncorrupted duplicate. Now prefers the primary copy.

## Not yet done
- Real LLM runs (needs your key): `python -m eval.run_eval --systems noop,rules,single,agent --provider groq --seeds 0 --sleep 20`
- Fuzzy duplicate matching (out of scope for v1)

## Week 4 TODO
- [ ] Run single + agent on all 10 datasets x 3 seeds (use --resume across days)
- [ ] Read `worst_cases.md` and the saved plans; write 2+ failure cases with explanations
- [ ] Fill the README results table; add the charts
- [ ] Optional: local Ollama run for a cloud-vs-local comparison
- [ ] Demo video (30-60 s), LinkedIn post, final write-up
