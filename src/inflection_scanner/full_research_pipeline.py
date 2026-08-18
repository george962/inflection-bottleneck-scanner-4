from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import MODEL_VERSION
from .build_info import source_hash
from .config import config_hash
from .ledger import decision_row, merge_jsonl, pit_row
from .performance import build_track_record
from .research_engine import ResearchEngine


def select_research_candidates(discovery: dict[str, Any], count: int) -> list[str]:
    candidates=discovery.get("candidates",[])
    # Preserve a mixture of early/mid opportunity names and strong late diagnostics.
    early=[x for x in candidates if x.get("price_stage")!="LATE"]
    late=[x for x in candidates if x.get("price_stage")=="LATE"]
    nlate=min(len(late),max(0,round(count*.2))); main=early[:max(0,count-nlate)]; selected=main+late[:nlate]
    if len(selected)<count:
        used={x["ticker"] for x in selected}; selected.extend(x for x in candidates if x["ticker"] not in used and len(selected)<count)
    return [x["ticker"] for x in selected[:count]]


def run_full_research(provider,warehouse,cfg,discovery,security_overrides=None,research_count=None,published_dir="published",force_refresh=False):
    count=int(research_count or cfg.get("research",{}).get("research_candidates",24)); tickers=select_research_candidates(discovery,count); engine=ResearchEngine(provider,warehouse,cfg,security_overrides)
    reports=[]
    for ticker in tickers:
        try: reports.append(engine.research(ticker,force_refresh=force_refresh))
        except Exception as exc:
            reports.append({"model_version":MODEL_VERSION,"asof":datetime.now(timezone.utc).isoformat(timespec="seconds"),"ticker":ticker,"company":ticker,"metrics":{},"valuation":{"valuation_status":"DATA_ERROR","valuation_resolved":False},"trust":{"trust_grade":"D","trust_score":0,"critical_flags":[f"Research failed: {exc.__class__.__name__}"]},"conviction":{"action":"REVIEW DATA","conviction_score":0,"thesis_score":0,"entry_score":0,"pillars":{},"rationale":"Research pipeline failed safely."},"decision":{"decision":"REVIEW DATA","confidence":"LOW","reason":"Research pipeline failed safely."}})
    p=Path(published_dir); p.mkdir(parents=True,exist_ok=True); ch=config_hash(cfg); code_hash=source_hash()
    (p/"latest_research.json").write_text(json.dumps(reports,indent=2,default=str),encoding="utf-8")
    _write_csv(p/"latest_research.csv",reports)
    merge_jsonl(p/"decision_ledger.jsonl",[decision_row(x,ch,code_hash) for x in reports],("model_version","asof","ticker"))
    merge_jsonl(p/"pit_estimates.jsonl",[pit_row(x,ch,code_hash) for x in reports],("model_version","asof","ticker"))
    track=build_track_record(warehouse,cfg.get("research",{}).get("performance_horizons_days"),MODEL_VERSION,cfg.get("benchmark","SPY"),p/"decision_ledger.jsonl")
    (p/"track_record.json").write_text(json.dumps(track,indent=2),encoding="utf-8")
    meta={"generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"version":"0.5.4","model_version":MODEL_VERSION,"config_hash":ch,"code_hash":code_hash,"reports":len(reports),"discovery_run":{k:v for k,v in discovery.items() if k!="candidates"},"methodology":"V5.4 adds fail-closed currency/ADR normalization, corrected company-family classification, robust public-history parsing, durable point-in-time decision/estimate ledgers, and model-versioned benchmark-relative outcome tracking."}
    (p/"metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    return {"reports":reports,"metadata":meta,"track_record":track}


def _write_csv(path: Path,reports: list[dict[str,Any]]):
    fields=["ticker","company","action","conviction_score","thesis_score","entry_score","entry_state","risk_tier","size_class","market_cap","years_public","analyst_count","trust_grade","trust_score","current_price","buy_below_price","valuation_status","company_type","expected_cagr","base_cagr","bear_return","valuation_model_count","model_agreement","fundamental_pillar","revision_pillar","valuation_pillar","timing_pillar","quality_pillar","evidence_pillar","price_stage","price_maturity","return_6m","return_12m","distance_from_52w_high","forward_pe","next_year_eps_growth","eps_revision_30d"]
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in reports:
            c=r.get("conviction",{}); t=r.get("trust",{}); m=r.get("metrics",{}); v=r.get("valuation",{}); p=c.get("pillars",{}); e=c.get("entry_timing",{})
            w.writerow({"ticker":r.get("ticker"),"company":r.get("company"),"action":c.get("action"),"conviction_score":c.get("conviction_score"),"thesis_score":c.get("thesis_score"),"entry_score":c.get("entry_score"),"entry_state":e.get("entry_state"),"risk_tier":t.get("risk_tier"),"size_class":t.get("size_class"),"market_cap":t.get("market_cap"),"years_public":t.get("years_public"),"analyst_count":t.get("analyst_count"),"trust_grade":t.get("trust_grade"),"trust_score":t.get("trust_score"),"current_price":m.get("price"),"buy_below_price":c.get("buy_below_price"),"valuation_status":v.get("valuation_status"),"company_type":v.get("company_type"),"expected_cagr":v.get("expected_cagr"),"base_cagr":v.get("base_cagr"),"bear_return":v.get("bear_return"),"valuation_model_count":v.get("model_count"),"model_agreement":v.get("model_agreement"),"fundamental_pillar":p.get("fundamental_inflection"),"revision_pillar":p.get("estimate_revision"),"valuation_pillar":p.get("valuation"),"timing_pillar":p.get("price_timing"),"quality_pillar":p.get("company_quality"),"evidence_pillar":p.get("evidence"),"price_stage":m.get("price_stage"),"price_maturity":m.get("price_maturity"),"return_6m":m.get("return_6m"),"return_12m":m.get("return_12m"),"distance_from_52w_high":m.get("distance_from_52w_high"),"forward_pe":m.get("forward_pe"),"next_year_eps_growth":m.get("next_year_eps_growth"),"eps_revision_30d":m.get("eps_revision_30d")})
