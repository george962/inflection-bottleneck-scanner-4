from __future__ import annotations

import os
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

from ..warehouse import ResearchWarehouse


class CachedSecResearchProvider:
    BASE = "https://data.sec.gov"
    WWW = "https://www.sec.gov"

    def __init__(
        self,
        warehouse: ResearchWarehouse,
        ttl_hours: float = 12,
        user_agent: str | None = None,
        offline: bool = False,
        min_interval: float = 0.15,
    ):
        self.warehouse = warehouse
        self.ttl_hours = ttl_hours
        self.user_agent = (user_agent or os.getenv("SEC_USER_AGENT", "")).strip()
        self.offline = offline
        self.min_interval = max(0.11, min_interval)
        self.last = 0.0
        self.session = requests.Session()
        self._status: dict[str, dict[str, Any]] = {}
        if self.user_agent:
            self.session.headers.update(
                {
                    "User-Agent": self.user_agent,
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                }
            )

    @property
    def available(self) -> bool:
        return bool(self.user_agent)

    def _get(self, url: str) -> requests.Response:
        if not self.user_agent:
            raise RuntimeError(
                "SEC_USER_AGENT is required for SEC evidence. Set a GitHub Actions secret such as 'George Jiang your@email.com'."
            )
        elapsed = time.monotonic() - self.last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        response = self.session.get(url, timeout=35)
        self.last = time.monotonic()
        response.raise_for_status()
        return response

    def ticker_map(self) -> dict[str, dict[str, Any]]:
        key = "sec:v5_2:ticker_map"
        cached = self.warehouse.get_json(key)
        if cached is not None:
            return cached
        stale = self.warehouse.get_json(key, True)
        if self.offline:
            return stale or {}
        data = self._get(f"{self.WWW}/files/company_tickers.json").json()
        out: dict[str, dict[str, Any]] = {}
        for item in data.values():
            ticker = str(item.get("ticker", "")).upper()
            if ticker:
                out[ticker] = item
        self.warehouse.put_json(key, out, 24 * 7)
        return out

    def submissions(self, ticker: str) -> dict[str, Any]:
        ticker = ticker.upper()
        key = f"sec:v5_2:submissions:{ticker}"
        cached = self.warehouse.get_json(key)
        if cached is not None:
            return cached
        stale = self.warehouse.get_json(key, True)
        if self.offline:
            return stale or {}
        item = self.ticker_map().get(ticker)
        if not item:
            raise KeyError(f"Ticker {ticker} is not present in SEC company_tickers.json")
        cik = int(item["cik_str"])
        data = self._get(f"{self.BASE}/submissions/CIK{cik:010d}.json").json()
        self.warehouse.put_json(key, data, self.ttl_hours)
        return data

    @staticmethod
    def _clean_html(text: str, max_chars: int) -> str:
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        cleaned = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        return cleaned[:max_chars]

    def status_for(self, ticker: str) -> dict[str, Any]:
        ticker = ticker.upper()
        if ticker in self._status:
            return dict(self._status[ticker])
        if not self.available:
            cached_count = len(self.warehouse.recent_filings(ticker, 10))
            return {
                "state": "CACHED_ONLY" if cached_count else "UNAVAILABLE",
                "available": False,
                "submission_ok": False,
                "documents_requested": 0,
                "documents_cached": cached_count,
                "documents_downloaded": 0,
                "errors": ([] if cached_count else ["SEC_USER_AGENT is not configured."]),
            }
        return {
            "state": "NOT_RUN",
            "available": True,
            "submission_ok": False,
            "documents_requested": 0,
            "documents_cached": len(self.warehouse.recent_filings(ticker, 10)),
            "documents_downloaded": 0,
            "errors": [],
        }

    def ensure_recent_documents(
        self,
        ticker: str,
        forms: list[str],
        max_documents: int,
        max_chars: int,
    ) -> list[dict[str, Any]]:
        ticker = ticker.upper()
        status: dict[str, Any] = {
            "state": "READY",
            "available": self.available,
            "submission_ok": False,
            "documents_requested": 0,
            "documents_cached": 0,
            "documents_downloaded": 0,
            "errors": [],
        }

        if not self.available:
            filings = self.warehouse.recent_filings(ticker, max_documents)
            status["documents_cached"] = len(filings)
            status["state"] = "CACHED_ONLY" if filings else "UNAVAILABLE"
            if not filings:
                status["errors"].append("SEC_USER_AGENT is not configured.")
            self._status[ticker] = status
            return filings

        try:
            sub = self.submissions(ticker)
            status["submission_ok"] = bool(sub)
        except Exception as exc:
            status["state"] = "ERROR"
            status["errors"].append(f"SEC submissions fetch failed: {type(exc).__name__}: {exc}")
            filings = self.warehouse.recent_filings(ticker, max_documents)
            status["documents_cached"] = len(filings)
            self._status[ticker] = status
            return filings

        if not sub:
            status["state"] = "ERROR"
            status["errors"].append("SEC submissions response was empty.")
            filings = self.warehouse.recent_filings(ticker, max_documents)
            status["documents_cached"] = len(filings)
            self._status[ticker] = status
            return filings

        cik = int(sub.get("cik", 0) or 0)
        recent = sub.get("filings", {}).get("recent", {}) or {}
        if not cik or not recent:
            status["state"] = "ERROR"
            status["errors"].append("SEC submissions response did not contain a usable CIK/recent-filings table.")
            filings = self.warehouse.recent_filings(ticker, max_documents)
            status["documents_cached"] = len(filings)
            self._status[ticker] = status
            return filings

        chosen: list[dict[str, str]] = []
        count = len(recent.get("form", []))
        for i in range(count):
            form = str(recent.get("form", [""])[i])
            if form not in forms:
                continue
            accession = str(recent.get("accessionNumber", [""])[i])
            primary = str(recent.get("primaryDocument", [""])[i])
            if not accession or not primary:
                continue
            url = f"{self.WWW}/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{primary}"
            chosen.append(
                {
                    "accession": accession,
                    "form": form,
                    "filing_date": str(recent.get("filingDate", [""])[i]),
                    "report_date": str(recent.get("reportDate", [""])[i]),
                    "source_url": url,
                }
            )
            if len(chosen) >= max_documents:
                break

        status["documents_requested"] = len(chosen)
        for item in chosen:
            if self.warehouse.has_filing(ticker, item["accession"]):
                continue
            if self.offline:
                continue
            try:
                response = self._get(item["source_url"])
                text = self._clean_html(response.text, max_chars)
                if len(text) < 200:
                    raise ValueError("Downloaded filing text was unexpectedly short.")
                self.warehouse.put_filing(
                    ticker,
                    item["accession"],
                    item["form"],
                    item["filing_date"],
                    item["report_date"],
                    item["source_url"],
                    text,
                )
                status["documents_downloaded"] += 1
            except Exception as exc:
                status["errors"].append(
                    f"{item['form']} {item['accession']} download failed: {type(exc).__name__}: {exc}"
                )

        filings = self.warehouse.recent_filings(ticker, max_documents)
        status["documents_cached"] = len(filings)
        if status["errors"] and filings:
            status["state"] = "PARTIAL_ERROR"
        elif status["errors"] and not filings:
            status["state"] = "ERROR"
        elif not filings:
            status["state"] = "ERROR"
            status["errors"].append("No requested SEC filing documents were cached after the fetch attempt.")
        else:
            status["state"] = "READY"

        self._status[ticker] = status
        return filings
