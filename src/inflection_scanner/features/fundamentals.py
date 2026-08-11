from __future__ import annotations

import math
from typing import Iterable

import pandas as pd


def safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    x = a / b
    return x if math.isfinite(x) else None


def _row(df: pd.DataFrame, aliases: Iterable[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    normalized = {str(i).lower().replace(" ", ""): i for i in df.index}
    for alias in aliases:
        key = alias.lower().replace(" ", "")
        if key in normalized:
            s = df.loc[normalized[key]]
            if isinstance(s, pd.Series):
                return s
    return None


def _values_desc(series: pd.Series | None) -> list[float | None]:
    if series is None:
        return []
    s = series.copy()
    try:
        s = s.sort_index(ascending=False)
    except Exception:
        pass
    out: list[float | None] = []
    for v in s.tolist():
        try:
            x = float(v)
            out.append(x if math.isfinite(x) else None)
        except (TypeError, ValueError):
            out.append(None)
    return out


def _at(values: list[float | None], idx: int) -> float | None:
    return values[idx] if len(values) > idx else None


def _growth(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old == 0:
        return None
    value = new / abs(old) - 1.0 if old < 0 else new / old - 1.0
    return value if math.isfinite(value) else None


def compute_fundamental_features(
    income: pd.DataFrame,
    cashflow: pd.DataFrame | None = None,
    balance: pd.DataFrame | None = None,
) -> dict[str, float | None]:
    rev = _values_desc(_row(income, ["Total Revenue", "Operating Revenue", "Revenue"]))
    gross = _values_desc(_row(income, ["Gross Profit"]))
    op = _values_desc(_row(income, ["Operating Income", "Operating Income Loss"]))
    net = _values_desc(
        _row(income, ["Net Income", "Net Income Common Stockholders", "Net Income Including Noncontrolling Interests"])
    )

    latest_rev, prev_rev, yago_rev, prior_yago_rev = (
        _at(rev, 0),
        _at(rev, 1),
        _at(rev, 4),
        _at(rev, 5),
    )
    latest_gross, yago_gross = _at(gross, 0), _at(gross, 4)
    latest_op, yago_op = _at(op, 0), _at(op, 4)
    latest_net, yago_net = _at(net, 0), _at(net, 4)

    revenue_yoy = _growth(latest_rev, yago_rev)
    prior_revenue_yoy = _growth(prev_rev, prior_yago_rev)

    gm_latest = safe_div(latest_gross, latest_rev)
    gm_yago = safe_div(yago_gross, yago_rev)
    opm_latest = safe_div(latest_op, latest_rev)
    opm_yago = safe_div(yago_op, yago_rev)

    delta_rev = (
        latest_rev - yago_rev
        if latest_rev is not None and yago_rev is not None
        else None
    )
    delta_op = (
        latest_op - yago_op
        if latest_op is not None and yago_op is not None
        else None
    )

    features: dict[str, float | None] = {
        "revenue_latest": latest_rev,
        "revenue_yoy": revenue_yoy,
        "prior_revenue_yoy": prior_revenue_yoy,
        "revenue_acceleration": (
            revenue_yoy - prior_revenue_yoy
            if revenue_yoy is not None and prior_revenue_yoy is not None
            else None
        ),
        "gross_margin": gm_latest,
        "gross_margin_change_yoy": (
            gm_latest - gm_yago
            if gm_latest is not None and gm_yago is not None
            else None
        ),
        "operating_margin": opm_latest,
        "operating_margin_change_yoy": (
            opm_latest - opm_yago
            if opm_latest is not None and opm_yago is not None
            else None
        ),
        "incremental_operating_margin_yoy": safe_div(delta_op, delta_rev),
        "net_income_yoy": _growth(latest_net, yago_net),
    }

    if cashflow is not None and not cashflow.empty:
        fcf = _values_desc(_row(cashflow, ["Free Cash Flow"]))
        ocf = _values_desc(_row(cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"]))
        capex = _values_desc(_row(cashflow, ["Capital Expenditure", "Capital Expenditures"]))

        latest_fcf = _at(fcf, 0)
        if latest_fcf is None:
            latest_ocf = _at(ocf, 0)
            latest_capex = _at(capex, 0)
            if latest_ocf is not None and latest_capex is not None:
                latest_fcf = latest_ocf + latest_capex if latest_capex < 0 else latest_ocf - latest_capex

        yago_fcf = _at(fcf, 4)
        if yago_fcf is None:
            yago_ocf = _at(ocf, 4)
            yago_capex = _at(capex, 4)
            if yago_ocf is not None and yago_capex is not None:
                yago_fcf = yago_ocf + yago_capex if yago_capex < 0 else yago_ocf - yago_capex

        fcf_margin = safe_div(latest_fcf, latest_rev)
        fcf_margin_yago = safe_div(yago_fcf, yago_rev)
        features.update(
            {
                "free_cash_flow_latest": latest_fcf,
                "free_cash_flow_margin": fcf_margin,
                "free_cash_flow_margin_change_yoy": (
                    fcf_margin - fcf_margin_yago
                    if fcf_margin is not None and fcf_margin_yago is not None
                    else None
                ),
            }
        )

    if balance is not None and not balance.empty:
        inventory = _values_desc(_row(balance, ["Inventory", "Finished Goods"]))
        current_inventory = _at(inventory, 0)
        yago_inventory = _at(inventory, 4)
        features["inventory_yoy"] = _growth(current_inventory, yago_inventory)
        if features.get("inventory_yoy") is not None and revenue_yoy is not None:
            features["inventory_growth_minus_revenue_growth"] = (
                features["inventory_yoy"] - revenue_yoy
            )

    return features
