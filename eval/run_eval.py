"""Run the benchmark.

  python -m eval.run_eval --systems noop,rules                       # no API key needed
  python -m eval.run_eval --systems noop,rules,single,agent --provider groq --sleep 3
  python -m eval.run_eval --systems agent --provider groq --resume   # continue after a rate limit
"""

from __future__ import annotations

import argparse
import io
import json
import time
from pathlib import Path

import pandas as pd

from datatidy.io import load_csv
from datatidy.profiler import profile_dataframe
from .baselines import LLM_SYSTEMS, RUNNERS, SYSTEMS
from .corrupt import make_case
from .datasets import DATASETS
from .metrics import evaluate, grid

ROOT = Path(__file__).resolve().parent
KEY = ["system", "dataset", "seed"]


def run_one(system: str, case, backend, messy_loaded, before_cache) -> dict:
    row = {"system": system, "dataset": case.dataset, "seed": case.seed, "error": ""}
    try:
        res = RUNNERS[system](messy_loaded, backend)
    except Exception as exc:                              # keep the benchmark running
        row["error"] = f"{type(exc).__name__}: {exc}"[:300]
        return row, None
    metrics = evaluate(case, res.cleaned, messy_loaded, before_cache)
    row.update(metrics)
    row.update(
        source=res.source, attempts=res.attempts, plan_valid_first_try=res.plan_valid_first_try,
        n_steps=len(res.plan), failed_steps=sum(1 for e in res.log if e["status"] == "failed"),
        prompt_tokens=res.prompt_tokens, completion_tokens=res.completion_tokens,
        latency_s=round(res.latency_s, 3),
        issues_before=len(profile_dataframe(messy_loaded)["issues"]),
        issues_after=len(profile_dataframe(res.cleaned)["issues"]) if len(res.cleaned.columns) else 0,
    )
    return row, res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DataTidy benchmark")
    ap.add_argument("--systems", default="noop,rules", help=f"comma list from {SYSTEMS}")
    ap.add_argument("--datasets", default="all")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--provider"), ap.add_argument("--model")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds to wait between LLM calls")
    ap.add_argument("--out", default=str(ROOT / "results"))
    ap.add_argument("--resume", action="store_true", help="skip runs already in runs.csv")
    args = ap.parse_args(argv)

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    bad = [s for s in systems if s not in RUNNERS]
    if bad:
        ap.error(f"unknown systems {bad}; choose from {SYSTEMS}")
    datasets = sorted(DATASETS) if args.datasets == "all" else args.datasets.split(",")

    backend = None
    if any(s in LLM_SYSTEMS for s in systems):
        from datatidy.llm import get_backend
        try:
            backend = get_backend(args.provider, args.model)
        except (RuntimeError, ValueError) as exc:
            print(f"Error: {exc}")
            return 2
        print(f"LLM backend: {backend.name}")

    out = Path(args.out)
    (out / "plans").mkdir(parents=True, exist_ok=True)
    runs_path = out / "runs.csv"
    rows = pd.read_csv(runs_path, float_precision="round_trip").to_dict("records") if args.resume and runs_path.exists() else []
    done = {(r["system"], r["dataset"], int(r["seed"])) for r in rows if not isinstance(r.get("error"), str) or not r["error"]}
    if args.resume:
        rows = [r for r in rows if (r["system"], r["dataset"], int(r["seed"])) in done]

    total = len(datasets) * len(args.seeds) * len(systems)
    k = 0
    for name in datasets:
        for seed in args.seeds:
            case = make_case(name, seed)
            messy_loaded = load_csv(io.StringIO(case.messy_csv()))
            before_cache = grid(case, messy_loaded)
            for system in systems:
                k += 1
                if (system, name, seed) in done:
                    continue
                row, res = run_one(system, case, backend, messy_loaded, before_cache)
                rows.append(row)
                tag = f"[{k}/{total}] {system:6} {name:10} seed {seed}"
                print(tag, f"acc {row['cell_accuracy']:.3f} dmg {row['damage_rate']:.3f}" if not row["error"] else f"ERROR {row['error']}")
                if res is not None and res.plan:
                    (out / "plans" / f"{system}_{name}_s{seed}.json").write_text(
                        json.dumps(res.plan, indent=2, ensure_ascii=False), encoding="utf-8")
                pd.DataFrame(rows).to_csv(runs_path, index=False)      # save after every run
                if system in LLM_SYSTEMS and args.sleep:
                    time.sleep(args.sleep)

    df = pd.DataFrame(rows)
    df.to_csv(runs_path, index=False)
    from .report import write_report
    write_report(df, out)
    print(f"\nSaved {runs_path} and the report in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
