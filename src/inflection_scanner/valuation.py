from __future__ import annotations

import math
import statistics
from typing import Any

import pandas as pd

from .security_normalization import SecurityNormalization

SCENARIO_WEIGHTS = {"Bear": 0.25, "Base": 0.50, "Bull": 0.25}


def finite(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def row_values(df: pd.DataFrame, aliases: list[str]) -> list[float]:
    if df is None or df.empty:
        return []
    normalized = {str(i).lower().replace(" ", ""): i for i in df.index}
    for alias in aliases:
        key = alias.lower().replace(" ", "")
        if key not in normalized:
            continue
        values = []
        for value in df.loc[normalized[key]].tolist():
            x = finite(value)
            if x is not None: values.append(x)
        return values
    return []


def positive_median(values: list[float]) -> float | None:
    good = [v for v in values if v > 0]
    return statistics.median(good) if good else None


def _text(profile: dict[str, Any]) -> str:
    return " ".join(str(profile.get(k) or "").lower() for k in ("company", "sector", "industry"))


def classify_company(profile: dict[str, Any], features: dict[str, Any]) -> str:
    """Classify valuation family conservatively.

    V5.4 deliberately does NOT classify generic "Computer Hardware" as memory/storage.
    Networking hardware, analog semis, semiconductor equipment, memory/storage and
    software have materially different economics and valuation anchors.
    """
    sector = str(profile.get("sector") or "").lower()
    industry = str(profile.get("industry") or "").lower()
    text = _text(profile)
    forward_pe = finite(profile.get("forward_pe"))
    next_eps = finite(features.get("next_year_eps_estimate"))
    revenue_growth = finite(features.get("next_year_revenue_growth_estimate")) or finite(features.get("revenue_yoy")) or 0.0
    operating_margin = finite(features.get("operating_margin"))
    operating_change = finite(features.get("operating_margin_change_yoy"))

    if "financial" in sector or "real estate" in sector:
        return "SPECIALIST_REQUIRED"
    if any(k in text for k in ("dram", "nand", "memory chip", "memory semiconductor", "hard disk drive", "data storage devices", "disk drive")):
        return "MEMORY_STORAGE_CYCLICAL"
    if any(k in text for k in ("semiconductor equipment", "semiconductor materials", "wafer fabrication equipment")):
        return "SEMICONDUCTOR_EQUIPMENT"
    if any(k in text for k in ("networking hardware", "communication equipment", "ethernet switch", "network equipment")):
        return "NETWORKING_HARDWARE"
    if "semiconductor" in industry or "semiconductor" in text:
        if revenue_growth >= 0.55 and operating_change is not None and operating_change >= 0.25:
            return "SEMICONDUCTOR_CYCLE_EXTREME"
        return "SEMICONDUCTOR_GROWTH"
    if "software" in industry or "software" in text:
        return "SOFTWARE"
    if any(x in sector for x in ["energy", "basic materials"]):
        return "CYCLICAL"
    if (forward_pe is None or forward_pe <= 0) and (next_eps is None or next_eps <= 0) and revenue_growth > 0.10:
        return "EARLY_STAGE_GROWTH"
    if operating_margin is not None and operating_margin < 0.05 and operating_change is not None and operating_change > 0.02:
        return "TURNAROUND"
    if next_eps is not None and next_eps > 0:
        return "PROFITABLE_GROWTH"
    return "GENERAL"


def _scenario(name: str, fair_value: float, assumptions: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "weight": SCENARIO_WEIGHTS[name], "fair_value": round(float(fair_value), 2), "assumptions": assumptions}


def _eps_model(next_eps: float, next_growth: float | None, forward_pe: float | None, horizon: int, family: str) -> dict[str, Any]:
    g = clamp(next_growth if next_growth is not None else 0.08, -0.20, 0.55)
    years = max(1, horizon - 1)
    family_params = {
        "SOFTWARE": (0.55, 14, 28),
        "NETWORKING_HARDWARE": (0.48, 12, 25),
        "SEMICONDUCTOR_GROWTH": (0.42, 11, 24),
        "SEMICONDUCTOR_EQUIPMENT": (0.38, 10, 22),
        "PROFITABLE_GROWTH": (0.50, 10, 24),
        "TURNAROUND": (0.32, 8, 18),
        "GENERAL": (0.40, 9, 21),
    }
    fade, min_pe, max_pe = family_params.get(family, family_params["PROFITABLE_GROWTH"])
    base_growth = clamp(g * fade, -0.03, 0.22)
    bear_growth = clamp(g * 0.08 - 0.04, -0.12, 0.06)
    bull_growth = clamp(g * 0.72 + 0.02, 0.02, 0.30)
    justified = clamp(11.0 + 28.0 * max(base_growth, 0), min_pe, max_pe)
    if forward_pe is not None and 6 <= forward_pe <= 60:
        base_pe = clamp(0.70 * justified + 0.30 * forward_pe, min_pe, max_pe)
    else:
        base_pe = justified
    bear_pe = clamp(base_pe * 0.70, 6, max(10, min_pe + 2))
    bull_pe = clamp(base_pe * 1.20, min_pe + 2, max_pe * 1.15)
    return {
        "name": f"{family}_FORWARD_EPS",
        "family": "earnings",
        "scenarios": [
            _scenario("Bear", next_eps * ((1 + bear_growth) ** years) * bear_pe, {"eps_growth": bear_growth, "exit_pe": bear_pe}),
            _scenario("Base", next_eps * ((1 + base_growth) ** years) * base_pe, {"eps_growth": base_growth, "exit_pe": base_pe}),
            _scenario("Bull", next_eps * ((1 + bull_growth) ** years) * bull_pe, {"eps_growth": bull_growth, "exit_pe": bull_pe}),
        ],
    }


def _cycle_eps_anchor(normalized_eps: float | None, next_eps: float | None, cap_factor: float) -> float | None:
    if normalized_eps and normalized_eps > 0 and next_eps and next_eps > 0:
        return 0.75 * normalized_eps + 0.25 * min(next_eps, normalized_eps * cap_factor)
    if normalized_eps and normalized_eps > 0: return normalized_eps
    if next_eps and next_eps > 0: return next_eps * 0.55
    return None


def _cycle_model(normalized_eps: float | None, next_eps: float | None, horizon: int, family: str) -> dict[str, Any] | None:
    if family == "MEMORY_STORAGE_CYCLICAL":
        anchor, growth, mult = _cycle_eps_anchor(normalized_eps, next_eps, 1.50), (-0.08, 0.03, 0.10), (7, 10, 13)
    elif family == "SEMICONDUCTOR_CYCLE_EXTREME":
        anchor, growth, mult = _cycle_eps_anchor(normalized_eps, next_eps, 1.75), (-0.05, 0.07, 0.16), (9, 14, 20)
    else:
        anchor, growth, mult = _cycle_eps_anchor(normalized_eps, next_eps, 1.45), (-0.06, 0.03, 0.10), (7, 10, 13)
    if not anchor or anchor <= 0: return None
    years = max(1, horizon - 1)
    return {
        "name": f"{family}_NORMALIZED_EPS", "family": "normalized_earnings",
        "scenarios": [
            _scenario("Bear", anchor * ((1 + growth[0]) ** years) * mult[0], {"normalized_eps": anchor, "eps_growth": growth[0], "exit_pe": mult[0]}),
            _scenario("Base", anchor * ((1 + growth[1]) ** years) * mult[1], {"normalized_eps": anchor, "eps_growth": growth[1], "exit_pe": mult[1]}),
            _scenario("Bull", anchor * ((1 + growth[2]) ** years) * mult[2], {"normalized_eps": anchor, "eps_growth": growth[2], "exit_pe": mult[2]}),
        ]
    }


def _fcf_model(fcf_per_traded_share: float, growth_anchor: float, horizon: int, cyclical: bool = False) -> dict[str, Any]:
    if cyclical:
        growth, yields = (-0.05, 0.03, 0.09), (0.10, 0.075, 0.055)
    else:
        g = clamp(growth_anchor, -0.10, 0.25)
        growth = (clamp(g * 0.10 - 0.03, -0.08, 0.04), clamp(g * 0.38, 0, 0.13), clamp(g * 0.68 + 0.02, 0.02, 0.20))
        yields = (0.09, 0.065, 0.05)
    vals = [fcf_per_traded_share * ((1 + growth[i]) ** horizon) / yields[i] for i in range(3)]
    return {"name": "NORMALIZED_FCF_YIELD" if cyclical else "FCF_YIELD", "family": "cash_flow", "scenarios": [
        _scenario("Bear", vals[0], {"fcf_growth": growth[0], "exit_fcf_yield": yields[0]}),
        _scenario("Base", vals[1], {"fcf_growth": growth[1], "exit_fcf_yield": yields[1]}),
        _scenario("Bull", vals[2], {"fcf_growth": growth[2], "exit_fcf_yield": yields[2]}),
    ]}


def _model_value(model: dict[str, Any], name: str) -> float | None:
    row = next((x for x in model.get("scenarios", []) if x.get("name") == name), None)
    return finite(row.get("fair_value")) if row else None


def _agreement(models: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    vals = [x for x in (_model_value(m, "Base") for m in models) if x and x > 0]
    if len(vals) < 2: return None, None
    ratio = max(vals) / min(vals)
    return round(1.0 / (1.0 + abs(math.log(ratio))), 3), round(ratio, 3)


def _ranges(models: list[dict[str, Any]]) -> dict[str, dict[str, float | None]]:
    out = {}
    for name in SCENARIO_WEIGHTS:
        vals = [x for x in (_model_value(m, name) for m in models) if x and x > 0]
        out[name] = {"low": round(min(vals),2), "mid": round(statistics.median(vals),2), "high": round(max(vals),2)} if vals else {"low":None,"mid":None,"high":None}
    return out


def _blend(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for name, weight in SCENARIO_WEIGHTS.items():
        vals = [x for x in (_model_value(m, name) for m in models) if x and x > 0]
        if vals:
            fair = math.exp(sum(math.log(v) for v in vals) / len(vals))
            out.append({"name": name, "weight": weight, "fair_value": round(fair,2), "model_values": [round(v,2) for v in vals]})
    return out


def _unresolved(company_type: str, price: float | None, reason: str, normalization: SecurityNormalization | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "company_type": company_type, "valuation_status": "UNRESOLVED", "valuation_resolved": False,
        "model": "UNAVAILABLE", "models": [], "model_count": 0, "model_agreement": None,
        "model_base_ratio": None, "model_ranges": {}, "reason": reason, "scenarios": [],
        "current_price": round(price,2) if price else None, "expected_value": None, "expected_cagr": None,
        "base_cagr": None, "bear_return": None, "base_return": None, "bull_return": None,
        "critical_flags": [], "warning_flags": warnings or [],
        "security_normalization": normalization.as_dict() if normalization else None,
    }


def build_valuation(profile, features, annual_financials, horizon_years=3, sanity_thresholds=None, normalization: SecurityNormalization | None = None):
    sanity = sanity_thresholds or {}
    price = finite(features.get("price"))
    if not price or price <= 0:
        return _unresolved("UNKNOWN", price, "Current price unavailable.", normalization, ["Current price is unavailable."])
    company_type = classify_company(profile, features)
    if company_type == "SPECIALIST_REQUIRED":
        out = _unresolved(company_type, price, "This sector requires specialist valuation logic.", normalization, ["Automated generic valuation intentionally disabled for this sector."])
        out["valuation_status"] = "SPECIALIST_REQUIRED"
        return out
    if normalization is not None and not normalization.resolved:
        out = _unresolved(company_type, price, normalization.reason, normalization, ["Currency/security-unit normalization is unresolved; no valuation was attempted."])
        out["valuation_status"] = "CURRENCY_UNIT_UNRESOLVED"
        return out

    next_eps = finite(features.get("next_year_eps_estimate"))
    # Analyst EPS is normally expressed in the trading security's currency/unit. Do not transform it.
    next_growth = finite(features.get("next_year_eps_growth"))
    shares = finite(profile.get("shares_outstanding"))
    forward_pe = finite(profile.get("forward_pe"))
    annual_income = annual_financials.get("income", pd.DataFrame())
    annual_cashflow = annual_financials.get("cashflow", pd.DataFrame())
    raw_eps = positive_median(row_values(annual_income, ["Diluted EPS", "Basic EPS", "Diluted EPS Continuing Operations"]))
    raw_fcf = positive_median(row_values(annual_cashflow, ["Free Cash Flow", "FreeCashFlow"])[-4:])

    normalized_eps = raw_eps
    normalized_fcf_total = raw_fcf
    if normalization is not None and normalization.resolved:
        # Statement EPS is per underlying share, so ADR ratio matters.
        normalized_eps = normalization.convert_per_underlying_share(raw_eps) if raw_eps is not None else None
        # Total statement FCF only needs FX conversion; dividing by trading shares below
        # automatically incorporates the ADR/share-count relationship.
        normalized_fcf_total = normalization.convert_total_financial_amount(raw_fcf) if raw_fcf is not None else None

    models: list[dict[str, Any]] = []
    cyclical = company_type in {"MEMORY_STORAGE_CYCLICAL", "SEMICONDUCTOR_CYCLE_EXTREME", "CYCLICAL"}
    if cyclical:
        m = _cycle_model(normalized_eps, next_eps, horizon_years, company_type)
        if m: models.append(m)
    elif next_eps and next_eps > 0 and company_type in {"SOFTWARE","NETWORKING_HARDWARE","SEMICONDUCTOR_GROWTH","SEMICONDUCTOR_EQUIPMENT","PROFITABLE_GROWTH","TURNAROUND","GENERAL"}:
        models.append(_eps_model(next_eps, next_growth, forward_pe, horizon_years, company_type))

    if normalized_fcf_total and normalized_fcf_total > 0 and shares and shares > 0:
        fcf_per_share = normalized_fcf_total / shares
        growth_candidates = [x for x in [finite(features.get("next_year_revenue_growth_estimate")), next_growth] if x is not None]
        models.append(_fcf_model(fcf_per_share, statistics.median(growth_candidates) if growth_candidates else 0.05, horizon_years, cyclical))

    if not models:
        return _unresolved(company_type, price, "No sufficiently reliable valuation method is available.", normalization, ["No usable valuation method."])

    agreement, ratio = _agreement(models)
    ranges = _ranges(models)
    model_count = len(models)
    min_models = int(sanity.get("min_valuation_models_for_buy", 2))
    min_agreement = float(sanity.get("min_model_agreement_for_buy", 0.60))
    max_ratio = float(sanity.get("max_model_base_ratio", 1.90))
    warnings, critical = [], []
    resolved = model_count >= min_models and agreement is not None and agreement >= min_agreement and ratio is not None and ratio <= max_ratio
    for m in models:
        base = _model_value(m, "Base")
        if not base: continue
        multiple = base / price
        if multiple > float(sanity.get("max_individual_model_multiple", 4.0)):
            warnings.append(f"{m['name']} base value is {multiple:.1f}x current price; verify assumptions.")
        if multiple < float(sanity.get("min_individual_model_multiple", 0.15)):
            warnings.append(f"{m['name']} base value is only {multiple:.2f}x current price; verify cycle/unit inputs.")
    if model_count < min_models:
        warnings.append(f"Only {model_count} independent valuation method(s) are usable; {min_models} are required for an actionable buy zone.")
    elif not resolved:
        warnings.append(f"Valuation models disagree too much for an actionable fair value (agreement={agreement}, base-value ratio={ratio}x).")

    scenarios, expected_value = [], None
    expected_cagr = base_cagr = bear_return = base_return = bull_return = None
    if resolved:
        scenarios = _blend(models)
        if len(scenarios) == 3:
            d = {x["name"]: x for x in scenarios}
            expected_value = sum(x["weight"] * x["fair_value"] for x in scenarios)
            expected_cagr = (expected_value / price) ** (1 / horizon_years) - 1
            base_cagr = (d["Base"]["fair_value"] / price) ** (1 / horizon_years) - 1
            bear_return = d["Bear"]["fair_value"] / price - 1
            base_return = d["Base"]["fair_value"] / price - 1
            bull_return = d["Bull"]["fair_value"] / price - 1
            if expected_cagr > float(sanity.get("max_extreme_expected_cagr", 0.50)):
                critical.append(f"Resolved valuation implies an extreme {expected_cagr:.1%} CAGR; suppress action until assumptions are reviewed.")
            if expected_value / price > float(sanity.get("max_expected_value_multiple", 3.0)):
                critical.append(f"Resolved expected fair value is {expected_value/price:.1f}x current price; suppress action until inputs are reviewed.")
            if bear_return > float(sanity.get("max_bear_upside_for_sanity", 1.0)):
                critical.append(f"Even the bear scenario is {bear_return:.1%} above current price; valuation is implausibly optimistic.")
        else:
            resolved = False
    if critical:
        resolved = False; scenarios = []; expected_value = expected_cagr = base_cagr = bear_return = base_return = bull_return = None

    return {
        "company_type": company_type,
        "valuation_status": "RESOLVED" if resolved else "UNRESOLVED",
        "valuation_resolved": resolved,
        "model": "MULTI_MODEL" if model_count > 1 else models[0]["name"],
        "models": models, "model_count": model_count, "model_agreement": agreement, "model_base_ratio": ratio,
        "model_ranges": ranges,
        "reason": "Independent valuation methods agree closely enough to create an actionable blended range." if resolved else "Individual valuation methods are shown, but no buy zone is calculated until they agree and pass sanity checks.",
        "current_price": round(price,2), "horizon_years": horizon_years, "scenarios": scenarios,
        "expected_value": round(expected_value,2) if expected_value is not None else None,
        "expected_cagr": round(expected_cagr,4) if expected_cagr is not None else None,
        "base_cagr": round(base_cagr,4) if base_cagr is not None else None,
        "bear_return": round(bear_return,4) if bear_return is not None else None,
        "base_return": round(base_return,4) if base_return is not None else None,
        "bull_return": round(bull_return,4) if bull_return is not None else None,
        "normalized_eps": round(normalized_eps,4) if normalized_eps is not None else None,
        "normalized_fcf": round(normalized_fcf_total,2) if normalized_fcf_total is not None else None,
        "critical_flags": critical, "warning_flags": list(dict.fromkeys(warnings)),
        "security_normalization": normalization.as_dict() if normalization else None,
    }


def make_decision(valuation, scores, data_quality, thresholds, risk_penalty=0.0):
    if valuation.get("critical_flags"):
        return {"decision":"REVIEW DATA","confidence":"LOW","reason":"Valuation sanity checks failed."}
    if not valuation.get("valuation_resolved"):
        return {"decision":"VALUATION UNRESOLVED","confidence":"LOW","reason":"Independent valuation methods do not support an actionable fair value."}
    cagr, base, bear = finite(valuation.get("expected_cagr")), finite(valuation.get("base_cagr")), finite(valuation.get("bear_return"))
    if cagr is None or base is None or bear is None:
        return {"decision":"VALUATION UNRESOLVED","confidence":"LOW","reason":"Resolved valuation is incomplete."}
    if cagr-risk_penalty >= float(thresholds.get("buy_min_expected_cagr",0.18)) and base >= float(thresholds.get("buy_min_base_cagr",0.12)) and bear >= float(thresholds.get("buy_min_bear_return",-0.35)) and data_quality >= 75:
        d="BUY"
    elif cagr-risk_penalty >= float(thresholds.get("watch_min_expected_cagr",0.08)): d="WATCH"
    else: d="PASS"
    return {"decision":d,"confidence":"MEDIUM","adjusted_expected_cagr":round(cagr-risk_penalty,4),"reason":f"Base CAGR {base:.1%}; expected CAGR {cagr:.1%}; bear return {bear:.1%}."}
