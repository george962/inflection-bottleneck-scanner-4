from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "published/latest_research.json"
META = ROOT / "published/metadata.json"


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


st.set_page_config(page_title="Automated Equity Research", layout="wide")
st.title("Automated Equity Research")
st.caption(
    "Established-company discovery → data trust checks → multi-model scenario valuation → conservative BUY / WATCH / PASS."
)

if not LATEST.exists():
    st.info("No published research yet. Run `inflection-scanner research` or the GitHub Actions workflow.")
    st.stop()

reports = json.loads(LATEST.read_text(encoding="utf-8"))
meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}

rows = []
for report in reports:
    valuation = report.get("valuation", {})
    decision = report.get("decision", {})
    metrics = report.get("metrics", {})
    discovery = report.get("discovery", {})
    trust = report.get("trust", {})
    scenarios = {x.get("name"): x for x in valuation.get("scenarios", [])}
    rows.append(
        {
            "ticker": report.get("ticker"),
            "company": report.get("company"),
            "decision": decision.get("decision"),
            "confidence": decision.get("evidence_confidence") or decision.get("confidence"),
            "trust_grade": trust.get("trust_grade"),
            "trust_score": trust.get("trust_score"),
            "risk_tier": trust.get("risk_tier"),
            "market_cap_b": market_cap_b(trust.get("market_cap")),
            "years_public": trust.get("years_public"),
            "analysts": trust.get("analyst_count"),
            "current_price": metrics.get("price"),
            "bear_fair": scenarios.get("Bear", {}).get("fair_value"),
            "base_fair": scenarios.get("Base", {}).get("fair_value"),
            "bull_fair": scenarios.get("Bull", {}).get("fair_value"),
            "expected_cagr": valuation.get("expected_cagr"),
            "base_cagr": valuation.get("base_cagr"),
            "bear_return": valuation.get("bear_return"),
            "scenario_support": valuation.get("scenario_support_weight"),
            "models": valuation.get("model_count"),
            "model_agreement": valuation.get("model_agreement"),
            "critical_flags": len(trust.get("critical_flags", [])),
            "price_stage": discovery.get("price_stage"),
            "return_12m": metrics.get("return_12m"),
        }
    )

df = pd.DataFrame(rows)

decision_options = [
    "BUY",
    "SMALL BUY / SPECULATIVE",
    "WATCH",
    "TOO LATE",
    "REVIEW DATA",
    "SPECULATIVE WATCH",
    "PASS",
]
selected_decisions = st.sidebar.multiselect(
    "Decision",
    decision_options,
    default=["BUY", "WATCH", "TOO LATE", "REVIEW DATA"],
)
risk_tiers = st.sidebar.multiselect(
    "Company risk tier",
    ["CORE", "MIDCAP", "SPECULATIVE"],
    default=["CORE"],
)
trust_grades = st.sidebar.multiselect(
    "Trust grade",
    ["A", "B", "C", "D"],
    default=["A", "B"],
)
min_market_cap = st.sidebar.slider("Minimum market cap ($B)", 0, 100, 10)
min_expected_cagr = st.sidebar.slider("Minimum scenario-weighted 3Y CAGR", -20, 50, 8) / 100.0

filtered = df.copy()
if selected_decisions:
    filtered = filtered[filtered.decision.isin(selected_decisions)]
if risk_tiers:
    filtered = filtered[filtered.risk_tier.isin(risk_tiers)]
if trust_grades:
    filtered = filtered[filtered.trust_grade.isin(trust_grades)]
filtered = filtered[filtered.market_cap_b.fillna(0) >= min_market_cap]
filtered = filtered[filtered.expected_cagr.fillna(-999) >= min_expected_cagr]

st.subheader("Decision table")
st.write(
    "**Default view is intentionally conservative:** CORE companies only, $10B+ market cap, long public history, meaningful analyst coverage, and trust grades A/B. "
    "A stock is not excluded merely because it already rose; late-stage names can still qualify if future value remains compelling."
)
st.info(
    "The upside numbers are **scenario valuation estimates, not predictions with known probabilities**. Bear/base/bull weights are fixed modeling weights. "
    "BUY is suppressed when the data or valuation fails sanity checks."
)

display_cols = [
    "ticker",
    "company",
    "decision",
    "confidence",
    "trust_grade",
    "trust_score",
    "risk_tier",
    "market_cap_b",
    "years_public",
    "analysts",
    "current_price",
    "base_fair",
    "expected_cagr",
    "base_cagr",
    "bear_return",
    "models",
    "model_agreement",
    "price_stage",
    "return_12m",
]
st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)

choices = filtered.ticker.tolist() or df.ticker.tolist()
ticker = st.selectbox("Research report", choices)
report = next(x for x in reports if x["ticker"] == ticker)
valuation = report.get("valuation", {})
decision = report.get("decision", {})
metrics = report.get("metrics", {})
discovery = report.get("discovery", {})
trust = report.get("trust", {})
scenarios = {x.get("name"): x for x in valuation.get("scenarios", [])}

if trust.get("critical_flags"):
    st.error("This company has critical data/valuation sanity flags. Do not rely on the modeled upside until they are resolved.")

