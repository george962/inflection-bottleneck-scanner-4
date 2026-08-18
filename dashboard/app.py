from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "published"
LATEST = PUBLISHED / "latest_research.json"
META = PUBLISHED / "metadata.json"
TRACK = PUBLISHED / "track_record.json"


def pct(value):
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "n/a"


def money(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "n/a"


def market_cap_b(value):
    try:
        return float(value) / 1_000_000_000
    except (TypeError, ValueError):
        return None


def status_icon(value):
    return "✅" if value else "❌"


def action_bucket(action: str | None) -> str:
    if action in {"BUY NOW", "BUY NOW — RESET ENTRY", "BUY ON PULLBACK"}:
        return "Actionable"
    if action == "TOO LATE / OVEREXTENDED":
        return "Past primary entry"
    if action == "WATCH — DEVELOPING":
        return "Developing"
    if action in {"VALUATION UNRESOLVED", "DATA INCOMPLETE", "REVIEW DATA"}:
        return "Unresolved / data"
    return "Other"


st.set_page_config(page_title="Large-Cap Inflection Research v5.3", layout="wide")
st.title("Large-Cap Inflection Research v5.3")
st.caption(
    "Large-established company discovery with separate thesis quality and entry timing. "
    "V5.3 can explicitly say that a good company is already past its primary entry, and it refuses to publish a buy zone when valuation models disagree."
)

if not LATEST.exists():
    st.info("No v5.3 research has been published yet. Run the GitHub Actions workflow `Equity Research Engine`.")
    st.stop()

reports = json.loads(LATEST.read_text(encoding="utf-8"))
meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
track = json.loads(TRACK.read_text(encoding="utf-8")) if TRACK.exists() else {"summaries": [], "observations": []}

if not isinstance(reports, list) or not reports:
    selection = meta.get("discovery_run", {}).get("research_selection", {}) or {}
    st.warning("The latest research run produced 0 full research reports. The dashboard is healthy; the upstream selection stage found no eligible reports.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CORE candidates", selection.get("core_candidates", 0))
    c2.metric("Entry candidates", selection.get("entry_opportunity_candidates", 0))
    c3.metric("Late diagnostic", selection.get("late_diagnostic_candidates", 0))
    c4.metric("Selected", selection.get("selected_for_research", 0))
    st.stop()

rows = []
for report in reports:
    conviction = report.get("conviction", {})
    valuation = report.get("valuation", {})
    trust = report.get("trust", {})
    metrics = report.get("metrics", {})
    discovery = report.get("discovery", {})
    entry = conviction.get("entry_timing", {})
    rows.append(
        {
            "ticker": report.get("ticker"),
            "company": report.get("company"),
            "action": conviction.get("action"),
            "bucket": action_bucket(conviction.get("action")),
            "thesis": conviction.get("thesis_score"),
            "entry": conviction.get("entry_score"),
            "entry_state": entry.get("entry_state"),
            "market_cap_b": market_cap_b(trust.get("market_cap")),
            "years_public": trust.get("years_public"),
            "analysts": trust.get("analyst_count"),
            "trust": trust.get("trust_score"),
            "sec": trust.get("evidence_status"),
            "filings": trust.get("filing_count"),
            "current": metrics.get("price"),
            "buy_below": conviction.get("buy_below_price"),
            "gap_to_buy_zone": conviction.get("gap_to_buy_zone"),
            "base_fair": conviction.get("base_fair_value"),
            "base_cagr": valuation.get("base_cagr"),
            "expected_cagr": valuation.get("expected_cagr"),
            "bear_return": valuation.get("bear_return"),
            "valuation_status": valuation.get("valuation_status"),
            "valuation_family": valuation.get("company_type"),
            "models": valuation.get("model_count"),
            "agreement": valuation.get("model_agreement"),
            "model_ratio": valuation.get("model_base_ratio"),
            "price_stage": discovery.get("price_stage"),
            "return_6m": metrics.get("return_6m"),
            "return_12m": metrics.get("return_12m"),
            "from_52w_high": metrics.get("distance_from_52w_high"),
            "eps_revision_30d": metrics.get("eps_revision_30d"),
        }
    )

df = pd.DataFrame(rows)

st.sidebar.header("Default risk filter")
tiers = st.sidebar.multiselect("Company tier", ["CORE", "MIDCAP", "SPECULATIVE"], default=["CORE"])
min_market_cap = st.sidebar.slider("Minimum market cap ($B)", 0, 200, 25)
min_thesis = st.sidebar.slider("Minimum thesis score", 0, 100, 55)

# risk_tier is available in reports but not needed in the table until filtering
risk_map = {r.get("ticker"): r.get("trust", {}).get("risk_tier") for r in reports}
df["risk_tier"] = df["ticker"].map(risk_map)
filtered = df.copy()
if tiers:
    filtered = filtered[filtered["risk_tier"].isin(tiers)]
filtered = filtered[filtered["market_cap_b"].fillna(0) >= min_market_cap]
filtered = filtered[filtered["thesis"].fillna(0) >= min_thesis]

st.subheader("Separate the company thesis from the entry")
st.write(
    "**Thesis score** asks whether the large company, fundamentals, revisions, corroborating data and resolved valuation are attractive. "
    "**Entry score** asks whether the primary rerating has already happened. This prevents an excellent company that is +100%/+200% into a move from being hidden inside a generic WATCH label."
)

summary_cols = st.columns(5)
summary_cols[0].metric("BUY NOW", int((filtered["action"] == "BUY NOW").sum()))
summary_cols[1].metric("Reset entries", int((filtered["action"] == "BUY NOW — RESET ENTRY").sum()))
summary_cols[2].metric("Pullback buys", int((filtered["action"] == "BUY ON PULLBACK").sum()))
summary_cols[3].metric("Past primary entry", int((filtered["action"] == "TOO LATE / OVEREXTENDED").sum()))
summary_cols[4].metric("Valuation / data unresolved", int(filtered["action"].isin(["VALUATION UNRESOLVED", "DATA INCOMPLETE", "REVIEW DATA"]).sum()))

show_cols = [
    "ticker",
    "company",
    "action",
    "thesis",
    "entry",
    "entry_state",
    "market_cap_b",
    "analysts",
    "trust",
    "current",
    "buy_below",
    "base_fair",
    "base_cagr",
    "valuation_status",
    "agreement",
    "return_6m",
    "return_12m",
    "from_52w_high",
]

actionable_tab, developing_tab, late_tab, unresolved_tab, all_tab = st.tabs(
    ["Actionable now", "Developing", "Past primary entry", "Unresolved / data", "All researched"]
)

with actionable_tab:
    actionable = filtered[filtered["bucket"] == "Actionable"]
    if actionable.empty:
        st.info("No company currently meets the full BUY NOW / reset-entry / pullback criteria. V5.3 does not manufacture a BUY label when evidence or valuation is unresolved.")
    else:
        st.dataframe(actionable[show_cols], use_container_width=True, hide_index=True)

with developing_tab:
    developing = filtered[filtered["bucket"] == "Developing"]
    if developing.empty:
        st.info("No developing names match the current filters.")
    else:
        st.dataframe(developing[show_cols], use_container_width=True, hide_index=True)

with late_tab:
    late = filtered[filtered["bucket"] == "Past primary entry"]
    if late.empty:
        st.info("No clearly overextended primary-entry cases match the current filters.")
    else:
        st.dataframe(late[show_cols], use_container_width=True, hide_index=True)
        st.caption("These can still be excellent businesses. The label means the scanner believes the easy primary rerating already occurred; wait for a meaningful reset or a new fundamental leg.")

with unresolved_tab:
    unresolved = filtered[filtered["bucket"] == "Unresolved / data"]
    if unresolved.empty:
        st.info("No unresolved/data cases match the current filters.")
    else:
        st.dataframe(unresolved[show_cols], use_container_width=True, hide_index=True)

with all_tab:
    st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)

