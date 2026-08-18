from __future__ import annotations

from typing import Any

import pandas as pd


def _ret(close: pd.Series, days: int) -> float | None:
    if close is None or len(close) <= days:
        return None
    a, b = float(close.iloc[-days-1]), float(close.iloc[-1])
    return b / a - 1.0 if a > 0 else None


def market_features(df: pd.DataFrame, benchmark: pd.DataFrame | None = None) -> dict[str, Any]:
    if df is None or df.empty or "Close" not in df:
        return {"price": None, "data_quality": 0.0}
    close = df["Close"].dropna()
    volume = df["Volume"].fillna(0) if "Volume" in df else pd.Series(index=df.index, data=0.0)
    if close.empty:
        return {"price": None, "data_quality": 0.0}
    price = float(close.iloc[-1])
    high_52 = float(close.tail(252).max()) if len(close) else price
    peak = close.tail(252).cummax()
    drawdowns = close.tail(252) / peak - 1.0
    dvol = (df["Close"] * volume).tail(20).mean() if "Volume" in df else None
    out = {
        "price": price,
        "return_1m": _ret(close, 21),
        "return_3m": _ret(close, 63),
        "return_6m": _ret(close, 126),
        "return_12m": _ret(close, 252),
        "distance_from_52w_high": price / high_52 - 1.0 if high_52 > 0 else None,
        "max_drawdown_1y": float(drawdowns.min()) if not drawdowns.empty else None,
        "dollar_volume_20d": float(dvol) if dvol is not None and pd.notna(dvol) else None,
    }
    if benchmark is not None and not benchmark.empty and "Close" in benchmark:
        bclose = benchmark["Close"].dropna()
        for label, days in [("3m",63),("6m",126),("12m",252)]:
            r = out.get(f"return_{label}")
            br = _ret(bclose, days)
            out[f"relative_return_{label}"] = (r - br) if r is not None and br is not None else None
    present = sum(v is not None for k, v in out.items() if k != "data_quality")
    out["data_quality"] = round(100.0 * present / max(1, len(out)), 1)
    return out
