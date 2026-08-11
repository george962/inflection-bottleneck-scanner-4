from __future__ import annotations
from typing import Any
import pandas as pd
import yfinance as yf
from ..warehouse import ResearchWarehouse
from .yahoo import YahooProvider

def _frame_to_payload(df):
    if df is None or df.empty: return {"empty":True}
    t=df.copy(); t.index=t.index.map(str); t.columns=t.columns.map(str)
    return {"empty":False,"json":t.to_json(orient="split",date_format="iso")}
def _payload_to_frame(p):
    if not p or p.get("empty"): return pd.DataFrame()
    return pd.read_json(p["json"],orient="split")

class CachedYahooProvider:
    def __init__(self,warehouse:ResearchWarehouse,ttl_hours:dict[str,float],pause_seconds=0.08,offline=False):
        self.warehouse=warehouse; self.ttl_hours=ttl_hours; self.live=YahooProvider(pause_seconds=pause_seconds); self.offline=offline
    def _get(self,key,ttl_name,fetcher):
        fresh=self.warehouse.get_json(key)
        if fresh is not None: return fresh
        stale=self.warehouse.get_json(key,allow_stale=True)
        if self.offline: return stale
        try:
            val=fetcher(); self.warehouse.put_json(key,val,float(self.ttl_hours.get(ttl_name,24))); return val
        except Exception:
            if stale is not None: return stale
            raise
    def profile(self,ticker):
        return self._get(f"yahoo:profile:{ticker.upper()}","profile",lambda:self.live.profile(ticker)) or {}
    def quarterly_financials(self,ticker):
        p=self._get(f"yahoo:qfin:{ticker.upper()}","financials",
            lambda:{k:_frame_to_payload(v) for k,v in self.live.quarterly_financials(ticker).items()}) or {}
        return {k:_payload_to_frame(p.get(k)) for k in ["income","cashflow","balance"]}
    def annual_financials(self,ticker):
        def fetch():
            t=yf.Ticker(ticker); fs={"income":t.income_stmt,"cashflow":t.cashflow,"balance":t.balance_sheet}
            return {k:_frame_to_payload(v) for k,v in fs.items()}
        p=self._get(f"yahoo:afin:{ticker.upper()}","financials",fetch) or {}
        return {k:_payload_to_frame(p.get(k)) for k in ["income","cashflow","balance"]}
    def analyst_data(self,ticker):
        p=self._get(f"yahoo:analyst:{ticker.upper()}","analyst",
            lambda:{k:_frame_to_payload(v) for k,v in self.live.analyst_data(ticker).items()}) or {}
        return {k:_payload_to_frame(p.get(k)) for k in ["earnings_estimate","revenue_estimate","eps_trend","eps_revisions","growth_estimates","earnings_history"]}
    def news(self,ticker,count=12):
        def fetch():
            raw=getattr(yf.Ticker(ticker),"news",[]) or []; out=[]
            for item in raw[:max(count,20)]:
                if not isinstance(item,dict): continue
                c=item.get("content") if isinstance(item.get("content"),dict) else {}
                pr=c.get("provider") if isinstance(c.get("provider"),dict) else {}
                cu=c.get("canonicalUrl") if isinstance(c.get("canonicalUrl"),dict) else {}
                out.append({"title":c.get("title") or item.get("title") or "",
                            "publisher":pr.get("displayName") or item.get("publisher") or "",
                            "published":c.get("pubDate") or item.get("providerPublishTime"),
                            "url":cu.get("url") or item.get("link") or "",
                            "summary":c.get("summary") or item.get("summary") or ""})
            return out
        return list(self._get(f"yahoo:news:{ticker.upper()}","news",fetch) or [])[:count]
