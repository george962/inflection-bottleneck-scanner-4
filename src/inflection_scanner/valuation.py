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
        values: list[float] = []
        for value in df.loc[normalized[key]].tolist():
            x = finite(value)
            if x is not None:
                values.append(x)
        return values
    return []


def positive_median(values: list[float]) -> float | None:
    good = [v for v in values if v > 0]
    return statistics.median(good) if good else None


def _text(profile: dict[str, Any]) -> str:
    return " ".join(
        str(profile.get(k) or "").lower()
        for k in ("company", "sector", "industry")
    )


def classify_company(profile: dict[str, Any], features: dict[str, Any]) -> str:
    """Choose a valuation family before calculating fair value.

    V5.2 deliberately recognizes memory/storage and semiconductor businesses as
    cycle-sensitive. That prevents peak-cycle forward EPS from being compounded
    like a normal secular software-style earnings stream.
    """
    sector = str(profile.get("sector") or "").lower()
    industry = str(profile.get("industry") or "").lower()
    text = _text(profile)
    forward_pe = finite(profile.get("forward_pe"))
    next_eps = finite(features.get("next_year_eps_estimate"))
    revenue_growth = (
        finite(features.get("next_year_revenue_growth_estimate"))
        or finite(features.get("revenue_yoy"))
        or 0.0
    )
    operating_margin = finite(features.get("operating_margin"))
    operating_change = finite(features.get("operating_margin_change_yoy"))

    if "financial" in sector or "real estate" in sector:
        return "SPECIALIST_REQUIRED"

    memory_storage_keywords = (
        "memory",
        "storage",
        "disk drive",
        "hard disk",
        "nand",
        "dram",
        "data storage",
        "computer hardware",
    )
    if any(k in text for k in memory_storage_keywords):
        return "MEMORY_STORAGE_CYCLICAL"

    if "semiconductor" in industry or "semiconductor" in text:
        # A very large simultaneous revenue/margin swing is a strong sign that
        # forward earnings are near a cycle inflection rather than a steady-state
        # secular run rate. Treat that case like memory/storage even when Yahoo's
        # broad industry label is only "Semiconductors".
        if revenue_growth >= 0.40 and operating_change is not None and operating_change >= 0.18:
            return "MEMORY_STORAGE_CYCLICAL"
        return "SEMICONDUCTOR_CYCLICAL_GROWTH"

    if any(x in sector for x in ["energy", "basic materials"]):
        return "CYCLICAL"

    if (
        (forward_pe is None or forward_pe <= 0)
        and (next_eps is None or next_eps <= 0)
        and revenue_growth > 0.10
    ):
        return "EARLY_STAGE_GROWTH"

    if (
        operating_margin is not None
        and operating_margin < 0.05
        and operating_change is not None
        and operating_change > 0.02
    ):
        return "TURNAROUND"

    if next_eps is not None and next_eps > 0:
        return "PROFITABLE_GROWTH"
    return "GENERAL"


def _scenario(name: str, fair_value: float, assumptions: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "weight": SCENARIO_WEIGHTS[name],
        # Compatibility only. These are model weights, not calibrated probabilities.
        "probability": SCENARIO_WEIGHTS[name],
        "fair_value": round(float(fair_value), 2),
        "assumptions": assumptions,
    }


def _forward_eps_model(next_eps, next_growth, forward_pe, horizon_years):
    g = clamp(next_growth if next_growth is not None else 0.08, -0.20, 0.45)
    years = max(1, horizon_years - 1)
    base_growth = clamp(g * 0.50, -0.03, 0.20)
    bear_growth = clamp(g * 0.08 - 0.03, -0.10, 0.06)
    bull_growth = clamp(g * 0.72 + 0.02, 0.02, 0.28)

    justified_pe = clamp(12.0 + 24.0 * max(base_growth, 0), 10.0, 22.0)
    if forward_pe is not None and 6 <= forward_pe <= 40:
        base_pe = clamp(0.65 * justified_pe + 0.35 * clamp(forward_pe, 8, 28), 9, 24)
    else:
        base_pe = justified_pe
    bear_pe = clamp(base_pe * 0.72, 7, 16)
    bull_pe = clamp(base_pe * 1.18, 13, 28)

    return {
        "name": "FORWARD_EPS",
        "family": "earnings",
        "scenarios": [
            _scenario("Bear", next_eps * ((1 + bear_growth) ** years) * bear_pe, {"eps_growth": bear_growth, "exit_pe": bear_pe}),
            _scenario("Base", next_eps * ((1 + base_growth) ** years) * base_pe, {"eps_growth": base_growth, "exit_pe": base_pe}),
            _scenario("Bull", next_eps * ((1 + bull_growth) ** years) * bull_pe, {"eps_growth": bull_growth, "exit_pe": bull_pe}),
        ],
    }


