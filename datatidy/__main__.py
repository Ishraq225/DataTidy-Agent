"""Command line: python -m datatidy profile data.csv | apply data.csv plan.json"""

from __future__ import annotations

import argparse
import json
import sys

from .executor import log_to_dataframe, run_plan
from .io import load_csv, save_csv
from .profiler import profile_dataframe, profile_to_text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="datatidy", description="DataTidy Agent (Week 1 core)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("profile", help="profile a CSV and list likely problems")
    pp.add_argument("csv")
    pp.add_argument("--json", action="store_true", help="print JSON instead of text")

    pa = sub.add_parser("apply", help="apply a JSON cleaning plan to a CSV")
    pa.add_argument("csv")
    pa.add_argument("plan", help="path to plan.json (a list of steps)")
    pa.add_argument("-o", "--output", default="cleaned.csv")
    pa.add_argument("--log", default="change_log.csv")

    args = p.parse_args(argv)
    df = load_csv(args.csv)

    if args.cmd == "profile":
        prof = profile_dataframe(df)
        print(json.dumps(prof, indent=2, default=str) if args.json else profile_to_text(prof))
        return 0

    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    cleaned, log = run_plan(df, plan)
    save_csv(cleaned, args.output)
    log_df = log_to_dataframe(log)
    save_csv(log_df, args.log)
    print(log_df[["step", "op", "column", "status", "cells_changed", "message"]].to_string(index=False))
    print(f"\nRows: {len(df)} -> {len(cleaned)}. Saved {args.output} and {args.log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
