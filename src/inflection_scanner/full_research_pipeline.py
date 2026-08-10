from __future__ import annotations
import csv,json
from datetime import datetime,timezone
from .discovery_pipeline import run_discovery
from .providers.cached_yahoo import CachedYahooProvider
from .providers.sec_research import CachedSecResearchProvider
from .research_engine import research_one
from .warehouse import ResearchWarehouse

ORDER={"BUY":0,"SMALL BUY / SPECULATIVE":1,"WATCH":2,"TOO LATE":3,"PASS":4}
def _key(r):
    d=r.get("decision",{}).get("decision","WATCH");c=r.get("valuation",{}).get("expected_cagr");return (ORDER.get(d,5),-(float(c) if c is not None else -999))
def _publish(reports,settings,meta):
    pub=settings.published_dir;pub.mkdir(parents=True,exist_ok=True);reports=sorted(reports,key=_key)
    jp=pub/"latest_research.json";jp.write_text(json.dumps(reports,indent=2,default=str,allow_nan=False),encoding="utf-8")
    rows=[]
    for r in reports:
        v=r.get("valuation",{});d=r.get("decision",{});m=r.get("metrics",{});disc=r.get("discovery",{})
        rows.append({"ticker":r.get("ticker"),"company":r.get("company"),"decision":d.get("decision"),"confidence":d.get("confidence"),
            "current_price":m.get("price"),"expected_value_3y":v.get("expected_value"),"expected_cagr":v.get("expected_cagr"),"base_cagr":v.get("base_cagr"),
            "probability_profit":v.get("probability_profit"),"bear_downside":v.get("bear_downside"),"company_type":v.get("company_type"),"valuation_model":v.get("model"),
            "potential_score":disc.get("potential_score"),"price_stage":disc.get("price_stage"),"price_maturity":disc.get("price_maturity"),
            "forward_pe":m.get("forward_pe"),"next_year_eps_growth":m.get("next_year_eps_growth"),"eps_revision_30d":m.get("eps_revision_30d"),"return_12m":m.get("return_12m")})
    cp=pub/"latest_research.csv"
    if rows:
        with cp.open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    else:cp.write_text("",encoding="utf-8")
    md={"generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),"version":"0.4.0","reports":len(reports),"discovery_run":meta,
        "note":"Small published payload is committed for Streamlit; large warehouse stays out of git and is restored via Actions cache."}
    mp=pub/"metadata.json";mp.write_text(json.dumps(md,indent=2,default=str),encoding="utf-8")
    return {"published_json":jp,"published_csv":cp,"published_metadata":mp}
def run_full_research(settings,deep_candidates=100,research_candidates=20,top_n=30,refresh_universe=False,max_universe=None,force_refresh=False,offline=False,progress_callback=None):
    snaps,meta=run_discovery(settings,deep_candidates,top_n,refresh_universe,max_universe,force_refresh,offline,progress_callback)
    ok=sorted([s for s in snaps if not s.get("error")],key=lambda x:x.get("scores",{}).get("total",-1),reverse=True)
    early=[s for s in ok if s.get("assessment",{}).get("price_stage")!="LATE"];late=[s for s in ok if s.get("assessment",{}).get("price_stage")=="LATE"]
    late_slots=min(max(2,research_candidates//4),len(late));chosen=early[:max(0,research_candidates-late_slots)]+late[:late_slots]
    wh=ResearchWarehouse(settings.warehouse_path);y=CachedYahooProvider(wh,settings.cache_ttl_hours,settings.request_pause_seconds,offline)
    sec=CachedSecResearchProvider(wh,float(settings.cache_ttl_hours.get("sec_submissions",12)),offline=offline);reports=[]
    for i,s in enumerate(chosen,1):
        if progress_callback:progress_callback("research",i,len(chosen),s["ticker"])
        reports.append(research_one(s,y,sec,wh,settings.research,settings.llm))
    info=wh.cache_info();wh.close()
    pub=_publish(reports,settings,{"run_id":meta.get("run_id"),"universe_count":meta.get("universe_count"),"price_scan_count":meta.get("price_scan_count"),
        "seed_count":meta.get("seed_count"),"market_stats":meta.get("market_stats"),"warehouse":info})
    meta["research_count"]=len(reports);meta["published"]=pub;meta["warehouse_after_research"]=info
    return reports,meta
