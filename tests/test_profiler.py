import numpy as np
import pandas as pd

from datatidy.profiler import profile_dataframe, profile_to_text


def issues(profile, kind):
    return [i for i in profile["issues"] if i["issue"] == kind]


def test_clean_data_has_no_issues():
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": ["x", "y", "z", "x", "y"]})
    p = profile_dataframe(df)
    assert p["issues"] == [] and p["n_duplicate_rows"] == 0


def test_detects_duplicates_and_missing():
    df = pd.DataFrame({"a": [1.0, 1.0, np.nan, 4.0]})
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    p = profile_dataframe(df)
    assert p["n_duplicate_rows"] >= 1
    assert issues(p, "duplicate_rows") and issues(p, "missing_values")


def test_detects_numbers_stored_as_text_and_hidden_missing():
    df = pd.DataFrame({"price": ["$1,200", "$300", "N/A", "$45.5", "$10"]})
    p = profile_dataframe(df)
    assert issues(p, "numbers_stored_as_text")
    assert issues(p, "hidden_missing_tokens")


def test_detects_inconsistent_categories_and_whitespace():
    df = pd.DataFrame({"city": ["Karachi", "karachi ", "KARACHI", "Lahore"] * 5})
    p = profile_dataframe(df)
    assert issues(p, "inconsistent_categories") and issues(p, "whitespace")


def test_detects_mixed_date_formats():
    df = pd.DataFrame({"d": ["2024-01-05", "2024-02-10", "03/04/2024", "05/06/2024", "2024-03-01"]})
    p = profile_dataframe(df)
    assert issues(p, "dates_stored_as_text")
    assert issues(p, "mixed_date_formats")


def test_detects_numeric_outliers():
    df = pd.DataFrame({"mass": [3000, 3100, 3200, 3150, 3050, 3120, 3080, 31000]})
    p = profile_dataframe(df)
    assert issues(p, "numeric_outliers")


def test_profile_is_json_serialisable_and_text_renders():
    import json
    df = pd.DataFrame({"a": [1, 2, None], "b": ["x", "N/A", "y"]})
    p = profile_dataframe(df)
    json.dumps(p)                                   # must not raise
    text = profile_to_text(p)
    assert "Dataset: 3 rows" in text and "Detected issues" in text
