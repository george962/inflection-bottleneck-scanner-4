from __future__ import annotations

import io
from typing import Iterable

import requests

DEFAULT_LARGE_CAP_UNIVERSE = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","AVGO","TSLA","BRK-B","LLY","JPM","V","XOM","WMT","MA","ORCL","COST","NFLX","HD","PG",
    "JNJ","ABBV","BAC","KO","PLTR","AMD","CRM","CVX","UNH","MRK","CSCO","IBM","GE","CAT","RTX","NOW","INTU","QCOM","TXN","AMAT","ADI",
    "MU","ANET","APH","MPWR","TER","STX","LITE","BE","TSM","RDDT","CLS","BX"
]


def normalize_tickers(values: Iterable[str]) -> list[str]:
    out, seen = [], set()
    for x in values:
        t = str(x).strip().upper().replace(".", "-")
        if t and t not in seen:
            seen.add(t); out.append(t)
    return out


def default_universe() -> list[str]:
    return list(DEFAULT_LARGE_CAP_UNIVERSE)


def fetch_us_listed_universe(timeout: int = 20) -> list[str]:
    """Fetch Nasdaq Trader's U.S.-listed symbol directory, with an offline fallback.

    This avoids a hard dependency on SEC and retains V5.3's broad-discovery intent.
    ETFs, test issues, warrants, rights, units and obvious preferred-share variants
    are excluded where the symbol-directory metadata makes that possible.
    """
    urls = [
        "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
        "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
    ]
    symbols: list[str] = []
    try:
        for url in urls:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "inflection-bottleneck-scanner/0.5.4.1"})
            r.raise_for_status()
            lines = [x for x in r.text.splitlines() if x and not x.startswith("File Creation Time")]
            if not lines:
                continue
            header = lines[0].split("|")
            for line in lines[1:]:
                parts = line.split("|")
                if len(parts) != len(header):
                    continue
                row = dict(zip(header, parts))
                symbol = row.get("Symbol") or row.get("ACT Symbol")
                if not symbol:
                    continue
                if row.get("Test Issue", "N") == "Y":
                    continue
                if row.get("ETF", "N") == "Y":
                    continue
                # Nasdaq's NextShares flag is not common-stock exposure.
                if row.get("NextShares", "N") == "Y":
                    continue
                t = symbol.strip().upper().replace(".", "-")
                # Exclude common warrant/right/unit suffix patterns.
                if any(t.endswith(sfx) for sfx in ["-W", "-WS", "-R", "-U"]):
                    continue
                symbols.append(t)
        result = normalize_tickers(symbols)
        return result if len(result) >= 1000 else default_universe()
    except Exception:
        return default_universe()
