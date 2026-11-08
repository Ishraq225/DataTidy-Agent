import numpy as np
import pandas as pd
import pytest

from datatidy.operations import OPERATIONS, OperationError


def test_parse_dates_mixed_formats_and_failures():
    df = pd.DataFrame({"d": ["2024-01-05", "03/04/2024", " Mar 5, 2024 ", "garbage", "N/A", None]})
    out = OPERATIONS["parse_dates"](df, column="d")
    parsed = out.df["d"]
    assert pd.api.types.is_datetime64_any_dtype(parsed)
    assert parsed.iloc[0] == pd.Timestamp("2024-01-05")
    assert parsed.iloc[1] == pd.Timestamp("2024-03-04")          # month first by default
    assert parsed.iloc[2] == pd.Timestamp("2024-03-05")
    assert out.extra["newly_missing"] == 1                       # only "garbage"; N/A is a known token
    assert "WARNING" in out.message


def test_parse_dates_dayfirst():
    df = pd.DataFrame({"d": ["03/04/2024"]})
    out = OPERATIONS["parse_dates"](df, column="d", dayfirst=True)
    assert out.df["d"].iloc[0] == pd.Timestamp("2024-04-03")


def test_map_values_trims_and_keeps_unmapped():
    df = pd.DataFrame({"city": ["khi", " KHI ", "Lahore", None]})
    out = OPERATIONS["map_values"](df, column="city", mapping={"khi": "Karachi"}, case_insensitive=True)
    assert out.df["city"].tolist()[:3] == ["Karachi", "Karachi", "Lahore"]
    assert out.cells_changed == 2
    exact = OPERATIONS["map_values"](df, column="city", mapping={"khi": "Karachi"})
    assert exact.cells_changed == 1                                # " KHI " does not match exactly


def test_map_values_requires_mapping():
    with pytest.raises(OperationError):
        OPERATIONS["map_values"](pd.DataFrame({"c": ["a"]}), column="c", mapping={})


def test_clip_outliers_iqr_clip_and_set_missing():
    df = pd.DataFrame({"m": [3000, 3100, 3200, 3150, 3050, 3120, 3080, 31000]})
    clipped = OPERATIONS["clip_outliers"](df, column="m")
    assert clipped.cells_changed == 1 and clipped.df["m"].max() < 31000
    gone = OPERATIONS["clip_outliers"](df, column="m", action="set_missing")
    assert gone.df["m"].isna().sum() == 1 and gone.df["m"].iloc[7] != gone.df["m"].iloc[7]


def test_clip_outliers_rejects_text_and_constant_column():
    with pytest.raises(OperationError):
        OPERATIONS["clip_outliers"](pd.DataFrame({"t": ["a", "b"]}), column="t")
    out = OPERATIONS["clip_outliers"](pd.DataFrame({"c": [5, 5, 5, 5]}), column="c")
    assert out.cells_changed == 0


def test_drop_missing_rows_by_column_and_threshold():
    df = pd.DataFrame({"a": [1, None, 3, None], "b": [1, None, None, None], "c": [1, 2, None, None]})
    assert len(OPERATIONS["drop_missing_rows"](df, column="a").df) == 2
    out = OPERATIONS["drop_missing_rows"](df, threshold=0.6)       # >= 60% of cells missing
    assert out.rows_removed == 3 and len(out.df) == 1      # rows 1, 2, 3 are >= 60% empty


def test_rename_and_drop_column():
    df = pd.DataFrame({"a": [1], "b": [2]})
    assert list(OPERATIONS["rename_column"](df, column="a", new_name="x").df.columns) == ["x", "b"]
    with pytest.raises(OperationError):
        OPERATIONS["rename_column"](df, column="a", new_name="b")  # would overwrite
    assert list(OPERATIONS["drop_column"](df, column="a").df.columns) == ["b"]


@pytest.mark.parametrize("op,kwargs", [
    ("parse_dates", {"column": "d"}),
    ("map_values", {"column": "d", "mapping": {"a": "b"}}),
    ("clip_outliers", {"column": "n"}),
    ("drop_missing_rows", {"column": "n"}),
    ("rename_column", {"column": "n", "new_name": "z"}),
    ("drop_column", {"column": "n"}),
])
def test_new_operations_do_not_mutate_input(op, kwargs):
    df = pd.DataFrame({"d": ["2024-01-01", "a"], "n": [1.0, 100.0]})
    snap = df.copy(deep=True)
    OPERATIONS[op](df, **kwargs)
    pd.testing.assert_frame_equal(df, snap)
