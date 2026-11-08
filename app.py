"""DataTidy Agent - Streamlit UI.   Run:  streamlit run app.py"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from datatidy.executor import log_to_dataframe, run_plan
from datatidy.io import load_csv
from datatidy.llm import PROVIDERS, OpenAICompatibleBackend, load_env
from datatidy.pipeline import format_plan, plan_to_table, table_to_plan
from datatidy.planner import PlannerResult, make_plan, rule_based_plan
from datatidy.profiler import profile_dataframe
from datatidy.schema import validate_plan

load_env()
st.set_page_config(page_title="DataTidy Agent", page_icon="🧹", layout="wide")

RULES = "Rule-based (no API key)"
SAMPLES = sorted((Path(__file__).parent / "data" / "messy").glob("*_messy.csv"))

st.title("DataTidy Agent")
st.caption("An LLM proposes a cleaning plan. You review it. A deterministic executor applies it and logs every change.")

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("1. Data")
    uploaded = st.file_uploader("Upload a CSV", type=["csv"], key="upload")
    sample = st.selectbox("...or use a sample", ["(none)"] + [p.name for p in SAMPLES], key="sample")

    st.header("2. Planner")
    provider = st.selectbox("Provider", [RULES] + list(PROVIDERS), key="provider")
    model = st.text_input("Model (optional)", key="model", disabled=provider == RULES,
                          help="Leave empty for the provider default.")
    api_key = st.text_input("API key (optional if set in .env)", type="password", key="api_key",
                            disabled=provider in (RULES, "ollama"))
    st.caption("Privacy: the LLM sees a profile summary (stats and a few sample values), never the whole file.")

# ---------------------------------------------------------------- load data
df = None
source_name = ""
if uploaded is not None:
    df = load_csv(io.BytesIO(uploaded.getvalue()))
    source_name = uploaded.name
elif sample != "(none)":
    df = load_csv(next(p for p in SAMPLES if p.name == sample))
    source_name = sample

if df is None:
    st.info("Upload a CSV or pick a sample in the sidebar to begin.")
    st.stop()

if st.session_state.get("loaded_name") != source_name:          # new file: reset everything
    for k in ("plan_table", "planner", "result"):
        st.session_state.pop(k, None)
    st.session_state["loaded_name"] = source_name

profile = profile_dataframe(df)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", f"{profile['n_rows']:,}")
c2.metric("Columns", profile["n_cols"])
c3.metric("Duplicate rows", profile["n_duplicate_rows"])
c4.metric("Issues found", len(profile["issues"]))

with st.expander("Data preview and detected issues", expanded=True):
    st.dataframe(df.head(50), use_container_width=True)
    if profile["issues"]:
        st.dataframe(pd.DataFrame(profile["issues"]), use_container_width=True, hide_index=True)
    else:
        st.success("The profiler found no issues.")

# ---------------------------------------------------------------- plan
st.subheader("Plan")
if st.button("Propose cleaning plan", type="primary", key="propose"):
    try:
        if provider == RULES:
            plan = rule_based_plan(profile)
            planner = PlannerResult(plan=plan, source="rules", attempts=0)
        else:
            if api_key:
                os.environ[PROVIDERS[provider]["key_env"] or "DATATIDY_UNUSED"] = api_key
            backend = OpenAICompatibleBackend(provider=provider, model=model or None)
            with st.spinner(f"Asking {backend.name}..."):
                planner = make_plan(df, backend, profile=profile)
        st.session_state["planner"] = planner
        st.session_state["plan_table"] = plan_to_table(planner.plan)
        st.session_state.pop("result", None)
    except Exception as exc:
        st.error(f"Could not create a plan: {exc}")

planner = st.session_state.get("planner")
if planner is not None:
    note = f"Plan source: **{planner.source}**"
    if planner.attempts:
        note += f" | attempts: {planner.attempts} | tokens: {planner.prompt_tokens}+{planner.completion_tokens} | {planner.latency_s:.1f}s"
    st.caption(note)
    for w in planner.warnings:
        st.warning(w)
    if planner.errors and planner.source == "fallback":
        with st.expander("Why the LLM plan was rejected"):
            st.write(planner.errors)

    table = st.session_state["plan_table"]
    if table.empty:
        st.success("Empty plan: nothing needs cleaning.")
    else:
        st.write("Untick steps you do not want. You can also edit a step's parameters (JSON).")
        edited = st.data_editor(
            table, key="plan_editor", hide_index=True, use_container_width=True,
            disabled=["op", "column", "reason"],
            column_config={"apply": st.column_config.CheckboxColumn("Apply", width="small"),
                           "params": st.column_config.TextColumn("Parameters (JSON)")},
        )

        if st.button("Run cleaning", type="primary", key="run"):
            steps, errors = table_to_plan(edited)
            check = validate_plan(steps, [str(c) for c in df.columns])
            errors += check.errors
            if errors:
                st.error("Fix these problems first:\n\n- " + "\n- ".join(errors))
            else:
                cleaned, log = run_plan(df, check.steps)
                st.session_state["result"] = (cleaned, log, check.steps)

# ---------------------------------------------------------------- result
result = st.session_state.get("result")
if result is not None:
    cleaned, log, steps = result
    after = profile_dataframe(cleaned)
    st.subheader("Result")
    r1, r2, r3 = st.columns(3)
    r1.metric("Rows", f"{len(cleaned):,}", delta=len(cleaned) - len(df))
    r2.metric("Issues", len(after["issues"]), delta=len(after["issues"]) - len(profile["issues"]), delta_color="inverse")
    failed = sum(1 for e in log if e["status"] == "failed")
    r3.metric("Failed steps", failed, delta_color="inverse")

    tab1, tab2, tab3 = st.tabs(["Cleaned data", "Change log", "Remaining issues"])
    with tab1:
        st.dataframe(cleaned.head(200), use_container_width=True)
    with tab2:
        st.dataframe(log_to_dataframe(log), use_container_width=True, hide_index=True)
    with tab3:
        if after["issues"]:
            st.dataframe(pd.DataFrame(after["issues"]), use_container_width=True, hide_index=True)
        else:
            st.success("No issues remain.")

    d1, d2, d3 = st.columns(3)
    d1.download_button("Download cleaned CSV", cleaned.to_csv(index=False), "cleaned.csv", "text/csv", key="dl_clean")
    d2.download_button("Download change log", log_to_dataframe(log).to_csv(index=False), "change_log.csv", "text/csv", key="dl_log")
    d3.download_button("Download plan (JSON)", json.dumps(steps, indent=2, ensure_ascii=False), "plan.json", "application/json", key="dl_plan")
