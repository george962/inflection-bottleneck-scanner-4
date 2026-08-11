from __future__ import annotations

import math
import statistics
from typing import Any

import pandas as pd


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
            if x is not None:
                values.append(x)
        return values
    return []


def positive_median(values: list[float]) -> float | None:
    good = [v for v in values if v > 0]
    return statistics.median(good) if good else None


def classify_company(profile: dict[str, Any], features: dict[str, Any]) -> str:
    sector = str(profile.get("sector") or "").lower()
    forward_pe = finite(profile.get("forward_pe"))
    next_eps = finite(features.get("next_year_eps_estimate"))
    revenue_growth = finite(features.get("next_year_revenue_growth_estimate")) or finite(features.get("revenue_yoy")) or 0.0
    operating_margin = finite(features.get("operating_margin"))
    operating_change = finite(features.get("operating_margin_change_yoy"))

    if "financial" in sector or "real estate" in sector:
        return "SPECIAL_CASE"
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
    return {
        "name": name,
        "weight": SCENARIO_WEIGHTS[name],
        "probability": SCENARIO_WEIGHTS[name],  # compatibility only
        "fair_value": round(fair_value, 2),
        "assumptions": assumptions,
    }


def _forward_eps_model(price, next_eps, next_growth, forward_pe, horizon_years):
    g = clamp(next_growth if next_growth is not None else 0.08, -0.20, 0.60)
    years = max(1, horizon_years - 1)
    base_growth = clamp(g * 0.55, -0.03, 0.25)
    bear_growth = clamp(g * 0.10 - 0.03, -0.10, 0.08)
    bull_growth = clamp(g * 0.80 + 0.02, 0.02, 0.35)

    justified_pe = clamp(12.0 + 25.0 * max(base_growth, 0), 10.0, 24.0)
    if forward_pe is not None and 5 <= forward_pe <= 45:
        base_pe = clamp(0.60 * justified_pe + 0.40 * clamp(forward_pe, 8, 30), 9, 26)
    else:
        base_pe = justified_pe
    bear_pe = clamp(base_pe * 0.70, 7, 16)
    bull_pe = clamp(base_pe * 1.18, 13, 30)

    bear_eps = next_eps * ((1 + bear_growth) ** years)
    base_eps = next_eps * ((1 + base_growth) ** years)
    bull_eps = next_eps * ((1 + bull_growth) ** years)

    return {
        "name": "FORWARD_EPS",
        "scenarios": [
            _scenario("Bear", bear_eps * bear_pe, {"eps_growth": bear_growth, "exit_pe": bear_pe}),
            _scenario("Base", base_eps * base_pe, {"eps_growth": base_growth, "exit_pe": base_pe}),
            _scenario("Bull", bull_eps * bull_pe, {"eps_growth": bull_growth, "exit_pe": bull_pe}),
        ],
    }


def _normalized_cyclical_model(normalized_eps):
    return {
        "name": "NORMALIZED_CYCLICAL_EPS",
        "scenarios": [
            _scenario("Bear", normalized_eps * 0.70 * 8, {"normalized_eps_factor": 0.70, "exit_pe": 8}),
            _scenario("Base", normalized_eps * 1.00 * 11, {"normalized_eps_factor": 1.00, "exit_pe": 11}),
            _scenario("Bull", normalized_eps * 1.25 * 14, {"normalized_eps_factor": 1.25, "exit_pe": 14}),
        ],
    }


def _fcf_yield_model(fcf_per_share, growth_anchor, horizon_years):
    g = clamp(growth_anchor, -0.10, 0.25)
    bear_growth = clamp(g * 0.15 - 0.03, -0.08, 0.05)
    base_growth = clamp(g * 0.45, 0.00, 0.15)
    bull_growth = clamp(g * 0.70 + 0.02, 0.02, 0.22)

    bear_fcf = fcf_per_share * ((1 + bear_growth) ** horizon_years)
    base_fcf = fcf_per_share * ((1 + base_growth) ** horizon_years)
    bull_fcf = fcf_per_share * ((1 + bull_growth) ** horizon_years)

    return {
        "name": "FCF_YIELD",
        "scenarios": [
            _scenario("Bear", bear_fcf / 0.09, {"fcf_growth": bear_growth, "exit_fcf_yield": 0.09}),
            _scenario("Base", base_fcf / 0.065, {"fcf_growth": base_growth, "exit_fcf_yield": 0.065}),
            _scenario("Bull", bull_fcf / 0.05, {"fcf_growth": bull_growth, "exit_fcf_yield": 0.05}),
        ],
    }


