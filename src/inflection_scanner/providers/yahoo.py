from __future__ import annotations

import time
from typing import Any, Callable

import pandas as pd
import yfinance as yf


class YahooProvider:
    def __init__(self, pause_seconds: float = 0.08, retries: int = 2):
        self.pause_seconds = pause_seconds
        self.retries = retries

    def _retry(self, fn: Callable[[], Any], default: Any = None) -> Any:
        last = None
        for attempt in range(self.retries + 1):
            try:
                value = fn()
                if self.pause_seconds:
                    time.sleep(self.pause_seconds)
                return value
            except Exception as exc:
                last = exc
                if attempt < self.retries:
                    time.sleep(max(0.5, self.pause_seconds * (attempt + 1) * 3))
        if default is not None:
            return default
        raise RuntimeError(str(last)) from last

    def history(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        t = yf.Ticker(ticker)
        df = self._retry(
            lambda: t.history(period=period, auto_adjust=True, actions=False),
            default=pd.DataFrame(),
        )
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    def profile(self, ticker: str) -> dict[str, Any]:
        t = yf.Ticker(ticker)
        info = self._retry(lambda: t.get_info(), default={}) or {}
        targets = self._retry(lambda: t.get_analyst_price_targets(), default={}) or {}
        fast = self._retry(lambda: dict(t.fast_info), default={}) or {}
        if not isinstance(info, dict):
            info = {}
        if not isinstance(targets, dict):
            targets = {}
        if not isinstance(fast, dict):
            fast = {}

        forward_pe = info.get("forwardPE")
        try:
            if forward_pe is not None and float(forward_pe) <= 0:
                forward_pe = None
        except Exception:
            forward_pe = None

        return {
            "company": info.get("shortName") or info.get("longName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "exchange": info.get("exchange"),
            "quote_type": info.get("quoteType"),
            "currency": info.get("currency"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "float_shares": info.get("floatShares"),
            "first_trade_date_epoch_utc": info.get("firstTradeDateEpochUtc"),
            "current_price_info": info.get("currentPrice") or info.get("regularMarketPrice"),
            "fast_last_price": fast.get("lastPrice") or fast.get("last_price"),
            "fast_market_cap": fast.get("marketCap") or fast.get("market_cap"),
            "fast_shares": fast.get("shares") or fast.get("shares_outstanding"),
            "forward_pe": forward_pe,
            "trailing_pe": info.get("trailingPE"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "price_to_book": info.get("priceToBook"),
            "enterprise_to_revenue": info.get("enterpriseToRevenue"),
            "enterprise_to_ebitda": info.get("enterpriseToEbitda"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            "free_cashflow": info.get("freeCashflow"),
            "operating_cashflow": info.get("operatingCashflow"),
            "gross_margins": info.get("grossMargins"),
            "operating_margins": info.get("operatingMargins"),
            "profit_margins": info.get("profitMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "beta": info.get("beta"),
            "target_current": targets.get("current"),
            "target_low": targets.get("low"),
            "target_high": targets.get("high"),
            "target_mean": targets.get("mean"),
            "target_median": targets.get("median"),
        }

    def quarterly_financials(self, ticker: str) -> dict[str, pd.DataFrame]:
        t = yf.Ticker(ticker)
        vals = {
            "income": self._retry(lambda: t.quarterly_income_stmt, default=pd.DataFrame()),
            "cashflow": self._retry(lambda: t.quarterly_cashflow, default=pd.DataFrame()),
            "balance": self._retry(lambda: t.quarterly_balance_sheet, default=pd.DataFrame()),
        }
        return {k: v if isinstance(v, pd.DataFrame) else pd.DataFrame() for k, v in vals.items()}

    def analyst_data(self, ticker: str) -> dict[str, pd.DataFrame]:
        t = yf.Ticker(ticker)
        out = {}
        for name in [
            "earnings_estimate",
            "revenue_estimate",
            "eps_trend",
            "eps_revisions",
            "growth_estimates",
            "earnings_history",
        ]:
            value = self._retry(lambda n=name: getattr(t, n), default=pd.DataFrame())
            out[name] = value if isinstance(value, pd.DataFrame) else pd.DataFrame()
        return out
