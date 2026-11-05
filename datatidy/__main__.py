<<<<<<< HEAD
"""Command line:

    python -m datatidy profile data.csv
    python -m datatidy plan    data.csv [--provider groq|ollama|openai|gemini] [--model NAME]
    python -m datatidy clean   data.csv [--provider ...] [--yes] [-o cleaned.csv]
    python -m datatidy apply   data.csv plan.json
"""
=======
"""Command line: python -m datatidy profile data.csv | apply data.csv plan.json"""
>>>>>>> 1cd048273e899c9cfef0050d522a8bb3c029c006

from __future__ import annotations

import argparse
import json
import sys

from .executor import log_to_dataframe, run_plan
from .io import load_csv, save_csv
<<<<<<< HEAD
from .pipeline import clean_dataframe, format_plan
from .profiler import profile_dataframe, profile_to_text


def _run_llm_command(args, df) -> int:
    from .llm import get_backend
    try:
        backend = get_backend(args.provider, args.model)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Using {backend.name}")

    def approve(plan):
        print("\nProposed plan:\n" + format_plan(plan))
        if args.cmd == "plan" or getattr(args, "yes", False):
            return args.cmd == "clean"
        return input("\nApply this plan? [y/N] ").strip().lower() in ("y", "yes")

    result = clean_dataframe(df, backend, approve=approve)
    pr = result.planner
    for w in pr.warnings:
        print(f"Note: {w}")
    print(f"\nPlan source: {pr.source} | attempts: {pr.attempts} | "
          f"tokens: {pr.prompt_tokens}+{pr.completion_tokens} | {pr.latency_s:.1f}s")
    if pr.errors and pr.source == "fallback":
        print("Why the LLM plan was rejected:\n  - " + "\n  - ".join(pr.errors[:5]))

    plan_path = args.output if args.cmd == "plan" else args.plan_out
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(pr.plan, f, indent=2, ensure_ascii=False)

    if args.cmd == "plan":
        print(f"Saved plan to {args.output}. Apply it with: python -m datatidy apply {args.csv} {args.output}")
        return 0
    if not result.approved:
        print("Cancelled. Nothing was changed.")
        return 0
    save_csv(result.cleaned, args.output)
    log_df = log_to_dataframe(result.log)
    save_csv(log_df, args.log)
    failed = int((log_df["status"] == "failed").sum())
    print(f"\nRows: {len(df)} -> {len(result.cleaned)}. Issues: {len(result.profile_before['issues'])} -> "
          f"{len(result.profile_after['issues'])}. Failed steps: {failed}")
    print(f"Saved {args.output}, {args.log}, {args.plan_out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="datatidy", description="DataTidy Agent")
=======
from .profiler import profile_dataframe, profile_to_text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="datatidy", description="DataTidy Agent (Week 1 core)")
>>>>>>> 1cd048273e899c9cfef0050d522a8bb3c029c006
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("profile", help="profile a CSV and list likely problems")
    pp.add_argument("csv")
    pp.add_argument("--json", action="store_true", help="print JSON instead of text")

    pa = sub.add_parser("apply", help="apply a JSON cleaning plan to a CSV")
    pa.add_argument("csv")
    pa.add_argument("plan", help="path to plan.json (a list of steps)")
    pa.add_argument("-o", "--output", default="cleaned.csv")
    pa.add_argument("--log", default="change_log.csv")

<<<<<<< HEAD
    for name, helptext in (("plan", "ask the LLM for a cleaning plan (does not change data)"),
                           ("clean", "plan with the LLM, ask for approval, then clean")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("csv")
        sp.add_argument("--provider", help="groq | ollama | openai | gemini (default: $DATATIDY_PROVIDER or groq)")
        sp.add_argument("--model", help="override the provider's default model")
        if name == "plan":
            sp.add_argument("-o", "--output", default="plan.json")
        else:
            sp.add_argument("-y", "--yes", action="store_true", help="skip the approval question")
            sp.add_argument("-o", "--output", default="cleaned.csv")
            sp.add_argument("--log", default="change_log.csv")
            sp.add_argument("--plan-out", default="plan.json")

=======
>>>>>>> 1cd048273e899c9cfef0050d522a8bb3c029c006
    args = p.parse_args(argv)
    df = load_csv(args.csv)

    if args.cmd == "profile":
        prof = profile_dataframe(df)
        print(json.dumps(prof, indent=2, default=str) if args.json else profile_to_text(prof))
        return 0

<<<<<<< HEAD
    if args.cmd in ("plan", "clean"):
        return _run_llm_command(args, df)

=======
>>>>>>> 1cd048273e899c9cfef0050d522a8bb3c029c006
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
