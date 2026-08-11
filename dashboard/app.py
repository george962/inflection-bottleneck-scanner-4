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


st.set_page_config(page_title="Large-Cap Inflection Research v5.1", layout="wide")
st.title("Large-Cap Inflection Research v5.1")
st.caption(
    "Find established companies with improving fundamentals, then ask a harder question: "
    "is today's price actually inside a return-required buy zone?"
)

if not LATEST.exists():
    st.info(
        "No v5 research has been published yet. Run the GitHub Actions workflow "
        "`Equity Research Engine`, then refresh this page."
    )
    st.stop()

reports = json.loads(LATEST.read_text(encoding="utf-8"))
meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
track = json.loads(TRACK.read_text(encoding="utf-8")) if TRACK.exists() else {"summaries": [], "observations": []}

# A successful GitHub Action should never mean "the dashboard must crash".
# If upstream selection returns zero reports, explain it and stop cleanly.
if not isinstance(reports, list) or not reports:
    selection = meta.get("discovery_run", {}).get("research_selection", {}) or {}
    st.warning(
        "The latest research run produced **0 full research reports**. The dashboard is working; "
        "the upstream candidate gate returned no eligible large/established companies. "
        "V5.1 treats this as a pipeline/data-quality condition instead of raising a KeyError."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CORE candidates", selection.get("core_candidates", 0))
    c2.metric("MIDCAP candidates", selection.get("midcap_candidates", 0))
    c3.metric("Speculative candidates", selection.get("speculative_candidates", 0))
    c4.metric("Selected", selection.get("selected_for_research", 0))
    st.info(
        "Run the V5.1 GitHub Action after pushing the updated code. V5.1 refreshes Yahoo profile metadata "
        "and no longer treats a missing first-trade date as proof that a large company is small/new."
    )
    st.stop()

rows = []
for r in reports:
    c = r.get("conviction", {})
    v = r.get("valuation", {})
    t = r.get("trust", {})
    m = r.get("metrics", {})
    d = r.get("discovery", {})
    rows.append(
        {
            "ticker": r.get("ticker"),
            "company": r.get("company"),
            "action": c.get("action"),
            "conviction": c.get("conviction_score"),
            "risk_tier": t.get("risk_tier"),
            "size_class": t.get("size_class"),
            "market_cap_b": market_cap_b(t.get("market_cap")),
            "years_public": t.get("years_public"),
            "analysts": t.get("analyst_count"),
            "established_for_action": t.get("actionable_established"),
            "trust": t.get("trust_score"),
            "current": m.get("price"),
            "buy_below": c.get("buy_below_price"),
            "gap_to_buy_zone": c.get("gap_to_buy_zone"),
            "base_fair": c.get("base_fair_value"),
            "base_cagr": v.get("base_cagr"),
            "expected_cagr": v.get("expected_cagr"),
            "bear_return": v.get("bear_return"),
            "models": v.get("model_count"),
            "agreement": v.get("model_agreement"),
            "price_stage": d.get("price_stage"),
            "return_12m": m.get("return_12m"),
            "eps_revision_30d": m.get("eps_revision_30d"),
            "next_year_eps_growth": m.get("next_year_eps_growth"),
        }
    )

df = pd.DataFrame(rows)

st.sidebar.header("Default risk filter")
actions = st.sidebar.multiselect(
    "Action",
    ["BUY NOW", "BUY ON PULLBACK", "WATCH", "TOO LATE", "REVIEW DATA", "SPECULATIVE WATCH", "PASS"],
    default=["BUY NOW", "BUY ON PULLBACK", "WATCH", "TOO LATE"],
)
tiers = st.sidebar.multiselect("Company tier", ["CORE", "MIDCAP", "SPECULATIVE"], default=["CORE"])
min_market_cap = st.sidebar.slider("Minimum market cap ($B)", 0, 200, 25)
min_conviction = st.sidebar.slider("Minimum conviction", 0, 100, 55)

filtered = df.copy()
if actions:
    filtered = filtered[filtered["action"].isin(actions)]
if tiers:
    filtered = filtered[filtered["risk_tier"].isin(tiers)]
filtered = filtered[filtered["market_cap_b"].fillna(0) >= min_market_cap]
filtered = filtered[filtered["conviction"].fillna(0) >= min_conviction]

st.subheader("What deserves attention now?")
st.write(
    "The default view intentionally avoids tiny/new companies. CORE targets approximately **$15B+ market cap, "
    "$50M+ average daily dollar volume, and established-history / analyst evidence**. Missing Yahoo age metadata is now a trust warning rather than an automatic small/new classification. "
    "Actionable **BUY NOW / BUY ON PULLBACK** recommendations additionally require the preferred **$25B+** large-cap tier. A stock can already have rallied and still appear, but it only earns **BUY NOW** if today's price meets the configured return hurdle."
)

show_cols = [
    "ticker",
    "company",
    "action",
    "conviction",
    "market_cap_b",
    "years_public",
    "analysts",
    "established_for_action",
    "trust",
    "current",
    "buy_below",
    "gap_to_buy_zone",
    "base_fair",
    "base_cagr",
    "expected_cagr",
    "bear_return",
    "models",
    "agreement",
    "price_stage",
    "return_12m",
]
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
discovery = report.get("discovery", {})

st.divider()
st.subheader(f"{ticker} — {report.get('company')}")

if conviction.get("action") == "BUY NOW":
    st.success(
        f"BUY NOW: current price {money(metrics.get('price'))} is inside the required-return buy zone "
        f"of {money(conviction.get('buy_below_price'))} or lower."
    )
elif conviction.get("action") == "BUY ON PULLBACK":
    st.warning(
        f"BUY ON PULLBACK: the research case may be strong, but today’s price does not meet the "
        f"{pct(conviction.get('required_base_cagr'))} base-case CAGR hurdle. Buy-zone price: "
        f"{money(conviction.get('buy_below_price'))} or lower."
    )
elif conviction.get("action") == "REVIEW DATA":
    st.error("REVIEW DATA: at least one data or valuation sanity check failed. Do not trust the upside estimate yet.")
else:
    st.info(f"{conviction.get('action')}: {conviction.get('rationale')}")

hero = st.columns(8)
hero[0].metric("Action", conviction.get("action"))
hero[1].metric("Conviction", conviction.get("conviction_score"))
hero[2].metric("Market cap", f"${market_cap_b(trust.get('market_cap')):,.1f}B" if market_cap_b(trust.get("market_cap")) is not None else "n/a")
hero[3].metric("Years public", f"{trust.get('years_public'):.1f}" if trust.get("years_public") is not None else "n/a")
hero[4].metric("Analysts", trust.get("analyst_count") if trust.get("analyst_count") is not None else "n/a")
hero[5].metric("Current", money(metrics.get("price")))
hero[6].metric("Buy below", money(conviction.get("buy_below_price")))
hero[7].metric("Base fair", money(conviction.get("base_fair_value")))

st.caption(
    f"Tier: {trust.get('risk_tier')} / {trust.get('size_class')} | Trust: {trust.get('trust_grade')} ({trust.get('trust_score')}) | "
    f"Price stage: {discovery.get('price_stage')} | Valuation methods: {valuation.get('model_count')} | "
    f"Model agreement: {valuation.get('model_agreement')}"
)

st.subheader("Why should I believe this one more than a random screener result?")
pillars = conviction.get("pillars", {})
pillar_cols = st.columns(6)
labels = [
    ("Fundamentals", "fundamental_inflection"),
    ("Revisions", "estimate_revision"),
    ("Valuation", "valuation"),
    ("Timing", "price_timing"),
    ("Company quality", "company_quality"),
    ("Evidence", "evidence"),
]
for col, (label, key) in zip(pillar_cols, labels):
    col.metric(label, pillars.get(key))

check_rows = [
    {"condition": name.replace("_", " ").title(), "pass": status_icon(passed)}
    for name, passed in conviction.get("checks", {}).items()
]
if check_rows:
    st.dataframe(pd.DataFrame(check_rows), use_container_width=True, hide_index=True)

st.subheader("Valuation: buy zone, not just an upside target")
st.write(
    f"Base fair value is **{money(conviction.get('base_fair_value'))}**. "
    f"To demand at least **{pct(conviction.get('required_base_cagr'))} annualized** in the base case over "
    f"{valuation.get('horizon_years', 3)} years, v5 calculates a maximum buy-zone price of "
    f"**{money(conviction.get('buy_below_price'))}**."
)

scenarios = []
current = metrics.get("price")
for s in valuation.get("scenarios", []):
    fv = s.get("fair_value")
    scenarios.append(
        {
            "scenario": s.get("name"),
            "model_weight_not_probability": s.get("weight"),
            "fair_value": fv,
            "return_from_today": fv / current - 1 if fv is not None and current else None,
            "model_values": s.get("model_values"),
        }
    )
if scenarios:
    st.dataframe(pd.DataFrame(scenarios), use_container_width=True, hide_index=True)
st.caption(
    "Bear/base/bull weights are modeling weights, not measured probabilities. The fair values are triangulated from available valuation methods."
)

if valuation.get("models"):
    with st.expander("See the independent valuation methods and assumptions"):
        for model in valuation.get("models", []):
            st.markdown(f"**{model.get('name')}**")
            rows = [
                {
                    "scenario": x.get("name"),
                    "fair_value": x.get("fair_value"),
                    "assumptions": json.dumps(x.get("assumptions", {})),
                }
                for x in model.get("scenarios", [])
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

left, right = st.columns(2)
with left:
    st.subheader("Evidence supporting the case")
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

st.subheader("Data trust")
trust_rows = pd.DataFrame(trust.get("checks", []))
if not trust_rows.empty:
    st.dataframe(trust_rows, use_container_width=True, hide_index=True)
for flag in trust.get("critical_flags", []):
    st.error(flag)
for warning in trust.get("warnings", [])[:8]:
    st.warning(warning)

st.subheader("SEC filing evidence")
if report.get("filing_evidence"):
    for i, e in enumerate(report.get("filing_evidence", [])[:18], 1):
        with st.expander(f"{i}. {e.get('form')} {e.get('filing_date')} — {e.get('topic')} / {e.get('tone')}"):
            st.write(e.get("text"))
            if e.get("source_url"):
                st.markdown(f"[Open SEC filing]({e['source_url']})")
else:
    st.info("No cached SEC evidence for this ticker.")

if report.get("llm_research_note"):
    st.subheader("Optional AI evidence synthesis")
    st.write(report.get("llm_research_note"))

st.divider()
st.subheader("V5 track record")
st.write(
    "This section is deliberately separate from the scenario model. As v5 runs over time, it records what actually happened after each prior "
    "BUY NOW / BUY ON PULLBACK / WATCH decision. Until enough observations accumulate, it explicitly says the history is insufficient."
)
summary_rows = track.get("summaries", [])
if summary_rows:
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
else:
    st.info("No mature v5 forward-return observations yet. The first 90-day outcomes will appear after enough time has passed.")

st.caption(
    f"Generated {meta.get('generated_at', 'unknown')}. Dashboard data is published by GitHub Actions; opening Streamlit does not rerun market-data downloads."
)