choices = filtered["ticker"].tolist() or df["ticker"].tolist()
if not choices:
    st.warning("No companies match the current filters.")
    st.stop()

ticker = st.selectbox("Research report", choices)
report = next(r for r in reports if r.get("ticker") == ticker)
conviction = report.get("conviction", {})
valuation = report.get("valuation", {})
trust = report.get("trust", {})
metrics = report.get("metrics", {})
entry = conviction.get("entry_timing", {})

st.divider()
st.subheader(f"{ticker} — {report.get('company')}")
action = conviction.get("action")
if action == "BUY NOW":
    st.success(f"BUY NOW: current price {money(metrics.get('price'))} is inside the resolved return-required buy zone of {money(conviction.get('buy_below_price'))} or lower.")
elif action == "BUY NOW — RESET ENTRY":
    st.success(f"BUY NOW — RESET ENTRY: the primary rerating was large, but a meaningful reset has reopened the entry window. Resolved buy zone: {money(conviction.get('buy_below_price'))} or lower.")
elif action == "BUY ON PULLBACK":
    st.warning(f"BUY ON PULLBACK: thesis is strong, but current price is above the resolved buy zone of {money(conviction.get('buy_below_price'))}.")
elif action == "TOO LATE / OVEREXTENDED":
    st.warning("TOO LATE / OVEREXTENDED: the company may still be attractive, but the scanner believes the primary entry occurred earlier and the stock has not reset enough to justify chasing it.")
