# Week 1 log

## Done
- Repo structure, environment files, MIT licence
- Profiler with 10 issue types, JSON-safe output and a compact text rendering for the planner
- 6 safe operations, executor with change log, CLI
- 36 tests (operations, profiler, executor, end-to-end)
- 3 datasets + seeded messy versions; example plans for each

## Findings worth remembering (put these in the Week 2 planner prompt)
1. **Order matters.** Deduplicating before normalising left 37 duplicates in Titanic, because rows
   that differ only by case, spacing or currency symbols are not yet identical. Plans should
   normalise first, then deduplicate last.
2. **Silent failure is the enemy.** Operations that accepted unknown parameters hid typos; they now
   raise errors. `cast_type` refuses to truncate 2.7 to 2.
3. **The profiler over-flags outliers** on naturally skewed columns (Titanic fare). Treatment must be
   a deliberate planner decision with a reason, not automatic.
4. **Mean vs median is a real decision**, so the planner must justify the choice using skew.

## Week 2 TODO
- [ ] Pydantic schema for plans (allowed ops, parameter types per op)
- [ ] Planner prompt with the profile text, op catalogue, ordering rules (above)
- [ ] OpenAI + Ollama backends behind one interface; one validation retry
- [ ] Add `parse_dates`, `map_values`, `clip_outliers`, `drop_missing_rows`, `rename_column`
- [ ] Freeze the operation list at the end of Week 2
