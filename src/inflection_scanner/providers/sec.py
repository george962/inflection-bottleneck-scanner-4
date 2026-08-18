from __future__ import annotations

import os
from typing import Any

import requests

from ..sanitize import safe_exception

SEC_DATA = "https://data.sec.gov"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"


def valid_user_agent(value: str | None) -> bool:
    if not value:
        return False
    text=value.strip()
    if "\n" in text or "\r" in text or "Name:" in text or "Value:" in text:
        return False
    return "@" in text and len(text)>=8


class SECProvider:
    def __init__(self,user_agent: str | None=None,timeout: int=20):
        self.user_agent=(user_agent if user_agent is not None else os.getenv("SEC_USER_AGENT","")).strip(); self.timeout=timeout
    @property
    def available(self): return valid_user_agent(self.user_agent)
    def _headers(self): return {"User-Agent":self.user_agent,"Accept-Encoding":"gzip, deflate","Host":"www.sec.gov"}
    def submissions(self,cik: str):
        if not self.available:return None,{"state":"DISABLED","available":False,"submission_ok":False,"errors":[]}
        cik10=str(cik).strip().replace("CIK","").zfill(10)
        try:
            r=requests.get(f"{SEC_DATA}/submissions/CIK{cik10}.json",headers={"User-Agent":self.user_agent,"Accept-Encoding":"gzip, deflate"},timeout=self.timeout); r.raise_for_status()
            return r.json(),{"state":"OK","available":True,"submission_ok":True,"errors":[]}
        except Exception as exc:
            return None,{"state":"ERROR","available":True,"submission_ok":False,"errors":[safe_exception(exc,"SEC submissions fetch failed")]}
    def filing_document(self,cik: str,accession_number: str,primary_document: str):
        if not self.available:return None,"SEC disabled"
        cik_int=str(int(str(cik).replace("CIK",""))); accession=accession_number.replace("-",""); doc=primary_document.lstrip("/")
        try:
            r=requests.get(f"{SEC_ARCHIVES}/{cik_int}/{accession}/{doc}",headers={"User-Agent":self.user_agent,"Accept-Encoding":"gzip, deflate"},timeout=self.timeout); r.raise_for_status(); return r.text,None
        except Exception as exc:return None,safe_exception(exc,"SEC filing download failed")