def _revenue_model(next_revenue, shares, growth, current_ps, horizon_years):
    g = clamp(growth, -0.10, 0.50)
    years = max(1, horizon_years - 1)
    base_growth = clamp(g * 0.65, 0.00, 0.25)
    bear_growth = clamp(g * 0.20 - 0.03, -0.08, 0.10)
    bull_growth = clamp(g * 0.85 + 0.02, 0.03, 0.35)

    growth_based_ps = clamp(1.0 + 7.0 * max(base_growth, 0), 1.0, 4.0)
    if current_ps is not None and 0.4 <= current_ps <= 10:
        base_ps = clamp(0.60 * growth_based_ps + 0.40 * min(current_ps, 5.0), 0.8, 4.5)
    else:
        base_ps = growth_based_ps
    bear_ps = clamp(base_ps * 0.60, 0.6, 2.2)
    bull_ps = clamp(base_ps * 1.25, 1.2, 5.5)

    def fair(growth_rate, multiple):
        future_revenue = next_revenue * ((1 + growth_rate) ** years)
        return future_revenue * multiple / shares

    return {
        "name": "FORWARD_REVENUE",
        "scenarios": [
            _scenario("Bear", fair(bear_growth, bear_ps), {"revenue_growth": bear_growth, "exit_price_sales": bear_ps}),
            _scenario("Base", fair(base_growth, base_ps), {"revenue_growth": base_growth, "exit_price_sales": base_ps}),
            _scenario("Bull", fair(bull_growth, bull_ps), {"revenue_growth": bull_growth, "exit_price_sales": bull_ps}),
        ],
    }


def _blend_models(models):
    if not models:
        return [], None
    blended = []
    for scenario_name in ["Bear", "Base", "Bull"]:
        values = []
        for model in models:
            row = next((x for x in model["scenarios"] if x["name"] == scenario_name), None)
            if row and finite(row.get("fair_value")) is not None:
                values.append(float(row["fair_value"]))
        if not values:
            continue
        blended.append(
            {
                "name": scenario_name,
                "weight": SCENARIO_WEIGHTS[scenario_name],
                "probability": SCENARIO_WEIGHTS[scenario_name],
                "fair_value": round(statistics.median(values), 2),
                "model_values": [round(x, 2) for x in values],
            }
        )

    base_values = []
    for model in models:
        row = next((x for x in model["scenarios"] if x["name"] == "Base"), None)
        value = finite(row.get("fair_value")) if row else None
        if value is not None and value > 0:
            base_values.append(value)
    agreement = None if len(base_values) < 2 else 1.0 / (1.0 + abs(math.log(max(base_values) / min(base_values))))
    return blended, round(agreement, 3) if agreement is not None else None


