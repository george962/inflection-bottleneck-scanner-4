from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def _safe_float(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _return_over(close: pd.Series, trading_days: int) -> float | None:
    if len(close) <= trading_days:
        return None
    old = _safe_float(close.iloc[-trading_days - 1])
    new = _safe_float(close.iloc[-1])
    if old is None or new is None or old == 0:
        return None
    return new / old - 1.0


def compute_market_features(
    history: pd.DataFrame,
    benchmark_history: pd.DataFrame | None = None,
) -> dict[str, float | None]:
    if history.empty or "Close" not in history:
        return {}

    close = history["Close"].dropna().astype(float)
    volume = (
        history["Volume"].dropna().astype(float)
        if "Volume" in history
        else pd.Series(dtype=float)
    )

    features: dict[str, float | None] = {
        "price": _safe_float(close.iloc[-1]) if len(close) else None,
        "return_1m": _return_over(close, 21),
        "return_3m": _return_over(close, 63),
        "return_6m": _return_over(close, 126),
        "return_12m": _return_over(close, 252),
    }

    if len(close) >= 20:
        daily = close.pct_change().dropna()
        if len(daily) >= 20:
            features["volatility_20d_annualized"] = _safe_float(
                daily.tail(20).std(ddof=1) * np.sqrt(252)
            )

    if len(close) >= 252:
        high_52w = _safe_float(close.tail(252).max())
        last = _safe_float(close.iloc[-1])
        features["distance_from_52w_high"] = (
            (last / high_52w - 1.0) if last is not None and high_52w else None
        )
        rolling_peak = close.cummax()
        drawdown = close / rolling_peak - 1.0
        features["max_drawdown_1y"] = _safe_float(drawdown.tail(252).min())

    if len(volume) >= 25:
        recent = _safe_float(volume.tail(5).mean())
        prior = _safe_float(volume.iloc[-25:-5].mean())
        features["volume_ratio_5v20"] = (
            recent / prior if recent is not None and prior not in (None, 0) else None
        )

    if benchmark_history is not None and not benchmark_history.empty:
        bench_close = benchmark_history["Close"].dropna().astype(float)
        for days, label in [(21, "1m"), (63, "3m"), (126, "6m"), (252, "12m")]:
            stock_ret = features.get(f"return_{label}")
            bench_ret = _return_over(bench_close, days)
            features[f"relative_return_{label}"] = (
                stock_ret - bench_ret
                if stock_ret is not None and bench_ret is not None
                else None
            )

    return features