top = st.columns(8)
top[0].metric("Decision", decision.get("decision"))
top[1].metric("Trust", f"{trust.get('trust_grade')} ({trust.get('trust_score')})")
mc = market_cap_b(trust.get("market_cap"))
top[2].metric("Market cap", f"${mc:,.1f}B" if mc is not None else "n/a")
top[3].metric("Years public", f"{trust.get('years_public'):.1f}" if trust.get("years_public") is not None else "n/a")
top[4].metric("Analysts", trust.get("analyst_count") if trust.get("analyst_count") is not None else "n/a")
top[5].metric("Current", money(metrics.get("price")))
top[6].metric("Base fair", money(scenarios.get("Base", {}).get("fair_value")))
top[7].metric("Expected CAGR", pct(valuation.get("expected_cagr")))

st.markdown(
    f"**Risk tier:** `{trust.get('risk_tier')}` &nbsp;&nbsp; "
    f"**Price stage:** `{discovery.get('price_stage')}` &nbsp;&nbsp; "
    f"**Maturity:** `{discovery.get('price_maturity')}` &nbsp;&nbsp; "
    f"**Type:** `{valuation.get('company_type')}` &nbsp;&nbsp; "
    f"**Valuation methods:** `{valuation.get('model_count')}` &nbsp;&nbsp; "
    f"**Model agreement:** `{valuation.get('model_agreement')}`"
)

st.subheader("How much upside is the model actually assuming?")
scenario_rows = []
for x in valuation.get("scenarios", []):
    current = metrics.get("price")
    scenario_rows.append(
        {
            "scenario": x.get("name"),
            "weight_not_probability": x.get("weight"),
            "fair_value": x.get("fair_value"),
            "return_from_today": x.get("fair_value") / current - 1 if x.get("fair_value") is not None and current else None,
            "model_values": x.get("model_values"),
        }
    )
if scenario_rows:
    st.dataframe(pd.DataFrame(scenario_rows), use_container_width=True, hide_index=True)
st.caption(valuation.get("reason", "Scenario valuation."))

if valuation.get("models"):
    with st.expander("See each independent valuation method"):
        for model in valuation["models"]:
            st.markdown(f"**{model.get('name')}**")
            model_rows = [
                {
                    "scenario": s.get("name"),
                    "fair_value": s.get("fair_value"),
                    "assumptions": json.dumps(s.get("assumptions", {})),
                }
                for s in model.get("scenarios", [])
            ]
            st.dataframe(pd.DataFrame(model_rows), use_container_width=True, hide_index=True)

left, right = st.columns(2)
with left:
    st.subheader("Why it may be worth buying")
    for item in report.get("why_buy", []):
        st.write("•", item)
    st.subheader("What would improve conviction")
    for item in report.get("what_changes_decision", []):
        st.write("•", item)
with right:
    st.subheader("Why NOT to buy / what can be wrong")
    for item in report.get("why_not", []):
        st.write("•", item)

st.subheader("Data trust")
trust_table = pd.DataFrame(trust.get("checks", []))
if not trust_table.empty:
    st.dataframe(trust_table, use_container_width=True, hide_index=True)

if trust.get("critical_flags"):
    st.markdown("**Critical flags**")
    for item in trust.get("critical_flags", []):
        st.error(item)
if trust.get("warnings"):
    st.markdown("**Warnings**")
    for item in trust.get("warnings", []):
        st.warning(item)

st.subheader("Source freshness")
freshness_rows = []
for source, info in report.get("source_freshness", {}).items():
    freshness_rows.append(
        {
            "source": source,
            "present": info.get("present"),
            "fetched_at": info.get("fetched_at"),
            "age_hours": info.get("age_hours"),
            "stale": info.get("stale"),
        }
    )
if freshness_rows:
    st.dataframe(pd.DataFrame(freshness_rows), use_container_width=True, hide_index=True)

st.subheader("SEC filing evidence")
if report.get("filing_evidence"):
    for i, evidence in enumerate(report["filing_evidence"][:16], 1):
        with st.expander(
            f"{i}. {evidence.get('form')} {evidence.get('filing_date')} — {evidence.get('topic')} / {evidence.get('tone')}"
        ):
            st.write(evidence.get("text"))
            if evidence.get("source_url"):
                st.markdown(f"[Open SEC filing]({evidence['source_url']})")
else:
    st.info("No cached SEC evidence. Set SEC_USER_AGENT in GitHub Actions secrets and run again.")

st.subheader("Recent cached news")
for news in report.get("news", [])[:10]:
    title = news.get("title") or "(untitled)"
    url = news.get("url")
    publisher = news.get("publisher")
    if url:
        st.markdown(f"- [{title}]({url}) — {publisher}")
    else:
        st.write(f"• {title} — {publisher}")

if report.get("llm_research_note"):
    st.subheader("Optional AI evidence synthesis")
    st.write(report["llm_research_note"])

st.divider()
st.caption(
    f"Published data generated: {meta.get('generated_at', 'unknown')}. The dashboard reads committed files only. "
    "The valuation is a research model—not a guaranteed forecast."
)
