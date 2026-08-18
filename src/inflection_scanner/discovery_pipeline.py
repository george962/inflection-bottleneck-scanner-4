from __future__ import annotations
from typing import Any
import pandas as pd
from .config import Settings
from .db import Database
from .discovery import compute_price_discovery_features,select_deep_candidates
from .market_store import update_market_history
from .pipeline import assess_snapshot,scan_one
from .providers.cached_yahoo import CachedYahooProvider
from .providers.universe import fetch_us_listed_equities
from .report import write_reports
from .warehouse import ResearchWarehouse

def run_discovery(settings:Settings,deep_candidates=None,top_n=None,refresh_universe=False,max_universe=None,force_refresh=False,offline=False,progress_callback=None):
    cfg=settings.discovery;settings.output_dir.mkdir(parents=True,exist_ok=True);wh=ResearchWarehouse(settings.warehouse_path)
    cache_dir=settings.warehouse_path.parent/"cache"; cache_file=cache_dir/"us_listed_equities.csv";
    if offline and not cache_file.exists():
        wh.close(); raise RuntimeError("--offline requires a previously cached U.S.-listed universe. Run online once first.")
    universe=fetch_us_listed_equities(cache_dir=cache_dir,cache_hours=float(cfg.get("universe_cache_hours",24)),refresh=refresh_universe and not offline)
    if max_universe and max_universe>0:universe=universe.head(max_universe).copy()
    symbols=universe["yahoo_symbol"].dropna().astype(str).tolist()
    market=update_market_history(wh,symbols,float(cfg.get("market_refresh_hours",14)),str(cfg.get("initial_price_period","2y")),
        str(cfg.get("incremental_price_period","10d")),int(cfg.get("batch_size",100)),float(cfg.get("batch_pause_seconds",.3)),force_refresh,offline,progress_callback)
    rows=[]
    for i,ticker in enumerate(symbols,1):
        feat=compute_price_discovery_features(wh.load_prices(ticker,600))
        if feat:rows.append({"ticker":ticker,**feat})
        if progress_callback and i%1000==0:progress_callback("features",i,len(symbols),len(rows))
    scan=pd.DataFrame(rows)
    if scan.empty:
        wh.close();raise RuntimeError("No usable cached/updated price history. Run online once before --offline.")
    scan.merge(universe[["yahoo_symbol","symbol","name","exchange"]],left_on="ticker",right_on="yahoo_symbol",how="left").to_csv(settings.output_dir/"universe_price_scan.csv",index=False)
    deep_n=int(deep_candidates or cfg.get("deep_candidates",100))
    seeds=select_deep_candidates(
        scan,
        float(cfg.get("min_price", 5)),
        float(cfg.get("min_dollar_volume_20d", 20_000_000)),
        int(cfg.get("min_history_days", 220)),
        deep_n,
        int(cfg.get("bucket_size", 100)),
        float(cfg.get("max_late_fraction", 0.40)),
        float(cfg.get("liquid_challenger_fraction", 0.55)),
    )
    seeds.merge(universe[["yahoo_symbol","symbol","name","exchange"]],left_on="ticker",right_on="yahoo_symbol",how="left").to_csv(settings.output_dir/"discovery_seed_candidates.csv",index=False)
    yahoo=CachedYahooProvider(wh,settings.cache_ttl_hours,settings.request_pause_seconds,offline)
    bench=wh.load_prices(settings.benchmark,600)
    if bench.empty and not offline:
        bench=yahoo.live.history(settings.benchmark,settings.price_period);wh.upsert_prices(settings.benchmark,bench)
    db=Database(settings.db_path);run_id=db.start_run(len(seeds));snaps=[]
    class Adapter:
        def history(self,symbol,period):
            h=wh.load_prices(symbol,600)
            return h if not h.empty else yahoo.live.history(symbol,period) if not offline else h
        def profile(self,symbol):return yahoo.profile(symbol)
        def quarterly_financials(self,symbol):return yahoo.quarterly_financials(symbol)
        def analyst_data(self,symbol):return yahoo.analyst_data(symbol)
    provider=Adapter()
    for idx,row in seeds.iterrows():
        ticker=str(row["ticker"]).upper()
        seed={k:(None if pd.isna(v) else v.item() if hasattr(v,"item") else v) for k,v in row.to_dict().items() if k!="ticker"}
        prev=db.latest_snapshot_before_run(ticker,run_id)
        snap=scan_one(ticker,[],provider,bench,settings,seed,"broad_discovery");snap=assess_snapshot(snap,prev,settings)
        db.save_snapshot(run_id,snap);snaps.append(snap)
        if progress_callback:progress_callback("deep",idx+1,len(seeds),ticker)
    ok=sum(not s.get("error") for s in snaps);fail=len(snaps)-ok;db.finish_run(run_id,ok,fail)
    paths=write_reports(snaps,settings.output_dir,top_n or settings.report_top_n)
    flat=[]
    for s in sorted([x for x in snaps if not x.get("error")],key=lambda x:x.get("scores",{}).get("total",-1),reverse=True):
        f=s.get("features",{});sc=s.get("scores",{});a=s.get("assessment",{});p=s.get("profile",{})
        flat.append({"ticker":s.get("ticker"),"company":s.get("company"),"potential_score":sc.get("total"),"action":a.get("action"),"stage":a.get("stage"),
                     "price_stage":a.get("price_stage"),"discovery_bucket":f.get("discovery_bucket"),"price":f.get("price"),"return_1m":f.get("return_1m"),
                     "return_3m":f.get("return_3m"),"return_6m":f.get("return_6m"),"return_12m":f.get("return_12m"),"forward_pe":p.get("forward_pe"),
                     "next_year_eps_growth":f.get("next_year_eps_growth"),"next_year_revenue_growth":f.get("next_year_revenue_growth_estimate"),
                     "eps_revision_30d":f.get("eps_revision_30d"),"analyst_target_upside":sc.get("analyst_target_upside"),"price_maturity":sc.get("price_maturity"),
                     "expectation_gap":sc.get("expectation_gap"),"data_quality":s.get("data_quality")})
    pd.DataFrame(flat).to_csv(settings.output_dir/"discovery_latest.csv",index=False)
    info=wh.cache_info();db.close();wh.close()
    return snaps,{"run_id":run_id,"universe_count":len(universe),"price_scan_count":len(scan),"seed_count":len(seeds),"success_count":ok,"failure_count":fail,
                  "market_stats":market,"warehouse":info,"paths":{**paths,"universe_scan":settings.output_dir/"universe_price_scan.csv",
                  "seed_candidates":settings.output_dir/"discovery_seed_candidates.csv","discovery":settings.output_dir/"discovery_latest.csv"}}
