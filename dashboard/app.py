from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
PUB=ROOT/"published"

st.set_page_config(page_title="Inflection Bottleneck Scanner V5.4",layout="wide")
st.title("Inflection Bottleneck Scanner V5.4")
st.caption("Currency-safe valuation • durable PIT ledgers • entry-aware large-cap research")

meta_path=PUB/"metadata.json"; csv_path=PUB/"latest_research.csv"; track_path=PUB/"track_record.json"
if not csv_path.exists():
    st.info("No published research yet. Run `inflection-scanner research` or the Equity Research Engine workflow.")
    st.stop()

meta=json.loads(meta_path.read_text()) if meta_path.exists() else {}
df=pd.read_csv(csv_path)
cols=st.columns(4)
cols[0].metric("Reports",len(df)); cols[1].metric("Model",str(meta.get("model_version","5.4"))); cols[2].metric("BUY labels",int(df["action"].astype(str).str.startswith("BUY").sum()) if "action" in df else 0); cols[3].metric("Config hash",str(meta.get("config_hash","—")))

actions=sorted(df["action"].dropna().unique().tolist()) if "action" in df else []
selected=st.multiselect("Actions",actions,default=actions)
view=df[df["action"].isin(selected)] if selected and "action" in df else df
preferred=[c for c in ["ticker","company","action","thesis_score","entry_score","trust_grade","current_price","buy_below_price","valuation_status","company_type","eps_revision_30d","next_year_eps_growth"] if c in view.columns]
st.dataframe(view[preferred],use_container_width=True,hide_index=True)

st.subheader("Prospective validation")
if track_path.exists():
    track=json.loads(track_path.read_text()); summaries=pd.DataFrame(track.get("summaries",[]))
    st.caption(f"Benchmark: {track.get('benchmark','SPY')} • Cohort model: {track.get('model_version','5.4')}")
    if summaries.empty: st.info("No matured outcome cohorts yet. V5.4 is accumulating decisions prospectively.")
    else: st.dataframe(summaries,use_container_width=True,hide_index=True)

st.subheader("V5.4 safety changes")
st.markdown("- Foreign-currency / ADR valuation fails closed until FX and security units reconcile.\n- SEC errors are sanitized before publication.\n- Decision and estimate ledgers are committed under `published/` so validation survives cache loss.\n- Outcome tracking is model-versioned and benchmark-relative.")