elif action == "VALUATION UNRESOLVED":
    st.error("VALUATION UNRESOLVED: independent models disagree too much. V5.3 intentionally does not publish a buy-below price from their midpoint.")
elif action == "DATA INCOMPLETE":
    st.error("DATA INCOMPLETE: one or more essential market/fundamental inputs are unavailable. SEC is optional and is not the cause of this action in V5.3.")
elif action == "REVIEW DATA":
    st.error("REVIEW DATA: a data/valuation sanity check failed.")
else:
    st.info(f"{action}: {conviction.get('rationale')}")

hero = st.columns(8)
hero[0].metric("Action", action)
hero[1].metric("Thesis", conviction.get("thesis_score"))
hero[2].metric("Entry", conviction.get("entry_score"))
hero[3].metric("Market cap", f"${market_cap_b(trust.get('market_cap')):,.1f}B" if market_cap_b(trust.get("market_cap")) is not None else "n/a")
hero[4].metric("Current", money(metrics.get("price")))
hero[5].metric("Buy below", money(conviction.get("buy_below_price")))
hero[6].metric("Base fair", money(conviction.get("base_fair_value")))
hero[7].metric("Trust", f"{trust.get('trust_grade')} / {trust.get('trust_score')}")

st.caption(
    f"Entry state: {entry.get('entry_state')} | Valuation family: {valuation.get('company_type')} | "
    f"Valuation status: {valuation.get('valuation_status')} | Models: {valuation.get('model_count')} | "
    f"Agreement: {valuation.get('model_agreement')} | Optional SEC: {trust.get('evidence_status')} / {trust.get('filing_count')} filings"
)

st.subheader("Thesis vs entry timing")
left_score, right_score = st.columns(2)
with left_score:
    st.metric("Business / thesis score", conviction.get("thesis_score"))
    st.write("Fundamentals + revisions + resolved valuation + company quality + data/analyst corroboration. SEC is optional enrichment.")
with right_score:
    st.metric("Entry timing score", conviction.get("entry_score"))
    st.write(
        f"{entry.get('entry_state')}. 6M {pct(entry.get('return_6m'))}; 12M {pct(entry.get('return_12m'))}; "
        f"distance from 52-week high {pct(entry.get('distance_from_52w_high'))}."
    )

pillars = conviction.get("pillars", {})
pillar_cols = st.columns(6)
for col, (label, key) in zip(
    pillar_cols,
    [
        ("Fundamentals", "fundamental_inflection"),
        ("Revisions", "estimate_revision"),
        ("Valuation", "valuation"),
        ("Entry timing", "price_timing"),
        ("Company quality", "company_quality"),
        ("Research evidence", "evidence"),
    ],
):
    col.metric(label, pillars.get(key))

check_rows = [
    {"condition": name.replace("_", " ").title(), "pass": status_icon(passed)}
    for name, passed in conviction.get("checks", {}).items()
]
if check_rows:
    st.dataframe(pd.DataFrame(check_rows), use_container_width=True, hide_index=True)

st.subheader("Valuation credibility")
if valuation.get("valuation_resolved"):
    st.success(
        f"RESOLVED: agreement={valuation.get('model_agreement')}, base-value ratio={valuation.get('model_base_ratio')}x. "
        f"The buy zone is calculated only after this gate passes."
    )
    st.write(
        f"Base fair value **{money(conviction.get('base_fair_value'))}**; required base CAGR **{pct(conviction.get('required_base_cagr'))}**; "
        f"buy at **{money(conviction.get('buy_below_price'))} or lower**."
    )
    scenario_rows = []
    current = metrics.get("price")
    for scenario in valuation.get("scenarios", []):
        fair = scenario.get("fair_value")
        scenario_rows.append(
            {
                "scenario": scenario.get("name"),
                "weight_not_probability": scenario.get("weight"),
                "fair_value": fair,
                "return_from_today": fair / current - 1 if fair is not None and current else None,
                "model_values": scenario.get("model_values"),
            }
        )
    if scenario_rows:
        st.dataframe(pd.DataFrame(scenario_rows), use_container_width=True, hide_index=True)
