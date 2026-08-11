from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf

from ..warehouse import ResearchWarehouse
from .yahoo import YahooProvider


CACHE_SCHEMA = "v5_3"


def _frame_to_payload(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {"empty": True}

    temp = df.copy()
    temp.index = temp.index.map(str)
    temp.columns = temp.columns.map(str)

    return {
        "empty": False,
        "json": temp.to_json(
            orient="split",
            date_format="iso",
        ),
    }


def _payload_to_frame(
    payload: dict[str, Any] | None,
) -> pd.DataFrame:
    if not payload or payload.get("empty"):
        return pd.DataFrame()

    return pd.read_json(
        payload["json"],
        orient="split",
    )


class CachedYahooProvider:
    def __init__(
        self,
        warehouse: ResearchWarehouse,
        ttl_hours: dict[str, float],
        pause_seconds: float = 0.08,
        offline: bool = False,
    ):
        self.warehouse = warehouse
        self.ttl_hours = ttl_hours
        self.live = YahooProvider(
            pause_seconds=pause_seconds
        )
        self.offline = offline

    @staticmethod
    def cache_key(
        kind: str,
        ticker: str,
    ) -> str:
        return (
            f"yahoo:{CACHE_SCHEMA}:"
            f"{kind}:{ticker.upper()}"
        )

    def _cached_or_live(
        self,
        key: str,
        ttl_name: str,
        fetcher,
    ):
        cached = self.warehouse.get_json(
            key,
            allow_stale=False,
        )

        if cached is not None:
            return cached

        stale = self.warehouse.get_json(
            key,
            allow_stale=True,
        )

        if self.offline:
            return stale

        try:
            value = fetcher()

            self.warehouse.put_json(
                key,
                value,
                ttl_hours=float(
                    self.ttl_hours.get(
                        ttl_name,
                        24,
                    )
                ),
            )

            return value

        except Exception:
            if stale is not None:
                return stale
            raise

    def profile(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        return (
            self._cached_or_live(
                self.cache_key(
                    "profile",
                    ticker,
                ),
                "profile",
                lambda: self.live.profile(
                    ticker
                ),
            )
            or {}
        )

    def quarterly_financials(
        self,
        ticker: str,
    ) -> dict[str, pd.DataFrame]:
        payload = (
            self._cached_or_live(
                self.cache_key(
                    "qfin",
                    ticker,
                ),
                "financials",
                lambda: {
                    key: _frame_to_payload(
                        value
                    )
                    for key, value
                    in self.live.quarterly_financials(
                        ticker
                    ).items()
                },
            )
            or {}
        )

        return {
            key: _payload_to_frame(
                payload.get(key)
            )
            for key in [
                "income",
                "cashflow",
                "balance",
            ]
        }

    def annual_financials(
        self,
        ticker: str,
    ) -> dict[str, pd.DataFrame]:
        key = self.cache_key(
            "afin",
            ticker,
        )

        def fetch():
            t = yf.Ticker(ticker)

            frames = {
                "income": t.income_stmt,
                "cashflow": t.cashflow,
                "balance": t.balance_sheet,
            }

            return {
                name: _frame_to_payload(
                    value
                )
                for name, value
                in frames.items()
            }

        payload = (
            self._cached_or_live(
                key,
                "financials",
                fetch,
            )
            or {}
        )

        return {
            name: _payload_to_frame(
                payload.get(name)
            )
            for name in [
                "income",
                "cashflow",
                "balance",
            ]
        }

    def analyst_data(
        self,
        ticker: str,
    ) -> dict[str, pd.DataFrame]:
        payload = (
            self._cached_or_live(
                self.cache_key(
                    "analyst",
                    ticker,
                ),
                "analyst",
                lambda: {
                    key: _frame_to_payload(
                        value
                    )
                    for key, value
                    in self.live.analyst_data(
                        ticker
                    ).items()
                },
            )
            or {}
        )

        return {
            key: _payload_to_frame(
                payload.get(key)
            )
            for key in [
                "earnings_estimate",
                "revenue_estimate",
                "eps_trend",
                "eps_revisions",
                "growth_estimates",
                "earnings_history",
            ]
        }

    def news(
        self,
        ticker: str,
        count: int = 12,
    ) -> list[dict[str, Any]]:
        def fetch():
            t = yf.Ticker(ticker)
            raw = getattr(
                t,
                "news",
                [],
            ) or []

            output = []

            for item in raw[
                : max(count, 20)
            ]:
                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                content = (
                    item.get("content")
                    if isinstance(
                        item.get("content"),
                        dict,
                    )
                    else {}
                )

                provider = (
                    content.get("provider")
                    if isinstance(
                        content.get("provider"),
                        dict,
                    )
                    else {}
                )

                canonical = (
                    content.get(
                        "canonicalUrl"
                    )
                    if isinstance(
                        content.get(
                            "canonicalUrl"
                        ),
                        dict,
                    )
                    else {}
                )

                output.append({
                    "title": (
                        content.get("title")
                        or item.get("title")
                        or ""
                    ),
                    "publisher": (
                        provider.get(
                            "displayName"
                        )
                        or item.get(
                            "publisher"
                        )
                        or ""
                    ),
                    "published": (
                        content.get("pubDate")
                        or item.get(
                            "providerPublishTime"
                        )
                    ),
                    "url": (
                        canonical.get("url")
                        or item.get("link")
                        or ""
                    ),
                    "summary": (
                        content.get("summary")
                        or item.get("summary")
                        or ""
                    ),
                })

            return output

        data = (
            self._cached_or_live(
                self.cache_key(
                    "news",
                    ticker,
                ),
                "news",
                fetch,
            )
            or []
        )

        return list(data)[:count]
