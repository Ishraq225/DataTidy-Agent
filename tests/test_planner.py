import json

import pandas as pd

from datatidy.llm import FakeBackend
from datatidy.planner import extract_json, make_plan, rule_based_plan
from datatidy.profiler import profile_dataframe

DF = pd.DataFrame({
    "price": ["$10", "$20", "N/A", "$30", "$10"] * 4,
    "city": ["Karachi", "karachi ", "Lahore", "LAHORE", "Karachi"] * 4,
})

GOOD = {"plan": [
    {"op": "drop_duplicates", "column": None, "params": {}, "reason": "20 rows, many repeated"},
    {"op": "standardize_missing", "column": "price", "params": {}, "reason": "'N/A' tokens in price"},
    {"op": "strip_symbols", "column": "price", "params": {}, "reason": "$ signs"},
    {"op": "normalise_text", "column": "city", "params": {}, "reason": "case variants of the same city"},
]}


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here is the plan: {"plan": []} Hope that helps.') == {"plan": []}
    assert extract_json("[1, 2]") == [1, 2]
    try:
        extract_json("no json here")
        assert False
    except ValueError:
        pass


def test_valid_first_try_and_dedupe_moved_last():
    backend = FakeBackend([json.dumps(GOOD)])
    r = make_plan(DF, backend)
    assert r.source == "llm" and r.attempts == 1
    assert r.plan[-1]["op"] == "drop_duplicates"                   # was first, moved last
    assert any("moved" in w for w in r.warnings)


def test_bare_list_and_fenced_reply_accepted():
    backend = FakeBackend(["```json\n" + json.dumps(GOOD["plan"]) + "\n```"])
    assert make_plan(DF, backend).source == "llm"


def test_invalid_then_valid_retries_with_error_feedback():
    bad = json.dumps({"plan": [{"op": "make_pretty", "column": "price", "params": {}, "reason": "because"}]})
    backend = FakeBackend([bad, json.dumps(GOOD)])
    r = make_plan(DF, backend)
    assert r.source == "llm_retry" and r.attempts == 2
    assert "unknown operation 'make_pretty'" in backend.calls[1][1]   # errors were sent back
    assert r.prompt_tokens == 20


def test_unparseable_twice_falls_back_to_rules():
    backend = FakeBackend(["I cannot help", "still not json"])
    r = make_plan(DF, backend)
    assert r.source == "fallback" and r.plan and r.errors
    ops = [s["op"] for s in r.plan]
    assert ops.index("standardize_missing") < ops.index("strip_symbols") and ops[-1] == "drop_duplicates"


def test_fallback_can_be_disabled():
    r = make_plan(DF, FakeBackend(["x", "y"]), fallback=False)
    assert r.source == "failed" and r.plan == []


def test_hallucinated_column_is_rejected():
    bad = json.dumps({"plan": [{"op": "normalise_text", "column": "town", "params": {}, "reason": "variants"}]})
    r = make_plan(DF, FakeBackend([bad, bad]))
    assert r.source == "fallback" and "town" in " ".join(r.errors)


def test_prompt_contains_rules_and_profile_but_not_raw_rows():
    backend = FakeBackend([json.dumps(GOOD)])
    make_plan(DF, backend)
    system, user = backend.calls[0]
    assert "drop_duplicates ALWAYS LAST" in system and "standardize_missing" in system
    assert "PROFILE:" in user and "20 rows x 2 columns" in user


def test_rule_based_plan_is_valid_and_ordered():
    from datatidy.schema import validate_plan
    plan = rule_based_plan(profile_dataframe(DF))
    assert validate_plan(plan, list(DF.columns)).ok
    assert [s["op"] for s in plan][-1] == "drop_duplicates"
    assert any(s["op"] == "fill_missing" and s["column"] == "price" and s["params"]["strategy"] == "median"
               for s in plan)                               # numeric after strip_symbols -> median


def test_rule_based_plan_leaves_sparse_columns_alone():
    df = pd.DataFrame({"deck": [None] * 8 + ["A", "B"], "x": range(10)})
    plan = rule_based_plan(profile_dataframe(df))
    assert not any(s.get("column") == "deck" for s in plan)
