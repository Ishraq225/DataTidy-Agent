# Datasets

Three public datasets, downloaded by `scripts/download_datasets.py` from
[mwaskom/seaborn-data](https://github.com/mwaskom/seaborn-data). They are git-ignored; check
each dataset's terms before redistributing any copy.

| Dataset | Rows | Why it is useful | Injected corruptions (seed 42) |
|---|---|---|---|
| tips | 244 | Small, clean, mixed numeric/categorical | `$` prefix on all bills, `N/A` in tips, case/space noise, 10 duplicates |
| penguins | 344 | Real missing values already present | Case/space noise, 4 impossible body masses (x10), 8 duplicates |
| titanic | 891 | Larger, many columns, heavy natural missingness | `£` prefix on fares, `?` in age, case/space noise, 15 duplicates |

Week 3 replaces `scripts/make_messy_samples.py` with a full corruption generator that records
ground truth for every injected error. Target: 8-10 datasets.
