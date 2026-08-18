from __future__ import annotations

import time
from typing import Any

from .discovery import price_stage
from .features.market import market_features
from .providers.universe import default_universe, fetch_us_listed_universe, normalize_tickers
from .scoring import discovery_score


def run_discovery(provider, warehouse, cfg: dict[str, Any], tickers: list[str] | None = None, deep: int | None = None, force_refresh: bool = False) -> dict[str, Any]:
    dcfg=cfg.get("discovery",{})
    universe=normalize_tickers(tickers) if tickers else fetch_us_listed_universe()
    if not universe:
        universe=default_universe()
    benchmark_ticker=cfg.get("benchmark","SPY")
    benchmark=provider.history(benchmark_ticker, cfg.get("price_period","2y")); warehouse.upsert_prices(benchmark_ticker,benchmark)
    candidates=[]; downloaded=0; batch_size=int(dcfg.get("batch_size",100)); pause=float(dcfg.get("batch_pause_seconds",.3))
    for start in range(0,len(universe),batch_size):
        batch=universe[start:start+batch_size]
        histories=provider.batch_history(batch,dcfg.get("initial_price_period","2y")) if hasattr(provider,"batch_history") else {t:provider.history(t,dcfg.get("initial_price_period","2y")) for t in batch}
        for ticker,df in histories.items():
            if df is None or df.empty: continue
            downloaded+=len(df); warehouse.upsert_prices(ticker,df); mf=market_features(df,benchmark)
            if (mf.get("price") or 0)<float(dcfg.get("min_price",5)): continue
            if (mf.get("dollar_volume_20d") or 0)<float(dcfg.get("min_dollar_volume_20d",20e6)): continue
            stage=price_stage(mf); mf.update({"price_stage":stage["price_stage"],"price_maturity":stage["price_maturity"]}); score=discovery_score(mf)
            candidates.append({"ticker":ticker,"features":mf,"scores":{"potential_score":score["potential_score"],"price_maturity":stage["price_maturity"]},"discovery_bucket":stage["discovery_bucket"],"price_stage":stage["price_stage"]})
        if pause and start+batch_size<len(universe): time.sleep(pause)
    candidates.sort(key=lambda x:x["scores"]["potential_score"],reverse=True)
    n=int(deep or dcfg.get("deep_candidates",180)); selected=candidates[:n]
    return {"universe_count":len(universe),"price_scan_count":len(candidates),"seed_count":len(selected),"candidates":selected,"market_stats":{"new_symbols":0,"updated_symbols":len(candidates),"downloaded_rows":downloaded,"used_cached_market":False},"warehouse":warehouse.stats()}