else:
    st.warning(
        f"UNRESOLVED: agreement={valuation.get('model_agreement')}, base-value ratio={valuation.get('model_base_ratio')}x. "
        "No blended fair value and no buy-below price are treated as actionable."
    )
    ranges = valuation.get("model_ranges", {}) or {}
    if ranges:
        st.dataframe(
            pd.DataFrame(
                [
                    {"scenario": name, "low_model_value": values.get("low"), "mid_reference_only": values.get("mid"), "high_model_value": values.get("high")}
                    for name, values in ranges.items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

if valuation.get("models"):
    with st.expander("See each independent valuation model and its assumptions"):
        for model in valuation.get("models", []):
            st.markdown(f"**{model.get('name')}** ({model.get('family')})")
            model_rows = [
                {
                    "scenario": x.get("name"),
                    "fair_value": x.get("fair_value"),
                    "assumptions": json.dumps(x.get("assumptions", {})),
                }
                for x in model.get("scenarios", [])
            ]
            st.dataframe(pd.DataFrame(model_rows), use_container_width=True, hide_index=True)

left, right = st.columns(2)
with left:
    st.subheader("Evidence supporting the thesis")
    for item in report.get("why_buy", []):
        st.write("•", item)
    st.subheader("What must be true")
    for item in report.get("what_must_be_true", []):
        st.write("•", item)
with right:
    st.subheader("Reasons not to buy")
    for item in report.get("why_not", []):
        st.write("•", item)
    st.subheader("Thesis invalidation")
    for item in report.get("invalidation", []):
        st.write("•", item)

st.subheader("Data trust and optional SEC diagnostics")
trust_rows = pd.DataFrame(trust.get("checks", []))
if not trust_rows.empty:
    st.dataframe(trust_rows, use_container_width=True, hide_index=True)
sec_status = report.get("sec_status", {}) or {}
st.write(
    f"SEC state: **{sec_status.get('state')}** | submissions OK: **{sec_status.get('submission_ok')}** | "
    f"requested: **{sec_status.get('documents_requested')}** | cached: **{sec_status.get('documents_cached')}** | "
    f"downloaded this run: **{sec_status.get('documents_downloaded')}**"
)
for error in sec_status.get("errors", [])[:8]:
    st.info(f"Optional SEC: {error}")
for flag in trust.get("critical_flags", []):
    st.error(flag)
for warning in trust.get("warnings", [])[:8]:
    st.warning(warning)

st.subheader("Optional SEC filing evidence")
if report.get("filing_evidence"):
    for i, evidence in enumerate(report.get("filing_evidence", [])[:18], 1):
        with st.expander(f"{i}. {evidence.get('form')} {evidence.get('filing_date')} — {evidence.get('topic')} / {evidence.get('tone')}"):
            st.write(evidence.get("text"))
            if evidence.get("source_url"):
                st.markdown(f"[Open SEC filing]({evidence['source_url']})")
else:
    st.info("No SEC filing evidence is cached for this ticker. That is acceptable in V5.3: SEC is optional enrichment and does not block BUY/WATCH decisions.")

if report.get("llm_research_note"):
    st.subheader("Optional AI evidence synthesis")
    st.write(report.get("llm_research_note"))

st.divider()
st.subheader("V5 realized track record")
st.write(
    "Scenario weights are not probabilities. The only probability-like evidence that matters over time is the realized forward record of prior actions. "
    "This table remains explicitly immature until enough 90/180/365-day observations accumulate."
)
if track.get("summaries"):
    st.dataframe(pd.DataFrame(track.get("summaries")), use_container_width=True, hide_index=True)
else:
    st.info("No mature forward-return observations yet.")

st.caption(
    f"Generated {meta.get('generated_at', 'unknown')}. GitHub Actions publishes the data; opening Streamlit does not redownload market data."
)
