from pathlib import Path

import pandas as pd
import pytest

from datatidy import load_csv, log_to_dataframe, profile_dataframe, run_plan


def test_plan_runs_in_order_and_logs_every_step():
    df = pd.DataFrame({"p": ["$1", "$2", "N/A", "$2"], "c": [" A", "a ", "b", "a "]})
    plan = [
        {"op": "standardize_missing", "column": "p", "reason": "N/A is a hidden missing value"},
        {"op": "strip_symbols", "column": "p", "reason": "currency text"},
        {"op": "fill_missing", "column": "p", "params": {"strategy": "median"}, "reason": "skewed"},
        {"op": "normalise_text", "column": "c", "reason": "case variants"},
        {"op": "drop_duplicates", "reason": "exact repeats"},
    ]
    out, log = run_plan(df, plan)
    assert [e["status"] for e in log] == ["ok"] * 5
    assert out["p"].tolist() == [1.0, 2.0, 2.0]
    assert out["c"].tolist() == ["a", "a", "b"]
    assert log[-1]["rows_before"] > log[-1]["rows_after"]
    table = log_to_dataframe(log)
    assert list(table["step"]) == [1, 2, 3, 4, 5]


def test_failed_step_is_logged_and_skipped():
    df = pd.DataFrame({"x": [1, 2]})
    plan = [
        {"op": "delete_everything", "column": "x"},
        {"op": "fill_missing", "column": "nope"},
        {"op": "fill_missing", "column": "x", "params": {"bogus": 1}},
        {"op": "drop_duplicates"},
    ]
    out, log = run_plan(df, plan)
    assert [e["status"] for e in log] == ["failed", "failed", "failed", "ok"]
    assert "Invalid parameters" in log[2]["message"]
    assert log[0]["status"] == "failed" and "Unknown operation" in log[0]["message"]
    assert len(out) == 2


def test_stop_on_error():
    df = pd.DataFrame({"x": [1, 2]})
    _, log = run_plan(df, [{"op": "nope"}, {"op": "drop_duplicates"}], stop_on_error=True)
    assert len(log) == 1


def test_input_dataframe_is_untouched():
    df = pd.DataFrame({"c": [" A", "a "]})
    before = df.copy(deep=True)
    run_plan(df, [{"op": "normalise_text", "column": "c"}])
    pd.testing.assert_frame_equal(df, before)


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / 'data' / 'raw' / 'tips.csv').exists(),
                    reason='run scripts/download_datasets.py first')
def test_end_to_end_on_messy_tips(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import make_messy_samples as m
    m.MESSY = tmp_path
    m.main(seed=42)
    df = load_csv(tmp_path / "tips_messy.csv")
    before = profile_dataframe(df)
    plan = [
        {"op": "drop_duplicates"},
        {"op": "strip_symbols", "column": "total_bill"},
        {"op": "standardize_missing", "column": "tip"},
        {"op": "cast_type", "column": "tip", "params": {"target": "float"}},
        {"op": "fill_missing", "column": "tip", "params": {"strategy": "median"}},
        {"op": "normalise_text", "column": "sex"},
        {"op": "normalise_text", "column": "day"},
    ]
    out, log = run_plan(df, plan)
    after = profile_dataframe(out)
    assert all(e["status"] == "ok" for e in log)
    assert len(after["issues"]) < len(before["issues"])
    kinds = {i["issue"] for i in after["issues"]}
    assert not kinds & {"duplicate_rows", "numbers_stored_as_text",
                        "hidden_missing_tokens", "inconsistent_categories", "whitespace"}


def test_unexpected_errors_are_logged_not_raised():
    df = pd.DataFrame({"x": [1.0, None]})
    # constant fill with an unhashable-ish value triggers a pandas error, not an OperationError
    plan = [{"op": "fill_missing", "column": "x", "params": {"strategy": "constant", "value": [1, 2]}},
            {"op": "drop_duplicates"}]
    out, log = run_plan(df, plan)
    assert log[0]["status"] == "failed" and log[1]["status"] == "ok"
    assert len(out) == 2


def test_row_removal_keeps_original_index_labels():
    df = pd.DataFrame({"a": [1, 1, 2, None], "b": ["x", "x", "y", "z"]})
    out, _ = run_plan(df, [{"op": "drop_duplicates"}, {"op": "drop_missing_rows", "column": "a"}])
    assert list(out.index) == [0, 2]
