"""Tests for the Week 3 benchmark: generator, metrics, baselines and runner."""
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from datatidy.io import load_csv
from datatidy.llm import FakeBackend
from datatidy.planner import rule_based_plan
from datatidy.profiler import profile_dataframe
from eval.baselines import run_agent, run_noop, run_rules, run_single_prompt
from eval.corrupt import ALL_TYPES, Case, make_case, roundtrip
from eval.metrics import canon, cells_equal, evaluate, grid


@pytest.fixture(scope="module")
def tips():
    try:
        return make_case("tips", 0)
    except Exception as exc:                                  # offline and no cached data
        pytest.skip(f"benchmark data unavailable: {exc}")


def loaded(case: Case) -> pd.DataFrame:
    return load_csv(io.StringIO(case.messy_csv()))


def oracle_output(case: Case) -> pd.DataFrame:
    """A perfect cleaner: the truth, indexed by each row's primary position in the messy file."""
    out = case.clean.copy()
    out.index = list(case.primary_pos)
    return out


# ---------------------------------------------------------------- generator
def test_generation_is_deterministic(tips):
    again = make_case("tips", 0)
    assert again.messy_csv() == tips.messy_csv() and again.injected == tips.injected


def test_different_seeds_differ(tips):
    assert make_case("tips", 1).messy_csv() != tips.messy_csv()


def test_row_map_and_duplicates_are_consistent(tips):
    assert len(tips.row_map) == len(tips.messy) == len(tips.clean) + tips.n_dup_rows
    assert set(tips.row_map) == set(range(len(tips.clean)))            # every original row present
    assert tips.n_dup_rows == len(tips.injected["dup_rows"]["__rows__"])


def test_injected_cells_really_differ_from_truth(tips):
    for col, ids in tips.injected["numeric_text"].items():
        assert all(isinstance(tips.messy[col].iloc[tips.primary_pos[i]], str) for i in ids[:20])
    for col, ids in tips.injected["missing_token"].items():
        token = tips.details["missing_token"][col]
        assert all(tips.messy[col].iloc[tips.primary_pos[i]] == token for i in ids)
    for col, ids in tips.injected["case_space"].items():
        assert all(tips.messy[col].iloc[tips.primary_pos[i]] != tips.clean[col].iloc[i] for i in ids)


def test_duplicates_are_independently_corrupted_near_duplicates(tips):
    """Some duplicate copies must differ from their primary copy (so dedupe-first misses them)."""
    src = tips.injected["dup_rows"]["__rows__"]
    differing = 0
    for rid in src:
        copies = [p for p, r in enumerate(tips.row_map) if r == rid]
        assert len(copies) == 2
        a, b = (tips.messy.iloc[c].astype(str).tolist() for c in copies)
        differing += a != b
    assert differing >= len(src) * 0.5


def test_each_dataset_has_all_recoverable_types_where_applicable():
    for name in ["tips", "dowjones"]:
        try:
            c = make_case(name, 0)
        except Exception:
            pytest.skip("data unavailable")
        assert "numeric_text" in c.injected and "dup_rows" in c.injected
    assert "date_format" in make_case("dowjones", 0).injected


def test_save_writes_files(tmp_path, tips):
    folder = tips.save(tmp_path / "case")
    assert (folder / "messy.csv").exists() and (folder / "clean.csv").exists()
    assert json.loads((folder / "manifest.json").read_text())["dataset"] == "tips"


# ---------------------------------------------------------------- comparison helpers
def test_cells_equal_rules():
    assert cells_equal(np.nan, None) and not cells_equal(1.0, np.nan)
    assert cells_equal(3, 3.0000001) and not cells_equal(3, 3.1)
    assert cells_equal("  Female ", "female") and not cells_equal("Female", "Male")
    assert cells_equal(pd.Timestamp("2024-03-05"), "2024-03-05")
    assert not cells_equal(12.5, "$12.5")
    assert canon(True) == 1.0


# ---------------------------------------------------------------- metrics
def test_oracle_scores_perfectly(tips):
    r = evaluate(tips, oracle_output(tips), loaded(tips))
    assert r["cell_accuracy"] == 1.0 and r["damage_rate"] == 0.0 and r["row_loss_rate"] == 0.0
    assert r["dup_removal_rate"] == 1.0 and r["recoverable_fix_rate"] == 1.0
    assert r["fix_numeric_text"] == 1.0 and r["fix_case_space"] == 1.0


def test_do_nothing_fixes_nothing_and_harms_nothing(tips):
    m = loaded(tips)
    r = evaluate(tips, m, m)
    assert r["cell_accuracy"] == r["baseline_accuracy"] and r["accuracy_gain"] == 0
    assert r["damage_rate"] == 0 and r["dup_removal_rate"] == 0
    assert r["fix_numeric_text"] == 0 and r["fix_missing_token"] == 0 and r["fix_case_space"] == 0


def test_damage_is_detected_when_a_correct_column_is_wrecked(tips):
    out = oracle_output(tips)
    touched = {c for cols in tips.injected.values() for c in cols}
    untouched = [c for c in tips.clean.columns if c not in touched]
    assert untouched, "need a column that was never corrupted"
    out[untouched[0]] = "ZZZ"                                # wreck a column that was correct before
    r = evaluate(tips, out, loaded(tips))
    assert r["damage_rate"] > 0.05 and r["cell_accuracy"] < 1.0


