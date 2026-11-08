"""Benchmark base tables (public datasets from seaborn-data).

Every base table is de-duplicated first: natural exact duplicates are indistinguishable
from injected ones, so keeping them would make the ground truth ambiguous.
Large tables are sampled with a FIXED seed so the clean table is identical for every
corruption seed.
"""

from __future__ import annotations

import io
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BASE_URL = "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/{}.csv"

# name -> max rows kept
DATASETS: dict[str, int] = {
    "tips": 1000, "penguins": 1000, "titanic": 1000, "mpg": 1000, "planets": 1000,
    "healthexp": 1000, "exercise": 1000, "diamonds": 1000, "dowjones": 1000, "seaice": 1000,
}


def _read(name: str) -> pd.DataFrame:
    path = RAW / f"{name}.csv"
    if not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urlopen(BASE_URL.format(name), timeout=30).read())
    return pd.read_csv(path)


def load_base(name: str) -> pd.DataFrame:
    """Deduplicated (and possibly sampled) base table with a clean RangeIndex."""
    if name not in DATASETS:
        raise KeyError(f"Unknown dataset '{name}'. Choose from {sorted(DATASETS)}.")
    df = _read(name).drop_duplicates()
    if len(df) > DATASETS[name]:
        df = df.sample(DATASETS[name], random_state=0).sort_index()
    return df.reset_index(drop=True)