def _cycle_eps_anchor(normalized_eps: float | None, next_eps: float | None, cap_factor: float) -> float | None:
    if normalized_eps is not None and normalized_eps > 0 and next_eps is not None and next_eps > 0:
        capped_forward = min(next_eps, normalized_eps * cap_factor)
        return 0.70 * normalized_eps + 0.30 * capped_forward
    if normalized_eps is not None and normalized_eps > 0:
        return normalized_eps
    # If historical normalized earnings are unavailable, do not treat the full
    # forward number as normalized cycle earnings. Apply a conservative haircut.
    if next_eps is not None and next_eps > 0:
        return next_eps * 0.60
    return None


def _normalized_cycle_eps_model(
    normalized_eps: float | None,
    next_eps: float | None,
    horizon_years: int,
    family: str,
) -> dict[str, Any] | None:
    if family == "MEMORY_STORAGE_CYCLICAL":
        anchor = _cycle_eps_anchor(normalized_eps, next_eps, 1.50)
        growth = (-0.05, 0.04, 0.12)
        multiples = (8.0, 11.0, 14.0)
        name = "NORMALIZED_MEMORY_STORAGE_EPS"
    elif family == "SEMICONDUCTOR_CYCLICAL_GROWTH":
        anchor = _cycle_eps_anchor(normalized_eps, next_eps, 1.90)
        growth = (-0.02, 0.10, 0.20)
        multiples = (11.0, 17.0, 24.0)
        name = "NORMALIZED_SEMICONDUCTOR_EPS"
    else:
        anchor = _cycle_eps_anchor(normalized_eps, next_eps, 1.45)
        growth = (-0.06, 0.03, 0.10)
        multiples = (7.0, 10.0, 13.0)
        name = "NORMALIZED_CYCLE_EPS"

    if anchor is None or anchor <= 0:
        return None

    years = max(1, horizon_years - 1)
    bear_g, base_g, bull_g = growth
    bear_pe, base_pe, bull_pe = multiples
    return {
        "name": name,
        "family": "normalized_earnings",
        "scenarios": [
            _scenario("Bear", anchor * ((1 + bear_g) ** years) * bear_pe, {"normalized_eps": anchor, "eps_growth": bear_g, "exit_pe": bear_pe}),
            _scenario("Base", anchor * ((1 + base_g) ** years) * base_pe, {"normalized_eps": anchor, "eps_growth": base_g, "exit_pe": base_pe}),
            _scenario("Bull", anchor * ((1 + bull_g) ** years) * bull_pe, {"normalized_eps": anchor, "eps_growth": bull_g, "exit_pe": bull_pe}),
        ],
    }


def _fcf_yield_model(fcf_per_share, growth_anchor, horizon_years, cyclical: bool = False):
    if cyclical:
        bear_growth, base_growth, bull_growth = -0.04, 0.03, 0.09
        bear_yield, base_yield, bull_yield = 0.10, 0.075, 0.055
        name = "NORMALIZED_FCF_YIELD"
    else:
        g = clamp(growth_anchor, -0.10, 0.22)
        bear_growth = clamp(g * 0.12 - 0.03, -0.08, 0.04)
        base_growth = clamp(g * 0.40, 0.00, 0.13)
        bull_growth = clamp(g * 0.68 + 0.02, 0.02, 0.20)
        bear_yield, base_yield, bull_yield = 0.09, 0.065, 0.05
        name = "FCF_YIELD"

    bear_fcf = fcf_per_share * ((1 + bear_growth) ** horizon_years)
    base_fcf = fcf_per_share * ((1 + base_growth) ** horizon_years)
    bull_fcf = fcf_per_share * ((1 + bull_growth) ** horizon_years)
    return {
        "name": name,
        "family": "cash_flow",
        "scenarios": [
            _scenario("Bear", bear_fcf / bear_yield, {"fcf_growth": bear_growth, "exit_fcf_yield": bear_yield}),
            _scenario("Base", base_fcf / base_yield, {"fcf_growth": base_growth, "exit_fcf_yield": base_yield}),
            _scenario("Bull", bull_fcf / bull_yield, {"fcf_growth": bull_growth, "exit_fcf_yield": bull_yield}),
        ],
    }


