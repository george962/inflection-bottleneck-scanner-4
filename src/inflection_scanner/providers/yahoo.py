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
        last: Exception | None = None
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
        return default if default is not None else (_raise(last))

    def history(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        df = self._retry(lambda: yf.Ticker(ticker).history(period=period, auto_adjust=True, actions=False), default=pd.DataFrame())
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()

    def batch_history(self, tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
        if not tickers:
            return {}
        try:
            raw = self._retry(
                lambda: yf.download(
                    tickers=tickers,
                    period=period,
                    auto_adjust=True,
                    actions=False,
                    group_by="ticker",
                    threads=True,
                    progress=False,
                ),
                default=pd.DataFrame(),
            )
        except Exception:
            raw = pd.DataFrame()
        out: dict[str, pd.DataFrame] = {}
        if raw is None or raw.empty:
            return out
        if len(tickers) == 1 and not isinstance(raw.columns, pd.MultiIndex):
            out[tickers[0]] = raw.dropna(how="all")
            return out
        if isinstance(raw.columns, pd.MultiIndex):
            level0 = set(str(x) for x in raw.columns.get_level_values(0))
            level1 = set(str(x) for x in raw.columns.get_level_values(1))
            for ticker in tickers:
                try:
                    if ticker in level0:
                        df = raw[ticker].copy()
                    elif ticker in level1:
                        df = raw.xs(ticker, axis=1, level=1).copy()
                    else:
                        continue
                    df = df.dropna(how="all")
                    if not df.empty:
                        out[ticker] = df
                except Exception:
                    continue
        return out

    def profile(self, ticker: str) -> dict[str, Any]:
        t = yf.Ticker(ticker)
        info = self._retry(lambda: t.get_info(), default={}) or {}
        targets = self._retry(lambda: t.get_analyst_price_targets(), default={}) or {}
        fast = self._retry(lambda: dict(t.fast_info), default={}) or {}
        history_meta = self._retry(lambda: t.get_history_metadata() if hasattr(t, "get_history_metadata") else {}, default={}) or {}
        if not isinstance(info, dict): info = {}
        if not isinstance(targets, dict): targets = {}
        if not isinstance(fast, dict): fast = {}
        if not isinstance(history_meta, dict): history_meta = {}

        forward_pe = info.get("forwardPE")
        try:
            if forward_pe is not None and float(forward_pe) <= 0:
                forward_pe = None
        except Exception:
            forward_pe = None

        return {
            "ticker": ticker.upper(),
            "cik": info.get("cik"),
            "company": info.get("shortName") or info.get("longName") or ticker.upper(),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "exchange": info.get("exchange"),
            "quote_type": info.get("quoteType"),
            "currency": info.get("currency") or history_meta.get("currency"),
            "financial_currency": info.get("financialCurrency"),
            "market_cap": info.get("marketCap") or fast.get("marketCap") or fast.get("market_cap"),
            "enterprise_value": info.get("enterpriseValue"),
            "shares_outstanding": info.get("sharesOutstanding") or fast.get("shares") or fast.get("shares_outstanding"),
            "float_shares": info.get("floatShares"),
            "first_trade_date_epoch_utc": info.get("firstTradeDateEpochUtc") or info.get("firstTradeDate") or history_meta.get("firstTradeDateEpochUtc") or history_meta.get("firstTradeDate"),
            "analyst_count_info": info.get("numberOfAnalystOpinions"),
            "current_price_info": info.get("currentPrice") or info.get("regularMarketPrice"),
            "fast_last_price": fast.get("lastPrice") or fast.get("last_price"),
            "fast_market_cap": fast.get("marketCap") or fast.get("market_cap"),
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

    def annual_financials(self, ticker: str) -> dict[str, pd.DataFrame]:
        t = yf.Ticker(ticker)
        vals = {
            "income": self._retry(lambda: t.income_stmt, default=pd.DataFrame()),
            "cashflow": self._retry(lambda: t.cashflow, default=pd.DataFrame()),
            "balance": self._retry(lambda: t.balance_sheet, default=pd.DataFrame()),
        }
        return {k: v if isinstance(v, pd.DataFrame) else pd.DataFrame() for k, v in vals.items()}

    def analyst_data(self, ticker: str) -> dict[str, pd.DataFrame]:
        t = yf.Ticker(ticker)
        out: dict[str, pd.DataFrame] = {}
        for name in ["earnings_estimate", "revenue_estimate", "eps_trend", "eps_revisions", "growth_estimates", "earnings_history"]:
            value = self._retry(lambda n=name: getattr(t, n), default=pd.DataFrame())
            out[name] = value if isinstance(value, pd.DataFrame) else pd.DataFrame()
        return out

    def news(self, ticker: str, limit: int = 12) -> list[dict[str, Any]]:
        raw = self._retry(lambda: yf.Ticker(ticker).news, default=[]) or []
        out = []
        for item in raw[:limit]:
            if not isinstance(item, dict):
                continue
            content = item.get("content") if isinstance(item.get("content"), dict) else item
            out.append({
                "title": content.get("title"),
                "publisher": content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else content.get("publisher"),
                "published": content.get("pubDate") or content.get("providerPublishTime"),
                "url": (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else content.get("link"),
                "summary": content.get("summary") or content.get("description"),
            })
        return out

    def fx_rate(self, from_currency: str | None, to_currency: str | None) -> float | None:
        if not from_currency or not to_currency:
            return None
        a, b = from_currency.upper(), to_currency.upper()
        if a == b:
            return 1.0
        for symbol, invert in [(f"{a}{b}=X", False), (f"{b}{a}=X", True)]:
            df = self._retry(lambda s=symbol: yf.Ticker(s).history(period="5d", auto_adjust=False), default=pd.DataFrame())
            if isinstance(df, pd.DataFrame) and not df.empty and "Close" in df:
                vals = df["Close"].dropna()
                if not vals.empty and float(vals.iloc[-1]) > 0:
                    rate = float(vals.iloc[-1])
                    return 1.0 / rate if invert else rate
        return None


def _raise(exc: Exception | None):
    raise RuntimeError(str(exc) if exc else "provider failure")