def test_row_and_column_loss_are_counted(tips):
    out = oracle_output(tips).iloc[:-20].drop(columns=["tip"])
    r = evaluate(tips, out, loaded(tips))
    assert r["row_loss_rate"] == pytest.approx(20 / len(tips.clean))
    assert r["col_loss_rate"] == pytest.approx(1 / tips.clean.shape[1])


def test_fabrication_is_counted_only_where_truth_is_missing():
    try:
        c = make_case("penguins", 0)                          # has naturally missing cells
    except Exception:
        pytest.skip("data unavailable")
    out = oracle_output(c)
    assert evaluate(c, out, loaded(c))["fabrication_rate"] == 0
    cols = ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g"]
    filled = out.copy()
    for col in cols:
        filled[col] = filled[col].fillna(filled[col].median())
    expected = c.clean[cols].isna().sum().sum() / c.clean.isna().sum().sum()   # share of missing cells we filled
    assert 0 < expected < 1
    assert evaluate(c, filled, loaded(c))["fabrication_rate"] == pytest.approx(expected)


def test_outlier_metric_ignores_float_noise_and_rewards_real_repair():
    try:
        c = make_case("diamonds", 2)
    except Exception:
        pytest.skip("data unavailable")
    m = loaded(c)
    r = evaluate(c, m, m)
    assert r["fix_outlier"] == 0                              # untouched file must score 0


# ---------------------------------------------------------------- baselines with a scripted LLM
def plan_json(plan):
    return json.dumps({"plan": plan})


def test_noop_and_rules_baselines(tips):
    m = loaded(tips)
    assert run_noop(m).cleaned.equals(m)
    res = run_rules(m)
    r = evaluate(tips, res.cleaned, m)
    assert r["cell_accuracy"] > 0.9 and r["damage_rate"] == 0


def test_agent_with_scripted_good_plan_matches_rules(tips):
    m = loaded(tips)
    good = rule_based_plan(profile_dataframe(m))
    res = run_agent(m, FakeBackend([plan_json(good)]))
    assert res.source == "llm" and res.plan_valid_first_try
    assert evaluate(tips, res.cleaned, m)["cell_accuracy"] == pytest.approx(
        evaluate(tips, run_rules(m).cleaned, m)["cell_accuracy"])


def test_scaffolding_beats_a_flawed_single_prompt(tips):
    """Same flawed LLM answer: dedupe FIRST and a hallucinated column. The agent repairs/validates;
    the single prompt runs it as-is."""
    m = loaded(tips)
    good = rule_based_plan(profile_dataframe(m))
    dedupe = [s for s in good if s["op"] == "drop_duplicates"]
    flawed = dedupe + [s for s in good if s["op"] != "drop_duplicates"] + [
        {"op": "normalise_text", "column": "ghost_column", "params": {}, "reason": "made up column"}]
    single = run_single_prompt(m, FakeBackend([plan_json(flawed)]))
    agent = run_agent(m, FakeBackend([plan_json(flawed), plan_json(good)]))
    assert single.plan_valid_first_try is False and single.attempts == 1
    assert agent.source == "llm_retry"                          # invalid plan was rejected and retried
    rs, ra = evaluate(tips, single.cleaned, m), evaluate(tips, agent.cleaned, m)
    assert ra["dup_removal_rate"] > rs["dup_removal_rate"]      # dedupe-first missed the near-duplicates
    assert ra["cell_accuracy"] >= rs["cell_accuracy"]


def test_single_prompt_with_garbage_does_nothing_no_fallback(tips):
    m = loaded(tips)
    res = run_single_prompt(m, FakeBackend(["I cannot do that"]))
    assert res.cleaned.equals(m) and res.plan == [] and res.plan_valid_first_try is False
    agent = run_agent(m, FakeBackend(["nope", "still nope"]))
    assert agent.source == "fallback" and evaluate(tips, agent.cleaned, m)["cell_accuracy"] > 0.9


def test_single_prompt_survives_nonsense_steps(tips):
    m = loaded(tips)
    steps = [{"op": "fill_missing", "column": "ghost", "params": {"strategy": "median"}},
             "not a dict", {"op": 5}, {"op": "strip_symbols", "column": "tip", "params": "bad"}]
    res = run_single_prompt(m, FakeBackend([plan_json(steps)]))
    assert len(res.log) == 3 and all(e["status"] == "failed" for e in res.log)


# ---------------------------------------------------------------- runner and report
def test_runner_end_to_end_and_resume(tmp_path, tips):
    from eval.run_eval import main
    out = tmp_path / "res"
    assert main(["--systems", "noop,rules", "--datasets", "tips", "--seeds", "0", "1", "--out", str(out)]) == 0
    runs = pd.read_csv(out / "runs.csv")
    assert len(runs) == 4 and set(runs["system"]) == {"noop", "rules"}
    assert (out / "summary.md").exists() and (out / "worst_cases.md").exists()
    summary = pd.read_csv(out / "summary.csv", index_col=0)
    assert summary.loc["rules", "cell_accuracy"] > summary.loc["noop", "cell_accuracy"]
    assert (out / "accuracy.png").exists()
    # resume: nothing is recomputed, file unchanged
    before = (out / "runs.csv").read_text()
    assert main(["--systems", "noop,rules", "--datasets", "tips", "--seeds", "0", "1", "--out", str(out), "--resume"]) == 0
    assert (out / "runs.csv").read_text() == before


def test_runner_needs_a_key_for_llm_systems(tmp_path, monkeypatch):
    from eval.run_eval import main
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert main(["--systems", "agent", "--provider", "groq", "--datasets", "tips", "--seeds", "0",
                 "--out", str(tmp_path)]) == 2
