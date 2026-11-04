"""Create messy versions of the three Week-1 datasets (seeded, reproducible).

This is a quick prototype of the corruption generator. In Week 3 it becomes
eval/corrupt.py, with a logged ground truth for every injected error.

Usage: python scripts/make_messy_samples.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, MESSY = ROOT / "data" / "raw", ROOT / "data" / "messy"


def add_duplicates(df, rng, n):
    idx = rng.choice(len(df), size=n, replace=False)
    return pd.concat([df, df.iloc[idx]], ignore_index=True)


def case_and_space_noise(s, rng, p=0.25):
    def f(v):
        if pd.isna(v) or rng.random() > p:
            return v
        return rng.choice([str(v).upper(), str(v).lower(), f"  {v} ", f"{v}  "])
    return s.map(f)


def make_tips(rng):
    df = pd.read_csv(RAW / "tips.csv")
    df["total_bill"] = df["total_bill"].map(lambda v: f"${v:,.2f}")
    df["sex"] = case_and_space_noise(df["sex"], rng)
    df["day"] = case_and_space_noise(df["day"], rng)
    tip = df["tip"].astype(object)
    tip[rng.choice(len(df), 20, replace=False)] = "N/A"
    df["tip"] = tip
    return add_duplicates(df, rng, 10)


def make_penguins(rng):
    df = pd.read_csv(RAW / "penguins.csv")
    df["species"] = case_and_space_noise(df["species"], rng)
    df["island"] = case_and_space_noise(df["island"], rng, p=0.2)
    mass = df["body_mass_g"].copy()
    mass[rng.choice(len(df), 4, replace=False)] *= 10        # impossible masses
    df["body_mass_g"] = mass
    return add_duplicates(df, rng, 8)


def make_titanic(rng):
    df = pd.read_csv(RAW / "titanic.csv")
    df["fare"] = df["fare"].map(lambda v: f"£{v:.2f}")
    age = df["age"].astype(object)
    age[rng.choice(len(df), 25, replace=False)] = "?"
    df["age"] = age
    df["embark_town"] = case_and_space_noise(df["embark_town"], rng)
    return add_duplicates(df, rng, 15)


def main(seed: int = 42) -> None:
    MESSY.mkdir(parents=True, exist_ok=True)
    for name, fn in [("tips", make_tips), ("penguins", make_penguins), ("titanic", make_titanic)]:
        out = fn(np.random.default_rng(seed))
        out.to_csv(MESSY / f"{name}_messy.csv", index=False)
        print(f"wrote {name}_messy.csv ({len(out)} rows)")


if __name__ == "__main__":
    main()