def build_valuation(profile, features, annual_financials, horizon_years=3, sanity_thresholds=None):
    sanity = sanity_thresholds or {}
    price = finite(features.get("price"))
    if price is None or price <= 0:
        return {
            "model": "UNAVAILABLE",
            "models": [],
            "model_count": 0,
            "scenarios": [],
            "critical_flags": ["Current price is unavailable."],
            "warning_flags": [],
            "reason": "Current price unavailable.",
        }

    company_type = classify_company(profile, features)
    next_eps = finite(features.get("next_year_eps_estimate"))
    next_eps_growth = finite(features.get("next_year_eps_growth"))
    next_revenue = finite(features.get("next_year_revenue_estimate"))
    next_revenue_growth = finite(features.get("next_year_revenue_growth_estimate"))
    shares = finite(profile.get("shares_outstanding"))
    forward_pe = finite(profile.get("forward_pe"))
    current_ps = finite(profile.get("price_to_sales"))
    profile_fcf = finite(profile.get("free_cashflow"))

    annual_income = annual_financials.get("income", pd.DataFrame())
    annual_cashflow = annual_financials.get("cashflow", pd.DataFrame())
    annual_eps = row_values(annual_income, ["Diluted EPS", "Basic EPS", "Diluted EPS Continuing Operations"])
    normalized_eps = positive_median(annual_eps)
    annual_fcf = row_values(annual_cashflow, ["Free Cash Flow", "FreeCashFlow"])
    fcf_candidates = [x for x in annual_fcf[-3:] if x > 0]
    if profile_fcf is not None and profile_fcf > 0:
        fcf_candidates.append(profile_fcf)
    normalized_fcf = statistics.median(fcf_candidates) if fcf_candidates else None

    models = []
    if company_type == "CYCLICAL":
        eps_candidates = [x for x in [normalized_eps, next_eps] if x is not None and x > 0]
        if eps_candidates:
            models.append(_normalized_cyclical_model(statistics.median(eps_candidates)))
    elif company_type in {"PROFITABLE_GROWTH", "TURNAROUND", "GENERAL"} and next_eps is not None and next_eps > 0:
        models.append(_forward_eps_model(price, next_eps, next_eps_growth, forward_pe, horizon_years))

    if normalized_fcf is not None and shares is not None and shares > 0:
        fcf_per_share = normalized_fcf / shares
        growth_candidates = [x for x in [next_revenue_growth, next_eps_growth] if x is not None]
        growth_anchor = statistics.median(growth_candidates) if growth_candidates else 0.05
        if fcf_per_share > 0:
            models.append(_fcf_yield_model(fcf_per_share, growth_anchor, horizon_years))

    if not models and company_type in {"EARLY_STAGE_GROWTH", "TURNAROUND", "GENERAL"} and next_revenue is not None and next_revenue > 0 and shares is not None and shares > 0:
        models.append(_revenue_model(next_revenue, shares, next_revenue_growth if next_revenue_growth is not None else 0.10, current_ps, horizon_years))

    if not models:
        return {
            "company_type": company_type,
            "model": "NEEDS_SPECIALIST_VALUATION",
            "models": [],
            "model_count": 0,
            "model_agreement": None,
            "reason": "Generic earnings/revenue/FCF valuation is not reliable for this company.",
            "scenarios": [],
            "current_price": price,
            "critical_flags": [],
            "warning_flags": ["No usable generic valuation method."],
        }

    scenarios, agreement = _blend_models(models)
    if len(scenarios) != 3:
        return {
            "company_type": company_type,
            "model": "INCOMPLETE",
            "models": models,
            "model_count": len(models),
            "model_agreement": agreement,
            "reason": "Scenario blend is incomplete.",
            "scenarios": scenarios,
            "current_price": price,
            "critical_flags": ["Valuation scenario blend is incomplete."],
            "warning_flags": [],
        }

    by_name = {x["name"]: x for x in scenarios}
    bear, base, bull = by_name["Bear"], by_name["Base"], by_name["Bull"]
    expected_value = sum(x["weight"] * x["fair_value"] for x in scenarios)
    expected_cagr = (expected_value / price) ** (1 / horizon_years) - 1 if expected_value > 0 else None
    base_cagr = (base["fair_value"] / price) ** (1 / horizon_years) - 1 if base["fair_value"] > 0 else None
    bear_return = bear["fair_value"] / price - 1
    base_return = base["fair_value"] / price - 1
    bull_return = bull["fair_value"] / price - 1
    scenario_support = sum(x["weight"] for x in scenarios if x["fair_value"] > price)

    critical_flags = []
    warning_flags = []
    implied_forward_pe = price / next_eps if next_eps is not None and next_eps > 0 else None
    min_implied_pe = float(sanity.get("min_implied_forward_pe", 3.0))
    max_implied_pe = float(sanity.get("max_implied_forward_pe", 80.0))

    if implied_forward_pe is not None and company_type != "CYCLICAL" and implied_forward_pe < min_implied_pe:
        critical_flags.append(
            f"Current price ÷ next-year EPS implies only {implied_forward_pe:.2f}x earnings. That is unusual enough to require manual data validation."
        )
    if implied_forward_pe is not None and implied_forward_pe > max_implied_pe:
        warning_flags.append(f"Implied forward P/E is {implied_forward_pe:.1f}x.")

    max_cagr = float(sanity.get("max_extreme_expected_cagr", 0.50))
    if expected_cagr is not None and expected_cagr > max_cagr:
        critical_flags.append(f"Scenario-weighted CAGR is an extreme {expected_cagr:.1%}; suppress BUY until inputs are validated.")

    max_multiple = float(sanity.get("max_expected_value_multiple", 3.0))
    if expected_value / price > max_multiple:
        critical_flags.append(f"Scenario-weighted fair value is {expected_value / price:.1f}x the current price.")

    max_bear_upside = float(sanity.get("max_bear_upside_for_sanity", 1.0))
    if bear_return > max_bear_upside:
        critical_flags.append(f"Even the bear scenario is {bear_return:.1%} above the current price; this is probably a model/input anomaly.")

    if len(models) < 2:
        warning_flags.append("Only one valuation method is available. A normal BUY requires corroboration from a second method.")
    if agreement is not None and agreement < 0.55:
        warning_flags.append(f"Valuation methods disagree materially (agreement {agreement:.2f}).")
    if next_eps_growth is not None and abs(next_eps_growth) > 2.0:
        warning_flags.append(f"Reported next-year EPS growth is extreme ({next_eps_growth:.1%}); percentage growth may be unstable around a turnaround/loss year.")

    return {
        "company_type": company_type,
        "model": "MULTI_MODEL" if len(models) > 1 else models[0]["name"],
        "models": models,
        "model_count": len(models),
        "model_agreement": agreement,
        "reason": "Scenario values are the median of available valuation methods. Fixed bear/base/bull weights are scenario weights, not statistically calibrated probabilities.",
        "current_price": round(price, 2),
        "horizon_years": horizon_years,
        "scenarios": scenarios,
        "expected_value": round(expected_value, 2),
        "expected_cagr": round(expected_cagr, 4) if expected_cagr is not None else None,
        "base_cagr": round(base_cagr, 4) if base_cagr is not None else None,
        "bear_return": round(bear_return, 4),
        "base_return": round(base_return, 4),
        "bull_return": round(bull_return, 4),
        "bear_downside": round(bear_return, 4),  # compatibility alias
        "scenario_support_weight": round(scenario_support, 4),
        "probability_profit": round(scenario_support, 4),  # compatibility alias; not a calibrated probability
        "implied_forward_pe": round(implied_forward_pe, 2) if implied_forward_pe is not None else None,
        "critical_flags": critical_flags,
        "warning_flags": warning_flags,
    }


