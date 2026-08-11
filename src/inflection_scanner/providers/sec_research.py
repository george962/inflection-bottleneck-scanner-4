from __future__ import annotations
import os,re,time
from typing import Any
import requests
from bs4 import BeautifulSoup
from ..warehouse import ResearchWarehouse

class CachedSecResearchProvider:
    BASE="https://data.sec.gov"; WWW="https://www.sec.gov"
    def __init__(self,warehouse:ResearchWarehouse,ttl_hours=12,user_agent=None,offline=False,min_interval=.15):
        self.warehouse=warehouse; self.ttl_hours=ttl_hours; self.user_agent=(user_agent or os.getenv("SEC_USER_AGENT","")).strip()
        self.offline=offline; self.min_interval=max(.11,min_interval); self.last=0.0; self.session=requests.Session()
        if self.user_agent:self.session.headers.update({"User-Agent":self.user_agent,"Accept-Encoding":"gzip, deflate"})
    @property
    def available(self): return bool(self.user_agent)
    def _get(self,url):
        if not self.user_agent: raise RuntimeError("SEC_USER_AGENT is required")
        elapsed=time.monotonic()-self.last
        if elapsed<self.min_interval:time.sleep(self.min_interval-elapsed)
        r=self.session.get(url,timeout=30); self.last=time.monotonic(); r.raise_for_status(); return r
    def ticker_map(self):
        key="sec:ticker_map"; v=self.warehouse.get_json(key)
        if v is not None:return v
        stale=self.warehouse.get_json(key,True)
        if self.offline:return stale or {}
        data=self._get(f"{self.WWW}/files/company_tickers.json").json(); out={}
        for item in data.values():
            t=str(item.get("ticker","")).upper()
            if t:out[t]=item
        self.warehouse.put_json(key,out,24*7); return out
    def submissions(self,ticker):
        ticker=ticker.upper(); key=f"sec:submissions:{ticker}"; v=self.warehouse.get_json(key)
        if v is not None:return v
        stale=self.warehouse.get_json(key,True)
        if self.offline:return stale or {}
        item=self.ticker_map().get(ticker)
        if not item:return stale or {}
        cik=int(item["cik_str"]); data=self._get(f"{self.BASE}/submissions/CIK{cik:010d}.json").json()
        self.warehouse.put_json(key,data,self.ttl_hours); return data
    @staticmethod
    def _clean_html(text,max_chars):
        soup=BeautifulSoup(text,"html.parser")
        for tag in soup(["script","style","noscript"]):tag.decompose()
        x=re.sub(r"\s+"," ",soup.get_text(" ",strip=True)); return x[:max_chars]
    def ensure_recent_documents(self,ticker,forms,max_documents,max_chars):
        ticker=ticker.upper(); sub=self.submissions(ticker)
        if not sub:return self.warehouse.recent_filings(ticker,max_documents)
        cik=int(sub.get("cik",0)); recent=sub.get("filings",{}).get("recent",{})
        if not cik or not recent:return self.warehouse.recent_filings(ticker,max_documents)
        chosen=[]; count=len(recent.get("form",[]))
        for i in range(count):
            form=str(recent.get("form",[""])[i])
            if form not in forms:continue
            acc=str(recent.get("accessionNumber",[""])[i]); primary=str(recent.get("primaryDocument",[""])[i])
            if not acc or not primary:continue
            url=f"{self.WWW}/Archives/edgar/data/{cik}/{acc.replace('-','')}/{primary}"
            chosen.append({"accession":acc,"form":form,"filing_date":str(recent.get("filingDate",[""])[i]),
                           "report_date":str(recent.get("reportDate",[""])[i]),"source_url":url})
            if len(chosen)>=max_documents:break
        for m in chosen:
            if self.warehouse.has_filing(ticker,m["accession"]) or self.offline:continue
            try:
                text=self._clean_html(self._get(m["source_url"]).text,max_chars)
                self.warehouse.put_filing(ticker,m["accession"],m["form"],m["filing_date"],m["report_date"],m["source_url"],text)
            except Exception:pass
        return self.warehouse.recent_filings(ticker,max_documents)
