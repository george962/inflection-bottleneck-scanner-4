from __future__ import annotations

from typing import Any

import pandas as pd


def _row(df: pd.DataFrame, names: list[str]) -> list[float]:
    if df is None or df.empty:
        return []
    lookup = {str(i).lower().replace(" ", ""): i for i in df.index}
    for name in names:
        key = name.lower().replace(" ", "")
        if key in lookup:
            vals = []
            for x in df.loc[lookup[key]].tolist():
                try:
                    y = float(x)
                    if pd.notna(y): vals.append(y)
                except Exception: pass
            return vals
    return []


def _growth(vals: list[float], periods: int = 4) -> float | None:
    if len(vals) <= periods or vals[periods] == 0:
        return None
    return vals[0] / vals[periods] - 1.0


def fundamental_features(quarterly: dict[str, pd.DataFrame], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    income = quarterly.get("income", pd.DataFrame())
    cash = quarterly.get("cashflow", pd.DataFrame())
    revenue = _row(income, ["Total Revenue", "Operating Revenue"])
    op_income = _row(income, ["Operating Income"])
    gross = _row(income, ["Gross Profit"])
    fcf = _row(cash, ["Free Cash Flow", "FreeCashFlow"])
    rev_yoy = _growth(revenue)
    op_margin = op_income[0] / revenue[0] if revenue and op_income and revenue[0] else None
    op_prev = op_income[4] / revenue[4] if len(revenue) > 4 and len(op_income) > 4 and revenue[4] else None
    gross_margin = gross[0] / revenue[0] if revenue and gross and revenue[0] else None
    gross_prev = gross[4] / revenue[4] if len(revenue) > 4 and len(gross) > 4 and revenue[4] else None
    fcf_margin = fcf[0] / revenue[0] if revenue and fcf and revenue[0] else None
    fcf_prev = fcf[4] / revenue[4] if len(revenue) > 4 and len(fcf) > 4 and revenue[4] else None
    rev_acc = None
    if len(revenue) > 5 and revenue[4] and revenue[5]:
        prev_yoy = revenue[1] / revenue[5] - 1.0
        if rev_yoy is not None: rev_acc = rev_yoy - prev_yoy
    return {
        "revenue_yoy": rev_yoy,
        "revenue_acceleration": rev_acc,
        "gross_margin": gross_margin,
        "gross_margin_change_yoy": (gross_margin - gross_prev) if gross_margin is not None and gross_prev is not None else None,
        "operating_margin": op_margin,
        "operating_margin_change_yoy": (op_margin - op_prev) if op_margin is not None and op_prev is not None else None,
        "free_cash_flow_margin": fcf_margin,
        "free_cash_flow_margin_change_yoy": (fcf_margin - fcf_prev) if fcf_margin is not None and fcf_prev is not None else None,
    }
