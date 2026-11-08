from pathlib import Path

import pandas as pd
import pytest

from datatidy.pipeline import plan_to_table, table_to_plan

PLAN = [
    {"op": "strip_symbols", "column": "price", "params": {}, "reason": "currency symbols"},
    {"op": "fill_missing", "column": "price", "params": {"strategy": "median"}, "reason": "skewed"},
    {"op": "drop_duplicates", "column": None, "params": {}, "reason": "repeats"},
]


def test_plan_table_round_trip():
    table = plan_to_table(PLAN)
    assert list(table.columns) == ["apply", "op", "column", "params", "reason"] and table["apply"].all()
    steps, errors = table_to_plan(table)
    assert errors == [] and steps == PLAN


def test_unticked_rows_are_left_out_and_edited_params_are_used():
    table = plan_to_table(PLAN)
    table.loc[0, "apply"] = False
    table.loc[1, "params"] = '{"strategy": "mean"}'
    steps, errors = table_to_plan(table)
    assert errors == [] and [s["op"] for s in steps] == ["fill_missing", "drop_duplicates"]
    assert steps[0]["params"] == {"strategy": "mean"}


def test_invalid_json_params_are_reported_not_crashed():
    table = plan_to_table(PLAN)
    table.loc[1, "params"] = "{strategy: mean"
    steps, errors = table_to_plan(table)
    assert len(errors) == 1 and "not valid JSON" in errors[0]
    table.loc[1, "params"] = "[1, 2]"
    assert "JSON object" in table_to_plan(table)[1][0]


def test_empty_plan_table():
    assert plan_to_table([]).empty and table_to_plan(plan_to_table([])) == ([], [])


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not (ROOT / "data" / "messy" / "tips_messy.csv").exists(), reason="run scripts first")
def test_streamlit_app_runs_and_cleans_a_sample():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception and at.info                      # "Upload a CSV or pick a sample"
    at.selectbox(key="sample").select("tips_messy.csv").run()
    assert not at.exception
    at.button(key="propose").click().run()
    assert not at.exception, at.exception
    assert at.session_state["planner"].source == "rules" and not at.session_state["plan_table"].empty
    at.button(key="run").click().run()
    assert not at.exception, at.exception
    cleaned, log, steps = at.session_state["result"]
    assert all(e["status"] == "ok" for e in log) and len(cleaned) < 255
