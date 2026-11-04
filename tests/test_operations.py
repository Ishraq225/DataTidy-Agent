import numpy as np
import pandas as pd
import pytest

from datatidy.operations import OPERATIONS, OperationError


def test_drop_duplicates_all_columns():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    out = OPERATIONS["drop_duplicates"](df)
    assert len(out.df) == 2 and out.rows_removed == 1


def test_drop_duplicates_subset_and_bad_column():
    df = pd.DataFrame({"id": [1, 1, 2], "v": [10, 20, 30]})
    assert len(OPERATIONS["drop_duplicates"](df, subset=["id"]).df) == 2
    with pytest.raises(OperationError):
        OPERATIONS["drop_duplicates"](df, subset=["nope"])


@pytest.mark.parametrize("strategy,expected", [("mean", 2.0), ("median", 2.0)])
def test_fill_missing_numeric(strategy, expected):
    df = pd.DataFrame({"x": [1.0, np.nan, 3.0]})
    out = OPERATIONS["fill_missing"](df, column="x", strategy=strategy)
    assert out.df["x"].tolist() == [1.0, expected, 3.0]
    assert out.cells_changed == 1


def test_fill_missing_mode_and_constant():
    df = pd.DataFrame({"c": ["a", "a", None, "b"]})
    assert OPERATIONS["fill_missing"](df, column="c", strategy="mode").df["c"].iloc[2] == "a"
    assert OPERATIONS["fill_missing"](df, column="c", strategy="constant", value="?").df["c"].iloc[2] == "?"


def test_fill_missing_errors():
    df = pd.DataFrame({"c": ["a", None]})
    with pytest.raises(OperationError):
        OPERATIONS["fill_missing"](df, column="c", strategy="mean")      # not numeric
    with pytest.raises(OperationError):
        OPERATIONS["fill_missing"](df, column="c", strategy="constant")  # no value
    with pytest.raises(OperationError):
        OPERATIONS["fill_missing"](df, column="zzz", strategy="mode")    # no such column


def test_cast_type_float_counts_failures():
    df = pd.DataFrame({"x": ["1.5", " 2 ", "oops", None]})
    out = OPERATIONS["cast_type"](df, column="x", target="float")
    assert out.df["x"].iloc[:2].tolist() == [1.5, 2.0]
    assert out.extra["newly_missing"] == 1
    assert "WARNING" in out.message


def test_cast_type_int_refuses_to_truncate():
    df = pd.DataFrame({"x": ["1", "2.7", "3"]})
    out = OPERATIONS["cast_type"](df, column="x", target="int")
    assert pd.isna(out.df["x"].iloc[1])          # 2.7 is NOT silently turned into 2
    assert out.df["x"].iloc[0] == 1


def test_cast_type_bool():
    df = pd.DataFrame({"b": ["Yes", "no", "TRUE", "maybe"]})
    out = OPERATIONS["cast_type"](df, column="b", target="bool")
    assert out.df["b"].iloc[:3].tolist() == [True, False, True]
    assert pd.isna(out.df["b"].iloc[3])


def test_cast_type_bad_target():
    with pytest.raises(OperationError):
        OPERATIONS["cast_type"](pd.DataFrame({"x": [1]}), column="x", target="datetime128")


def test_normalise_text():
    df = pd.DataFrame({"c": ["  Male ", "MALE", "male", None, "Fe  male"]})
    out = OPERATIONS["normalise_text"](df, column="c")
    assert out.df["c"].tolist()[:3] == ["male", "male", "male"]
    assert out.df["c"].iloc[4] == "fe male"
    assert pd.isna(out.df["c"].iloc[3])
    assert out.cells_changed == 3


def test_normalise_text_keep_case():
    df = pd.DataFrame({"c": ["  Ali  Khan "]})
    out = OPERATIONS["normalise_text"](df, column="c", lowercase=False)
    assert out.df["c"].iloc[0] == "Ali Khan"


def test_normalise_text_rejects_numeric():
    with pytest.raises(OperationError):
        OPERATIONS["normalise_text"](pd.DataFrame({"n": [1, 2]}), column="n")


def test_strip_symbols_currency_percent_accounting():
    df = pd.DataFrame({"p": ["$1,200.50", "£3", "12%", "(500)", "garbage", None]})
    out = OPERATIONS["strip_symbols"](df, column="p")
    v = out.df["p"].tolist()
    assert v[:4] == [1200.5, 3.0, 12.0, -500.0]
    assert np.isnan(v[4]) and np.isnan(v[5])
    assert out.extra["newly_missing"] == 1       # only "garbage" is new damage


def test_strip_symbols_suffixes_are_opt_in():
    df = pd.DataFrame({"n": ["1.2k", "3m"]})
    assert OPERATIONS["strip_symbols"](df, column="n").df["n"].isna().all()
    out = OPERATIONS["strip_symbols"](df, column="n", expand_suffixes=True)
    assert out.df["n"].tolist() == [1200.0, 3_000_000.0]


def test_standardize_missing_single_and_all_columns():
    df = pd.DataFrame({"a": ["x", "N/A", "?"], "b": ["null", "ok", " - "], "n": [1, 2, 3]})
    one = OPERATIONS["standardize_missing"](df, column="a")
    assert one.df["a"].isna().sum() == 2 and one.df["b"].isna().sum() == 0
    allc = OPERATIONS["standardize_missing"](df)
    assert allc.cells_changed == 4


def test_standardize_missing_custom_tokens():
    df = pd.DataFrame({"a": ["x", "999", "N/A"]})
    out = OPERATIONS["standardize_missing"](df, column="a", tokens=["999"])
    assert out.df["a"].isna().sum() == 1 and out.df["a"].iloc[2] == "N/A"


@pytest.mark.parametrize("op,kwargs", [
    ("drop_duplicates", {}),
    ("fill_missing", {"column": "x", "strategy": "median"}),
    ("cast_type", {"column": "x", "target": "float"}),
    ("normalise_text", {"column": "t"}),
    ("strip_symbols", {"column": "t"}),
    ("standardize_missing", {"column": "t"}),
])
def test_no_operation_mutates_its_input(op, kwargs):
    df = pd.DataFrame({"x": [1.0, np.nan, 1.0], "t": [" A", "N/A", " A"]})
    snapshot = df.copy(deep=True)
    OPERATIONS[op](df, **kwargs)
    pd.testing.assert_frame_equal(df, snapshot)


def test_unknown_parameters_are_rejected_not_ignored():
    df = pd.DataFrame({"x": [1.0, None]})
    with pytest.raises(TypeError):
        OPERATIONS["fill_missing"](df, column="x", strategy="median", bogus=1)
