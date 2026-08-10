from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import streamlit as st
ROOT=Path(__file__).resolve().parents[1];LATEST=ROOT/"published/latest_research.json";META=ROOT/"published/metadata.json"
st.set_page_config(page_title="Automated Equity Research",layout="wide")
st.title("Automated Equity Research")
st.caption("Broad discovery → cached filings/fundamentals → scenario valuation → BUY / WATCH / PASS.")
if not LATEST.exists():
    st.info("No published research yet. Run `inflection-scanner research` or the GitHub Actions workflow. This dashboard itself makes no Yahoo/SEC requests.");st.stop()
reports=json.loads(LATEST.read_text());meta=json.loads(META.read_text()) if META.exists() else {}
rows=[]
for r in reports:
    v=r.get("valuation",{});d=r.get("decision",{});m=r.get("metrics",{});disc=r.get("discovery",{})
    rows.append({"ticker":r.get("ticker"),"company":r.get("company"),"decision":d.get("decision"),"confidence":d.get("confidence"),
                 "current_price":m.get("price"),"expected_value_3y":v.get("expected_value"),"expected_cagr":v.get("expected_cagr"),
                 "probability_profit":v.get("probability_profit"),"bear_downside":v.get("bear_downside"),"price_stage":disc.get("price_stage"),
                 "price_maturity":disc.get("price_maturity"),"company_type":v.get("company_type"),"forward_pe":m.get("forward_pe"),
                 "next_year_eps_growth":m.get("next_year_eps_growth"),"eps_revision_30d":m.get("eps_revision_30d"),"return_12m":m.get("return_12m")})
df=pd.DataFrame(rows)
selected=st.sidebar.multiselect("Decision",["BUY","SMALL BUY / SPECULATIVE","WATCH","TOO LATE","PASS"],default=["BUY","SMALL BUY / SPECULATIVE","WATCH"])
minc=st.sidebar.slider("Minimum expected 3Y CAGR",-20,50,8)/100;minp=st.sidebar.slider("Minimum scenario P(profit)",0,100,50)/100
f=df.copy()
if selected:f=f[f.decision.isin(selected)]
f=f[(f.expected_cagr.fillna(-999)>=minc)&(f.probability_profit.fillna(0)>=minp)]
st.subheader("Decision table")
st.write("A stock is **not excluded** because it already rose. Late-stage stocks remain eligible, but must still offer enough forward return from today's price to earn BUY.")
cols=["ticker","company","decision","confidence","current_price","expected_value_3y","expected_cagr","probability_profit","bear_downside","price_stage","price_maturity","company_type","forward_pe","next_year_eps_growth","eps_revision_30d","return_12m"]
st.dataframe(f[cols],use_container_width=True,hide_index=True)
choices=f.ticker.tolist() or df.ticker.tolist();ticker=st.selectbox("Research report",choices);r=next(x for x in reports if x["ticker"]==ticker)
v=r.get("valuation",{});d=r.get("decision",{});m=r.get("metrics",{});disc=r.get("discovery",{})
cs=st.columns(6);cs[0].metric("Decision",d.get("decision"));cs[1].metric("Confidence",d.get("confidence"))
cs[2].metric("Current",f"${m.get('price'):,.2f}" if m.get("price") is not None else "n/a")
cs[3].metric("Expected 3Y",f"${v.get('expected_value'):,.2f}" if v.get("expected_value") is not None else "n/a")
cs[4].metric("Expected CAGR",f"{v.get('expected_cagr'):.1%}" if v.get("expected_cagr") is not None else "n/a")
cs[5].metric("Bear downside",f"{v.get('bear_downside'):.1%}" if v.get("bear_downside") is not None else "n/a")
st.markdown(f"**Price stage:** `{disc.get('price_stage')}` &nbsp;&nbsp; **Maturity:** `{disc.get('price_maturity')}` &nbsp;&nbsp; **Type:** `{v.get('company_type')}` &nbsp;&nbsp; **Valuation:** `{v.get('model')}`")
sr=[{"scenario":x.get("name"),"probability":x.get("probability"),"fair_value":x.get("fair_value"),"assumptions":json.dumps(x.get("assumptions",{}))} for x in v.get("scenarios",[])]
st.subheader("Bear / base / bull valuation")
if sr:st.dataframe(pd.DataFrame(sr),use_container_width=True,hide_index=True);st.caption(v.get("reason"))
else:st.warning(v.get("reason","No generic valuation available."))
lft,rgt=st.columns(2)
with lft:
    st.subheader("Why buy")
    for x in r.get("why_buy",[]):st.write("•",x)
    st.subheader("What would change the decision")
    for x in r.get("what_changes_decision",[]):st.write("•",x)
with rgt:
    st.subheader("Why NOT to buy")
    for x in r.get("why_not",[]):st.write("•",x)
    st.subheader("Key metrics")
    st.dataframe(pd.DataFrame([{"metric":k,"value":v} for k,v in m.items() if v is not None]),use_container_width=True,hide_index=True)
st.subheader("SEC filing evidence")
if r.get("filing_evidence"):
    for i,e in enumerate(r["filing_evidence"][:16],1):
        with st.expander(f"{i}. {e.get('form')} {e.get('filing_date')} — {e.get('topic')} / {e.get('tone')}"):
            st.write(e.get("text"))
            if e.get("source_url"):st.markdown(f"[Open SEC filing]({e['source_url']})")
else:st.info("No cached SEC evidence. Set SEC_USER_AGENT in GitHub Actions secrets and run again.")
st.subheader("Recent cached news")
for n in r.get("news",[])[:10]:
    title=n.get("title") or "(untitled)";url=n.get("url");pub=n.get("publisher")
    st.markdown(f"- [{title}]({url}) — {pub}" if url else f"- {title} — {pub}")
if r.get("llm_research_note"):st.subheader("Optional AI evidence synthesis");st.write(r["llm_research_note"])
st.divider();st.caption(f"Published data generated: {meta.get('generated_at','unknown')}. The dashboard reads committed files only and does not redownload market data when opened.")
