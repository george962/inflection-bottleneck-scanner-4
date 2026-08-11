from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _num(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _row(df: pd.DataFrame, preferred: list[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    index_map = {str(i).lower(): i for i in df.index}
    for key in preferred:
        if key.lower() in index_map:
            row = df.loc[index_map[key.lower()]]
            return row if isinstance(row, pd.Series) else None
    return None


def _find_col(series: pd.Series | None, candidates: list[str]) -> float | None:
    if series is None:
        return None
    col_map = {str(c).lower().replace(" ", ""): c for c in series.index}
    for candidate in candidates:
        key = candidate.lower().replace(" ", "")
        if key in col_map:
            return _num(series[col_map[key]])
    return None


def _growth(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old == 0:
        return None
    return new / abs(old) - 1.0 if old < 0 else new / old - 1.0


def compute_estimate_features(data: dict[str, pd.DataFrame]) -> dict[str, float | None]:
    features: dict[str, float | None] = {}

    eps_trend = data.get("eps_trend", pd.DataFrame())
    trend_row = _row(eps_trend, ["+1y", "0y", "+1q", "0q"])
    current = _find_col(trend_row, ["current"])
    d7 = _find_col(trend_row, ["7daysAgo", "7 days ago"])
    d30 = _find_col(trend_row, ["30daysAgo", "30 days ago"])
    d60 = _find_col(trend_row, ["60daysAgo", "60 days ago"])
    d90 = _find_col(trend_row, ["90daysAgo", "90 days ago"])

    def revision(old: float | None) -> float | None:
        if current is None or old is None or old == 0:
            return None
        return (current - old) / abs(old)

    features.update(
        {
            "eps_estimate_current": current,
            "eps_revision_7d": revision(d7),
            "eps_revision_30d": revision(d30),
            "eps_revision_60d": revision(d60),
            "eps_revision_90d": revision(d90),
        }
    )

    if features["eps_revision_30d"] is not None and features["eps_revision_90d"] is not None:
        features["eps_revision_acceleration"] = (
            features["eps_revision_30d"] - features["eps_revision_90d"] / 3.0
        )

    eps_rev = data.get("eps_revisions", pd.DataFrame())
    rev_row = _row(eps_rev, ["+1y", "0y", "+1q", "0q"])
    ups7 = _find_col(rev_row, ["upLast7days", "up last 7 days"])
    ups30 = _find_col(rev_row, ["upLast30days", "up last 30 days"])
    downs7 = _find_col(rev_row, ["downLast7Days", "down last 7 days"])
    downs30 = _find_col(rev_row, ["downLast30days", "down last 30 days"])
    total = sum(x or 0 for x in [ups30, downs30])
    if total:
        features["revision_breadth_30d"] = ((ups30 or 0) - (downs30 or 0)) / total
    total7 = sum(x or 0 for x in [ups7, downs7])
    if total7:
        features["revision_breadth_7d"] = ((ups7 or 0) - (downs7 or 0)) / total7

    earnings_est = data.get("earnings_estimate", pd.DataFrame())
    current_year = _row(earnings_est, ["0y"])
    next_year = _row(earnings_est, ["+1y"])
    current_q = _row(earnings_est, ["0q"])
    next_q = _row(earnings_est, ["+1q"])

    cy_eps = _find_col(current_year, ["avg"])
    ny_eps = _find_col(next_year, ["avg"])
    cy_growth = _find_col(current_year, ["growth"])
    ny_growth = _find_col(next_year, ["growth"])

    features.update(
        {
            "current_year_eps_estimate": cy_eps,
            "next_year_eps_estimate": ny_eps,
            "current_year_eps_growth": cy_growth,
            "next_year_eps_growth": ny_growth if ny_growth is not None else _growth(ny_eps, cy_eps),
            "current_quarter_eps_growth": _find_col(current_q, ["growth"]),
            "next_quarter_eps_growth": _find_col(next_q, ["growth"]),
            "analyst_eps_growth": ny_growth if ny_growth is not None else cy_growth,
            "next_year_eps_analyst_count": _find_col(next_year, ["numberOfAnalysts"]),
        }
    )

    revenue_est = data.get("revenue_estimate", pd.DataFrame())
    cy_rev_row = _row(revenue_est, ["0y"])
    ny_rev_row = _row(revenue_est, ["+1y"])
    cy_rev = _find_col(cy_rev_row, ["avg"])
    ny_rev = _find_col(ny_rev_row, ["avg"])

    features.update(
        {
            "current_year_revenue_estimate": cy_rev,
            "next_year_revenue_estimate": ny_rev,
            "current_year_revenue_growth_estimate": _find_col(cy_rev_row, ["growth"]),
            "next_year_revenue_growth_estimate": (
                _find_col(ny_rev_row, ["growth"])
                if _find_col(ny_rev_row, ["growth"]) is not None
                else _growth(ny_rev, cy_rev)
            ),
            "analyst_revenue_growth": (
                _find_col(ny_rev_row, ["growth"])
                if _find_col(ny_rev_row, ["growth"]) is not None
                else _find_col(cy_rev_row, ["growth"])
            ),
        }
    )

    history = data.get("earnings_history", pd.DataFrame())
    if history is not None and not history.empty:
        if "surprisePercent" in history.columns:
            surprises = pd.to_numeric(history["surprisePercent"], errors="coerce").dropna()
            if len(surprises):
                features["avg_eps_surprise_last4"] = float(surprises.tail(4).mean())
                features["positive_eps_surprises_last4"] = float((surprises.tail(4) > 0).sum())

    return features
