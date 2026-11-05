import json

import pandas as pd

from datatidy.llm import FakeBackend
from datatidy.pipeline import clean_dataframe, format_plan

DF = pd.DataFrame({
    "price": ["$10", "$20", "N/A", "$30", "$10"] * 4,
    "city": ["Karachi", "karachi ", "Lahore", "LAHORE", "Karachi"] * 4,
})
PLAN = {"plan": [
    {"op": "standardize_missing", "column": "price", "params": {}, "reason": "N/A tokens in price"},
    {"op": "strip_symbols", "column": "price", "params": {}, "reason": "$ signs in price"},
    {"op": "fill_missing", "column": "price", "params": {"strategy": "median"}, "reason": "4 missing values"},
    {"op": "normalise_text", "column": "city", "params": {}, "reason": "case variants"},
    {"op": "drop_duplicates", "column": None, "params": {}, "reason": "repeated rows"},
]}


def test_full_pipeline_with_auto_approval():
    r = clean_dataframe(DF, FakeBackend([json.dumps(PLAN)]))
    assert r.approved and r.planner.source == "llm"
    assert all(e["status"] == "ok" for e in r.log)
    assert len(r.profile_after["issues"]) < len(r.profile_before["issues"])
    assert set(r.cleaned["city"]) == {"karachi", "lahore"}
    assert r.cleaned["price"].dtype == "float64" and not r.cleaned["price"].isna().any()


def test_rejected_plan_changes_nothing():
    r = clean_dataframe(DF, FakeBackend([json.dumps(PLAN)]), approve=lambda plan: False)
    assert not r.approved and r.cleaned is None and r.log == []


def test_user_can_edit_the_plan_before_running():
    def untick_fill(plan):
        return [s for s in plan if s["op"] != "fill_missing"]
    r = clean_dataframe(DF, FakeBackend([json.dumps(PLAN)]), approve=untick_fill)
    assert "fill_missing" not in [e["op"] for e in r.log]
    assert r.cleaned["price"].isna().any()                         # the missing values stay missing


def test_source_dataframe_is_never_modified():
    before = DF.copy(deep=True)
    clean_dataframe(DF, FakeBackend([json.dumps(PLAN)]))
    pd.testing.assert_frame_equal(DF, before)


def test_pipeline_survives_garbage_llm_output():
    r = clean_dataframe(DF, FakeBackend(["nonsense", "more nonsense"]))
    assert r.planner.source == "fallback" and r.approved
    assert len(r.profile_after["issues"]) < len(r.profile_before["issues"])


def test_format_plan_readable():
    text = format_plan(PLAN["plan"])
    assert "1. standardize_missing on 'price'" in text and "why:" in text
    assert "empty plan" in format_plan([])