def _revenue_model(next_revenue, shares, growth, current_ps, horizon_years):
    g = clamp(growth, -0.10, 0.40)
    years = max(1, horizon_years - 1)
    base_growth = clamp(g * 0.55, 0.00, 0.20)
    bear_growth = clamp(g * 0.15 - 0.03, -0.08, 0.08)
    bull_growth = clamp(g * 0.78 + 0.02, 0.03, 0.28)

    growth_based_ps = clamp(1.0 + 6.0 * max(base_growth, 0), 1.0, 3.6)
    if current_ps is not None and 0.4 <= current_ps <= 8:
        base_ps = clamp(0.65 * growth_based_ps + 0.35 * min(current_ps, 4.5), 0.8, 4.0)
    else:
        base_ps = growth_based_ps
    bear_ps = clamp(base_ps * 0.60, 0.6, 2.0)
    bull_ps = clamp(base_ps * 1.25, 1.2, 5.0)

    def fair(growth_rate, multiple):
        future_revenue = next_revenue * ((1 + growth_rate) ** years)
        return future_revenue * multiple / shares

    return {
        "name": "FORWARD_REVENUE",
        "family": "revenue",
        "scenarios": [
            _scenario("Bear", fair(bear_growth, bear_ps), {"revenue_growth": bear_growth, "exit_price_sales": bear_ps}),
            _scenario("Base", fair(base_growth, base_ps), {"revenue_growth": base_growth, "exit_price_sales": base_ps}),
            _scenario("Bull", fair(bull_growth, bull_ps), {"revenue_growth": bull_growth, "exit_price_sales": bull_ps}),
        ],
    }


def _model_value(model: dict[str, Any], scenario_name: str) -> float | None:
    row = next((x for x in model.get("scenarios", []) if x.get("name") == scenario_name), None)
    return finite(row.get("fair_value")) if row else None


