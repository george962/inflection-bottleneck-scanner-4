from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd
import requests


NASDAQ_LISTED_URL = (
    "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
)
OTHER_LISTED_URL = (
    "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
)


def yahoo_symbol(symbol: str) -> str:
    """
    Convert common U.S. class-share punctuation to Yahoo's convention.
    Example: BRK.B -> BRK-B.
    """
    return str(symbol).strip().upper().replace(".", "-")


def _read_pipe_text(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text), sep="|", dtype=str)
    # Nasdaq directory files end with a "File Creation Time" footer row.
    first_col = df.columns[0]
    mask = ~df[first_col].fillna("").str.startswith("File Creation Time")
    return df.loc[mask].copy()


def _download(url: str, timeout: int = 30) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 inflection-discovery-engine/0.3 "
            "(research use)"
        )
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def _looks_like_common_equity(name: str) -> bool:
    n = f" {str(name).lower()} "
    excluded = [
        " warrant",
        " warrants",
        " right ",
        " rights ",
        " unit ",
        " units ",
        " preferred",
        " preference",
    ]
    return not any(x in n for x in excluded)


def fetch_us_listed_equities(
    cache_dir: str | Path,
    cache_hours: float = 18,
    refresh: bool = False,
) -> pd.DataFrame:
    """
    Build a broad current U.S.-listed equity universe using Nasdaq Trader's
    Nasdaq-listed and other-exchange-listed symbol directory files.

    ETFs, test issues, obvious warrants/rights/units/preferreds are removed.
    ADR/common-share listings are retained.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "us_listed_equities.csv"

    if cache_file.exists() and not refresh:
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600.0
        if age_hours <= cache_hours:
            return pd.read_csv(cache_file, dtype=str)

    nasdaq = _read_pipe_text(_download(NASDAQ_LISTED_URL))
    other = _read_pipe_text(_download(OTHER_LISTED_URL))

    n = pd.DataFrame({
        "symbol": nasdaq.get("Symbol"),
        "name": nasdaq.get("Security Name"),
        "exchange": "NASDAQ",
        "etf": nasdaq.get("ETF", "N"),
        "test_issue": nasdaq.get("Test Issue", "N"),
        "financial_status": nasdaq.get("Financial Status", "N"),
    })

    exchange_map = {
        "A": "NYSE American",
        "N": "NYSE",
        "P": "NYSE Arca",
        "Z": "Cboe BZX",
        "V": "IEX",
    }
    o = pd.DataFrame({
        "symbol": other.get("ACT Symbol"),
        "name": other.get("Security Name"),
        "exchange": other.get("Exchange").map(exchange_map).fillna(other.get("Exchange")),
        "etf": other.get("ETF", "N"),
        "test_issue": other.get("Test Issue", "N"),
        "financial_status": "N",
    })

    df = pd.concat([n, o], ignore_index=True)
    df["symbol"] = df["symbol"].fillna("").str.strip().str.upper()
    df["name"] = df["name"].fillna("").str.strip()
    df["yahoo_symbol"] = df["symbol"].map(yahoo_symbol)

    df = df[
        (df["symbol"] != "")
        & (df["test_issue"].fillna("N") == "N")
        & (df["etf"].fillna("N") == "N")
    ].copy()

    # Keep normal Nasdaq financial status; other exchanges are set to N above.
    df = df[
        df["financial_status"].fillna("N").isin(["N", ""])
    ].copy()

    df = df[df["name"].map(_looks_like_common_equity)].copy()
    df = df.drop_duplicates("yahoo_symbol").sort_values("yahoo_symbol")
    df.to_csv(cache_file, index=False)
    return df.reset_index(drop=True)
