from __future__ import annotations

from typing import Any

import pandas as pd


def _cell(df: pd.DataFrame, row_names: list[str], col_names: list[str]) -> float | None:
    if df is None or df.empty:
        return None
    rmap = {str(i).lower(): i for i in df.index}
    cmap = {str(i).lower(): i for i in df.columns}
    for rn in row_names:
        if rn.lower() not in rmap: continue
        for cn in col_names:
            if cn.lower() not in cmap: continue
            try:
                x = float(df.loc[rmap[rn.lower()], cmap[cn.lower()]])
                return x if pd.notna(x) else None
            except Exception: pass
    return None


def _trend_value(df: pd.DataFrame, period: str, age: str) -> float | None:
    return _cell(df, [period], [age])


def estimate_features(data: dict[str, pd.DataFrame]) -> dict[str, Any]:
    ee = data.get("earnings_estimate", pd.DataFrame())
    re = data.get("revenue_estimate", pd.DataFrame())
    trend = data.get("eps_trend", pd.DataFrame())
    revisions = data.get("eps_revisions", pd.DataFrame())
    history = data.get("earnings_history", pd.DataFrame())

    eps_next = _cell(ee, ["+1y", "1y", "next year"], ["avg", "avgEstimate"])
    eps_curr = _cell(ee, ["0y", "current year"], ["avg", "avgEstimate"])
    rev_next = _cell(re, ["+1y", "1y", "next year"], ["avg", "avgEstimate"])
    rev_curr = _cell(re, ["0y", "current year"], ["avg", "avgEstimate"])
    eps_growth = eps_next / eps_curr - 1.0 if eps_next is not None and eps_curr and eps_curr > 0 else None
    rev_growth = rev_next / rev_curr - 1.0 if rev_next is not None and rev_curr and rev_curr > 0 else None

    current = _trend_value(trend, "+1y", "current") or _trend_value(trend, "1y", "current")
    d7 = _trend_value(trend, "+1y", "7daysAgo") or _trend_value(trend, "1y", "7daysAgo")
    d30 = _trend_value(trend, "+1y", "30daysAgo") or _trend_value(trend, "1y", "30daysAgo")
    d90 = _trend_value(trend, "+1y", "90daysAgo") or _trend_value(trend, "1y", "90daysAgo")
    def rev(old): return current / old - 1.0 if current is not None and old and old != 0 else None

    analyst_count = _cell(ee, ["+1y", "1y", "next year"], ["numberOfAnalysts", "numberOfanalysts"])
    up30 = _cell(revisions, ["+1y", "1y"], ["upLast30days", "upLast30Days"])
    down30 = _cell(revisions, ["+1y", "1y"], ["downLast30days", "downLast30Days"])
    breadth = None
    if up30 is not None and down30 is not None and up30 + down30 > 0:
        breadth = (up30 - down30) / (up30 + down30)

    surprise = None
    if history is not None and not history.empty:
        for col in history.columns:
            if str(col).lower().replace(" ", "") in {"surprise(%)", "surprisepercent", "surprise%"}:
                vals = pd.to_numeric(history[col], errors="coerce").dropna().tail(4)
                if not vals.empty: surprise = float(vals.mean()) / (100.0 if vals.abs().max() > 2 else 1.0)
                break

    r7, r30, r90 = rev(d7), rev(d30), rev(d90)
    return {
        "next_year_eps_estimate": eps_next,
        "next_year_eps_growth": eps_growth,
        "next_year_revenue_estimate": rev_next,
        "next_year_revenue_growth_estimate": rev_growth,
        "next_year_eps_analyst_count": analyst_count,
        "eps_revision_7d": r7,
        "eps_revision_30d": r30,
        "eps_revision_90d": r90,
        "eps_revision_acceleration": (r30 - r90) if r30 is not None and r90 is not None else None,
        "revision_breadth_30d": breadth,
        "avg_eps_surprise_last4": surprise,
    }