def make_decision(valuation, scores, data_quality, thresholds, risk_penalty=0.0):
    cagr = finite(valuation.get("expected_cagr"))
    base_cagr = finite(valuation.get("base_cagr"))
    support = finite(valuation.get("scenario_support_weight"))
    if support is None:
        support = finite(valuation.get("probability_profit"))
    bear_return = finite(valuation.get("bear_return"))
    if bear_return is None:
        bear_return = finite(valuation.get("bear_downside"))
    maturity = finite(scores.get("price_maturity")) or 0.0

    if valuation.get("critical_flags"):
        return {
            "decision": "REVIEW DATA",
            "confidence": "LOW",
            "reason": "Valuation sanity checks failed; do not treat the modeled upside as investable until inputs are validated.",
        }
    if valuation.get("model") in {"UNAVAILABLE", "NEEDS_SPECIALIST_VALUATION", "INCOMPLETE"}:
        return {"decision": "WATCH", "confidence": "LOW", "reason": "Generic valuation is not reliable enough for an automated buy/pass call."}
    if cagr is None or base_cagr is None or support is None or bear_return is None:
        return {"decision": "WATCH", "confidence": "LOW", "reason": "Scenario valuation is incomplete."}

    buy_cagr = float(thresholds.get("buy_min_expected_cagr", 0.18))
    buy_base = float(thresholds.get("buy_min_base_cagr", 0.12))
    buy_support = float(thresholds.get("buy_min_scenario_support", 0.75))
    buy_bear = float(thresholds.get("buy_min_bear_return", -0.35))
    small_cagr = float(thresholds.get("small_buy_min_expected_cagr", 0.16))
    watch_cagr = float(thresholds.get("watch_min_expected_cagr", 0.08))
    late = float(thresholds.get("too_late_maturity", 75))
    adjusted_cagr = cagr - risk_penalty
    model_count = int(valuation.get("model_count") or 0)
    agreement = finite(valuation.get("model_agreement"))

    if (
        adjusted_cagr >= buy_cagr
        and base_cagr >= buy_base
        and support >= buy_support
        and bear_return >= buy_bear
        and data_quality >= 75
        and model_count >= 2
        and agreement is not None
        and agreement >= 0.55
    ):
        decision = "BUY"
    elif adjusted_cagr >= small_cagr and base_cagr >= 0.10 and bear_return >= -0.45:
        decision = "SMALL BUY / SPECULATIVE"
    elif maturity >= late and adjusted_cagr < 0.15:
        decision = "TOO LATE"
    elif adjusted_cagr >= watch_cagr:
        decision = "WATCH"
    else:
        decision = "PASS"

    coverage = float(scores.get("weighted_coverage") or 0) / 100.0
    agreement_component = agreement or 0.0
    confidence_score = (
        0.45 * min(max(data_quality / 100.0, 0), 1)
        + 0.30 * min(max(coverage, 0), 1)
        + 0.25 * min(max(agreement_component, 0), 1)
    )
    confidence = "HIGH" if confidence_score >= 0.78 else "MEDIUM" if confidence_score >= 0.60 else "LOW"
    return {
        "decision": decision,
        "confidence": confidence,
        "confidence_score": round(confidence_score, 3),
        "adjusted_expected_cagr": round(adjusted_cagr, 4),
        "reason": (
            f"Scenario-weighted {valuation.get('horizon_years', 3)}Y CAGR {cagr:.1%}; "
            f"base-case CAGR {base_cagr:.1%}; scenario support weight {support:.0%}; "
            f"bear-case return {bear_return:.1%}; price maturity {maturity:.0f}/100."
        ),
    }
