from __future__ import annotations
from datetime import datetime,timezone
from .llm_research import synthesize_with_openai
from .research_evidence import extract_filing_evidence,summarize_evidence
from .valuation import build_valuation,finite,make_decision
def _pct(v):
    x=finite(v);return "n/a" if x is None else f"{x:.1%}"
def _risk(profile,summary):
    p=0;debt=finite(profile.get("total_debt"));cash=finite(profile.get("total_cash"));mc=finite(profile.get("market_cap"))
    if mc and debt is not None:
        nd=(debt-(cash or 0))/mc
        if nd>.6:p+=.03
        elif nd>.3:p+=.015
    if summary.get("negative_count",0)>=summary.get("positive_count",0)+4:p+=.02
    return min(p,.06)
def _metrics(s):
    f=s.get("features",{});p=s.get("profile",{});sc=s.get("scores",{});a=s.get("assessment",{})
    keys=["price","return_1m","return_3m","return_6m","return_12m","revenue_yoy","revenue_acceleration","gross_margin_change_yoy","operating_margin_change_yoy","incremental_operating_margin_yoy","eps_revision_30d","eps_revision_90d","next_year_eps_estimate","next_year_eps_growth","next_year_revenue_estimate","next_year_revenue_growth_estimate"]
    out={k:f.get(k) for k in keys};out.update({"price_stage":a.get("price_stage"),"price_maturity":sc.get("price_maturity"),"market_cap":p.get("market_cap"),"forward_pe":p.get("forward_pe"),"price_to_sales":p.get("price_to_sales"),"enterprise_to_ebitda":p.get("enterprise_to_ebitda"),"analyst_target_upside":sc.get("analyst_target_upside"),"data_quality":s.get("data_quality")});return out
def _bullets(s,val,summary):
    f=s.get("features",{});p=s.get("profile",{});sc=s.get("scores",{});buy=[];avoid=[];watch=[]
    e30=finite(f.get("eps_revision_30d"));acc=finite(f.get("revenue_acceleration"));eg=finite(f.get("next_year_eps_growth"));rg=finite(f.get("next_year_revenue_growth_estimate"));fpe=finite(p.get("forward_pe"));mat=finite(sc.get("price_maturity")) or 0;cagr=finite(val.get("expected_cagr"));down=finite(val.get("bear_downside"))
    if e30 is not None and e30>=.05:buy.append(f"EPS consensus rose {_pct(e30)} over 30 days.")
    if acc is not None and acc>=.05:buy.append(f"Revenue growth accelerated {acc*100:+.1f} percentage points.")
    if eg is not None and eg>=.2:buy.append(f"Consensus next-year EPS growth is {_pct(eg)}.")
    if rg is not None and rg>=.15:buy.append(f"Consensus next-year revenue growth is {_pct(rg)}.")
    if cagr is not None and cagr>=.15:buy.append(f"Scenario-weighted valuation implies about {_pct(cagr)} annualized return over the model horizon.")
    if mat<40:buy.append("The stock has not yet reached the model's late-stage price-maturity threshold.")
    if mat>=75:avoid.append("The stock has already rerated materially; future earnings must keep outrunning expectations.")
    if down is not None and down<=-.4:avoid.append(f"Bear scenario implies approximately {_pct(down)} downside.")
    if fpe is not None and fpe>=45:avoid.append(f"Forward P/E is approximately {fpe:.1f}x.")
    if e30 is not None and e30<0:avoid.append(f"30-day EPS revisions are negative at {_pct(e30)}.")
    if acc is not None and acc<0:avoid.append(f"Revenue growth is decelerating {acc*100:+.1f} percentage points.")
    if summary.get("negative_count",0)>summary.get("positive_count",0):avoid.append("Recent SEC filing snippets contain more negative than positive keyword evidence; inspect the cited passages.")
    if e30 is None:watch.append("Obtain a reliable recent EPS-revision history.")
    elif e30<=0:watch.append("30-day EPS revisions turn positive.")
    if acc is None or acc<=0:watch.append("A future quarter confirms positive revenue-growth acceleration.")
    watch.append("Re-run after the next earnings report; cached financials refresh automatically after their TTL.")
    if not buy:buy.append("No single strong generic buy factor passed the configured threshold.")
    if not avoid:avoid.append("No generic red flag passed the configured threshold; company-specific risks still require filing review.")
    return buy[:7],avoid[:7],watch[:6]
def research_one(snapshot,yahoo,sec,warehouse,research_cfg,llm_cfg):
    ticker=snapshot["ticker"];asof=datetime.now(timezone.utc).isoformat(timespec="seconds");annual=yahoo.annual_financials(ticker);news=yahoo.news(ticker,int(research_cfg.get("news_items_per_ticker",12)))
    filings=sec.ensure_recent_documents(ticker,list(research_cfg.get("filing_forms",["10-K","10-Q","8-K"])),int(research_cfg.get("filing_documents_per_ticker",5)),int(research_cfg.get("filing_text_max_chars",300000))) if sec.available else warehouse.recent_filings(ticker,int(research_cfg.get("filing_documents_per_ticker",5)))
    evidence=extract_filing_evidence(filings);summary=summarize_evidence(evidence)
    val=build_valuation(snapshot.get("profile",{}),snapshot.get("features",{}),annual,int(research_cfg.get("horizon_years",3)))
    decision=make_decision(val,snapshot.get("scores",{}),float(snapshot.get("data_quality") or 0),dict(research_cfg.get("decision_thresholds",{})),_risk(snapshot.get("profile",{}),summary))
    why,why_not,changes=_bullets(snapshot,val,summary)
    report={"asof":asof,"ticker":ticker,"company":snapshot.get("company"),"sector":snapshot.get("sector"),"industry":snapshot.get("industry"),"source":snapshot.get("source"),
            "discovery":{"potential_score":snapshot.get("scores",{}).get("total"),"discovery_bucket":snapshot.get("features",{}).get("discovery_bucket"),"price_stage":snapshot.get("assessment",{}).get("price_stage"),"price_maturity":snapshot.get("scores",{}).get("price_maturity")},
            "metrics":_metrics(snapshot),"valuation":val,"decision":decision,"why_buy":why,"why_not":why_not,"what_changes_decision":changes,
            "filing_evidence_summary":summary,"filing_evidence":evidence[:24],"news":news,
            "cache_note":"Prices, financial statements, analyst data, news, and SEC filings are cached. Immutable SEC filing documents are not downloaded again once stored."}
    report["llm_research_note"]=synthesize_with_openai(report,str(llm_cfg.get("model","gpt-5-mini"))) if llm_cfg.get("enabled_if_key_present",True) else None
    warehouse.put_research_report(ticker,asof,decision.get("decision","WATCH"),val.get("expected_cagr"),report);return report
