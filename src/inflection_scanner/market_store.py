from __future__ import annotations
import time
import pandas as pd
import yfinance as yf
from .warehouse import ResearchWarehouse

def _extract_one(raw,ticker):
    if raw is None or raw.empty:return pd.DataFrame()
    if isinstance(raw.columns,pd.MultiIndex):
        l0=set(map(str,raw.columns.get_level_values(0))); l1=set(map(str,raw.columns.get_level_values(1)))
        if ticker in l0:return raw[ticker].copy().dropna(how="all")
        if ticker in l1:return raw.xs(ticker,axis=1,level=1).copy().dropna(how="all")
        return pd.DataFrame()
    return raw.copy().dropna(how="all")
def _batches(symbols,warehouse,period,batch_size,pause,progress,label):
    inserted=0; total=(len(symbols)+batch_size-1)//batch_size
    for b,start in enumerate(range(0,len(symbols),batch_size),1):
        batch=symbols[start:start+batch_size]
        try:
            raw=yf.download(tickers=batch,period=period,interval="1d",auto_adjust=True,actions=False,
                            progress=False,threads=True,group_by="ticker",timeout=25)
        except Exception: raw=pd.DataFrame()
        for ticker in batch: inserted+=warehouse.upsert_prices(ticker,_extract_one(raw,ticker))
        if progress: progress(label,b,total,inserted)
        if pause: time.sleep(pause)
    return inserted
def update_market_history(warehouse,symbols,refresh_hours=14,initial_period="2y",incremental_period="10d",
                          batch_size=100,pause_seconds=0.3,force=False,offline=False,progress_callback=None):
    known=warehouse.known_price_tickers(); wanted=list(dict.fromkeys(s.upper() for s in symbols)); new=[s for s in wanted if s not in known]
    stale=force or not warehouse.is_fetch_fresh("market:all",refresh_hours)
    stats={"new_symbols":len(new),"updated_symbols":0,"downloaded_rows":0,"used_cached_market":False}
    if offline: stats["used_cached_market"]=True; return stats
    if new: stats["downloaded_rows"]+=_batches(new,warehouse,initial_period,batch_size,pause_seconds,progress_callback,"initial")
    if stale:
        existing=[s for s in wanted if s in known]
        if existing:
            stats["downloaded_rows"]+=_batches(existing,warehouse,incremental_period,batch_size,pause_seconds,progress_callback,"incremental")
            stats["updated_symbols"]=len(existing)
        warehouse.set_fetch_state("market:all",{"symbols":len(wanted),"incremental_period":incremental_period})
    elif not new: stats["used_cached_market"]=True
    warehouse.delete_prices_older_than(900); return stats