def _agreement(models: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    base_values = [
        x for x in (_model_value(model, "Base") for model in models)
        if x is not None and x > 0
    ]
    if len(base_values) < 2:
        return None, None
    ratio = max(base_values) / min(base_values)
    score = 1.0 / (1.0 + abs(math.log(ratio)))
    return round(score, 3), round(ratio, 3)


def _model_ranges(models: list[dict[str, Any]]) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for scenario_name in ["Bear", "Base", "Bull"]:
        values = [
            x for x in (_model_value(model, scenario_name) for model in models)
            if x is not None and x > 0
        ]
        if not values:
            out[scenario_name] = {"low": None, "mid": None, "high": None}
        else:
            out[scenario_name] = {
                "low": round(min(values), 2),
                "mid": round(statistics.median(values), 2),
                "high": round(max(values), 2),
            }
    return out


def _geometric_blend(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Blend only after models have passed the agreement gate.

    A geometric mean is less sensitive than an arithmetic midpoint and avoids
    manufacturing a precise-looking value halfway between incompatible models.
    """
    blended: list[dict[str, Any]] = []
    for scenario_name in ["Bear", "Base", "Bull"]:
        values = [
            x for x in (_model_value(model, scenario_name) for model in models)
            if x is not None and x > 0
        ]
        if not values:
            continue
        fair = math.exp(sum(math.log(v) for v in values) / len(values))
        blended.append(
            {
                "name": scenario_name,
                "weight": SCENARIO_WEIGHTS[scenario_name],
                "probability": SCENARIO_WEIGHTS[scenario_name],
                "fair_value": round(fair, 2),
                "model_values": [round(v, 2) for v in values],
            }
        )
    return blended


def build_valuation(profile, features, annual_financials, horizon_years=3, sanity_thresholds=None):
    sanity = sanity_thresholds or {}
    price = finite(features.get("price"))
    if price is None or price <= 0:
        return {
            "company_type": "UNKNOWN",
            "valuation_status": "DATA_ERROR",
            "valuation_resolved": False,
            "model": "UNAVAILABLE",
            "models": [],
            "model_count": 0,
            "model_agreement": None,
            "model_base_ratio": None,
            "model_ranges": {},
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

    if company_type == "SPECIALIST_REQUIRED":
        return {
            "company_type": company_type,
            "valuation_status": "SPECIALIST_REQUIRED",
            "valuation_resolved": False,
            "model": "SPECIALIST_REQUIRED",
            "models": [],
            "model_count": 0,
            "model_agreement": None,
            "model_base_ratio": None,
            "model_ranges": {},
            "reason": "This sector needs specialist valuation logic rather than a generic EPS/FCF model.",
            "scenarios": [],
            "current_price": round(price, 2),
            "horizon_years": horizon_years,
            "critical_flags": [],
            "warning_flags": ["Automated generic valuation intentionally disabled for this sector."],
        }

    annual_income = annual_financials.get("income", pd.DataFrame())
    annual_cashflow = annual_financials.get("cashflow", pd.DataFrame())
    annual_eps = row_values(annual_income, ["Diluted EPS", "Basic EPS", "Diluted EPS Continuing Operations"])
    normalized_eps = positive_median(annual_eps)
    annual_fcf = row_values(annual_cashflow, ["Free Cash Flow", "FreeCashFlow"])
    positive_fcf = [x for x in annual_fcf if x > 0]
    normalized_fcf = positive_median(positive_fcf[-4:]) if positive_fcf else None
    if normalized_fcf is not None and profile_fcf is not None and profile_fcf > 0:
        # Prevent one unusually strong TTM cash-flow print from dominating the
        # cycle-normalized anchor.
        profile_fcf_capped = min(profile_fcf, normalized_fcf * 1.6)
        normalized_fcf = statistics.median([normalized_fcf, profile_fcf_capped])
    elif normalized_fcf is None and profile_fcf is not None and profile_fcf > 0:
        normalized_fcf = profile_fcf

    models: list[dict[str, Any]] = []
    cyclical_family = company_type in {
        "MEMORY_STORAGE_CYCLICAL",
        "SEMICONDUCTOR_CYCLICAL_GROWTH",
        "CYCLICAL",
    }

    if cyclical_family:
        cycle_model = _normalized_cycle_eps_model(normalized_eps, next_eps, horizon_years, company_type)
        if cycle_model:
            models.append(cycle_model)
    elif company_type in {"PROFITABLE_GROWTH", "TURNAROUND", "GENERAL"} and next_eps is not None and next_eps > 0:
        models.append(_forward_eps_model(next_eps, next_eps_growth, forward_pe, horizon_years))

    if normalized_fcf is not None and shares is not None and shares > 0:
        fcf_per_share = normalized_fcf / shares
        growth_candidates = [x for x in [next_revenue_growth, next_eps_growth] if x is not None]
        growth_anchor = statistics.median(growth_candidates) if growth_candidates else 0.05
        if fcf_per_share > 0:
            models.append(_fcf_yield_model(fcf_per_share, growth_anchor, horizon_years, cyclical=cyclical_family))

    # Revenue is a fallback, not a second method used merely to manufacture
    # triangulation when earnings/FCF are already available.
    if not models and company_type in {"EARLY_STAGE_GROWTH", "TURNAROUND", "GENERAL"} and next_revenue and next_revenue > 0 and shares and shares > 0:
        models.append(_revenue_model(next_revenue, shares, next_revenue_growth or 0.10, current_ps, horizon_years))

    if not models:
        return {
            "company_type": company_type,
            "valuation_status": "UNRESOLVED",
            "valuation_resolved": False,
            "model": "NEEDS_SPECIALIST_VALUATION",
            "models": [],
            "model_count": 0,
            "model_agreement": None,
            "model_base_ratio": None,
            "model_ranges": {},
            "reason": "No sufficiently reliable generic valuation method is available.",
            "scenarios": [],
            "current_price": round(price, 2),
            "horizon_years": horizon_years,
            "critical_flags": [],
            "warning_flags": ["No usable valuation method."],
        }

    agreement, base_ratio = _agreement(models)
    model_ranges = _model_ranges(models)
    min_agreement = float(sanity.get("min_model_agreement_for_buy", 0.60))
    max_ratio = float(sanity.get("max_model_base_ratio", 1.90))
    min_models = int(sanity.get("min_valuation_models_for_buy", 2))

    warning_flags: list[str] = []
    critical_flags: list[str] = []
    model_count = len(models)

    for model in models:
        base_value = _model_value(model, "Base")
        if base_value is None:
            continue
        multiple = base_value / price
        if multiple > float(sanity.get("max_individual_model_multiple", 4.0)):
            warning_flags.append(
                f"{model['name']} base value is {multiple:.1f}x current price; treat that model as an outlier until assumptions are verified."
            )
        if multiple < float(sanity.get("min_individual_model_multiple", 0.15)):
            warning_flags.append(
                f"{model['name']} base value is only {multiple:.2f}x current price; valuation inputs may represent a depressed or mismatched cycle."
            )

    valuation_resolved = bool(
        model_count >= min_models
        and agreement is not None
        and agreement >= min_agreement
        and base_ratio is not None
        and base_ratio <= max_ratio
    )

    if model_count < min_models:
        warning_flags.append(
            f"Only {model_count} independent valuation method(s) are usable; {min_models} are required for an actionable buy zone."
        )
    elif not valuation_resolved:
        warning_flags.append(
            f"Valuation models disagree too much for an actionable fair value (agreement={agreement}, base-value ratio={base_ratio}x)."
        )

    implied_forward_pe = price / next_eps if next_eps is not None and next_eps > 0 else None
    min_implied_pe = float(sanity.get("min_implied_forward_pe", 3.0))
    max_implied_pe = float(sanity.get("max_implied_forward_pe", 80.0))
    if implied_forward_pe is not None and implied_forward_pe < min_implied_pe:
        if cyclical_family:
            warning_flags.append(
                f"Implied forward P/E is only {implied_forward_pe:.2f}x; for a cyclical business this may reflect peak-cycle earnings rather than true cheapness."
            )
        else:
            critical_flags.append(
                f"Current price ÷ next-year EPS implies only {implied_forward_pe:.2f}x earnings; validate the EPS input before relying on valuation."
            )
    if implied_forward_pe is not None and implied_forward_pe > max_implied_pe:
        warning_flags.append(f"Implied forward P/E is {implied_forward_pe:.1f}x.")

    if critical_flags:
        valuation_resolved = False

    scenarios: list[dict[str, Any]] = []
    expected_value = expected_cagr = base_cagr = None
    bear_return = base_return = bull_return = None
    scenario_support = None

    if valuation_resolved:
        scenarios = _geometric_blend(models)
        if len(scenarios) == 3:
            by_name = {x["name"]: x for x in scenarios}
            bear, base, bull = by_name["Bear"], by_name["Base"], by_name["Bull"]
            expected_value = sum(x["weight"] * x["fair_value"] for x in scenarios)
            expected_cagr = (expected_value / price) ** (1 / horizon_years) - 1 if expected_value > 0 else None
            base_cagr = (base["fair_value"] / price) ** (1 / horizon_years) - 1 if base["fair_value"] > 0 else None
            bear_return = bear["fair_value"] / price - 1
            base_return = base["fair_value"] / price - 1
            bull_return = bull["fair_value"] / price - 1
            scenario_support = sum(x["weight"] for x in scenarios if x["fair_value"] > price)

            max_cagr = float(sanity.get("max_extreme_expected_cagr", 0.50))
            max_multiple = float(sanity.get("max_expected_value_multiple", 3.0))
            max_bear_upside = float(sanity.get("max_bear_upside_for_sanity", 1.0))
            if expected_cagr is not None and expected_cagr > max_cagr:
                critical_flags.append(
                    f"Resolved valuation still implies an extreme {expected_cagr:.1%} CAGR; suppress buy action until assumptions are reviewed."
                )
            if expected_value is not None and expected_value / price > max_multiple:
                critical_flags.append(
                    f"Resolved expected fair value is {expected_value / price:.1f}x current price; suppress buy action until inputs are reviewed."
                )
            if bear_return is not None and bear_return > max_bear_upside:
                critical_flags.append(
                    f"Even the bear scenario is {bear_return:.1%} above current price; this is too optimistic for an actionable model."
                )
            if critical_flags:
                valuation_resolved = False
                scenarios = []
                expected_value = expected_cagr = base_cagr = None
                bear_return = base_return = bull_return = None
                scenario_support = None
        else:
            valuation_resolved = False
            warning_flags.append("Resolved models did not produce a complete three-scenario blend.")

    status = "RESOLVED" if valuation_resolved else "UNRESOLVED"
    reason = (
        "Independent valuation methods agree closely enough to create an actionable blended range. "
        "The blend uses a geometric mean only after the agreement gate passes."
        if valuation_resolved
        else "Individual valuation methods are shown, but no buy zone should be calculated until they agree sufficiently."
    )

    return {
        "company_type": company_type,
        "valuation_status": status,
        "valuation_resolved": valuation_resolved,
        "model": "MULTI_MODEL" if model_count > 1 else models[0]["name"],
        "models": models,
        "model_count": model_count,
        "model_agreement": agreement,
        "model_base_ratio": base_ratio,
        "model_ranges": model_ranges,
        "reason": reason,
        "current_price": round(price, 2),
        "horizon_years": horizon_years,
        "scenarios": scenarios,
        "expected_value": round(expected_value, 2) if expected_value is not None else None,
        "expected_cagr": round(expected_cagr, 4) if expected_cagr is not None else None,
        "base_cagr": round(base_cagr, 4) if base_cagr is not None else None,
        "bear_return": round(bear_return, 4) if bear_return is not None else None,
        "base_return": round(base_return, 4) if base_return is not None else None,
        "bull_return": round(bull_return, 4) if bull_return is not None else None,
        "bear_downside": round(bear_return, 4) if bear_return is not None else None,
        "scenario_support_weight": round(scenario_support, 4) if scenario_support is not None else None,
        "probability_profit": round(scenario_support, 4) if scenario_support is not None else None,
        "implied_forward_pe": round(implied_forward_pe, 2) if implied_forward_pe is not None else None,
        "normalized_eps": round(normalized_eps, 4) if normalized_eps is not None else None,
        "normalized_fcf": round(normalized_fcf, 2) if normalized_fcf is not None else None,
        "critical_flags": critical_flags,
        "warning_flags": list(dict.fromkeys(warning_flags)),
    }


def make_decision(valuation, scores, data_quality, thresholds, risk_penalty=0.0):
    """Compatibility helper for older CLI/tests.

    V5.2's primary action comes from conviction.py. This helper intentionally
    refuses to emit BUY when the valuation is unresolved.
    """
    if valuation.get("critical_flags"):
        return {
            "decision": "REVIEW DATA",
            "confidence": "LOW",
            "reason": "Valuation sanity checks failed.",
        }
    if not valuation.get("valuation_resolved"):
        return {
            "decision": "VALUATION UNRESOLVED",
            "confidence": "LOW",
            "reason": "Independent valuation methods do not yet support an actionable fair value.",
        }

    cagr = finite(valuation.get("expected_cagr"))
    base_cagr = finite(valuation.get("base_cagr"))
    bear_return = finite(valuation.get("bear_return"))
    if cagr is None or base_cagr is None or bear_return is None:
        return {"decision": "VALUATION UNRESOLVED", "confidence": "LOW", "reason": "Resolved valuation is incomplete."}

    buy_cagr = float(thresholds.get("buy_min_expected_cagr", 0.18))
    buy_base = float(thresholds.get("buy_min_base_cagr", 0.12))
    buy_bear = float(thresholds.get("buy_min_bear_return", -0.35))
    adjusted_cagr = cagr - risk_penalty
    if adjusted_cagr >= buy_cagr and base_cagr >= buy_base and bear_return >= buy_bear and data_quality >= 75:
        decision = "BUY"
    elif adjusted_cagr >= float(thresholds.get("watch_min_expected_cagr", 0.08)):
        decision = "WATCH"
    else:
        decision = "PASS"
    return {
        "decision": decision,
        "confidence": "MEDIUM",
        "adjusted_expected_cagr": round(adjusted_cagr, 4),
        "reason": f"Resolved base CAGR {base_cagr:.1%}; expected CAGR {cagr:.1%}; bear return {bear_return:.1%}.",
    }
