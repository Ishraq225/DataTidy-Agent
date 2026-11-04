"""CSV loading and saving.

Messy files often hide missing values behind tokens such as "N/A" or "?".
pandas would silently turn many of them into NaN, which would hide them from
the profiler. We therefore only treat the empty string as missing on load and
let the profiler report the remaining tokens explicitly.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_csv(path: str | Path, **kwargs) -> pd.DataFrame:
    """Load a CSV without silently converting NA-like tokens."""
    options = {"keep_default_na": False, "na_values": [""]}
    options.update(kwargs)
    return pd.read_csv(path, **options)


def save_csv(df: pd.DataFrame, path: str | Path) -> None:
    """Save a DataFrame to CSV (UTF-8, no index)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
