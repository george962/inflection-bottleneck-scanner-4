from __future__ import annotations

import os
import time
from functools import lru_cache
from typing import Any

import requests


class SecProvider:
    BASE = "https://data.sec.gov"
    WWW = "https://www.sec.gov"

    def __init__(self, user_agent: str | None = None, min_interval: float = 0.15):
        self.user_agent = user_agent or os.getenv("SEC_USER_AGENT", "").strip()
        if not self.user_agent:
            raise ValueError(
                "SEC_USER_AGENT is required. Example: 'Your Name your.email@example.com'"
            )
        self.min_interval = max(min_interval, 0.11)
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json",
            }
        )

    def _get_json(self, url: str) -> Any:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        resp = self.session.get(url, timeout=30)
        self._last_request = time.monotonic()
        resp.raise_for_status()
        return resp.json()

    @lru_cache(maxsize=1)
    def ticker_map(self) -> dict[str, dict[str, Any]]:
        data = self._get_json(f"{self.WWW}/files/company_tickers.json")
        out: dict[str, dict[str, Any]] = {}
        for item in data.values():
            ticker = str(item.get("ticker", "")).upper()
            if ticker:
                out[ticker] = item
        return out

    def cik_for_ticker(self, ticker: str) -> int:
        item = self.ticker_map().get(ticker.upper())
        if not item:
            raise KeyError(f"Ticker not found in SEC company_tickers.json: {ticker}")
        return int(item["cik_str"])

    def recent_filings(self, ticker: str, limit: int = 10) -> list[dict[str, Any]]:
        cik = self.cik_for_ticker(ticker)
        data = self._get_json(f"{self.BASE}/submissions/CIK{cik:010d}.json")
        recent = data.get("filings", {}).get("recent", {})
        keys = [
            "accessionNumber",
            "filingDate",
            "reportDate",
            "acceptanceDateTime",
            "form",
            "primaryDocument",
            "primaryDocDescription",
        ]
        n = min(limit, len(recent.get("form", [])))
        rows: list[dict[str, Any]] = []
        for i in range(n):
            rows.append({k: recent.get(k, [None] * n)[i] for k in keys})
        return rows
