from __future__ import annotations

import math
from typing import Any


def finite(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def linear(value: float | None, bad: float, good: float, neutral: float = 50.0) -> float:
    if value is None:
        return neutral
    if good == bad:
        return neutral
    return clamp(100.0 * (value - bad) / (good - bad))


def peaked(value: float | None, lo: float, ideal: float, hi: float, neutral: float = 50.0) -> float:
    if value is None:
        return neutral
    if value <= lo or value >= hi:
        return 0.0
    if value <= ideal:
        return clamp(100.0 * (value - lo) / (ideal - lo))
    return clamp(100.0 * (hi - value) / (hi - ideal))


def average(values: list[float | None], default: float = 50.0) -> float:
    clean = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    return sum(clean) / len(clean) if clean else default


def _scenario(valuation: dict[str, Any], name: str) -> dict[str, Any]:
    return next((x for x in valuation.get("scenarios", []) if x.get("name") == name), {})


def _fundamental_pillar(features: dict[str, Any]) -> float:
    return average(
        [
            linear(finite(features.get("revenue_acceleration")), -0.10, 0.15),
            linear(finite(features.get("operating_margin_change_yoy")), -0.05, 0.08),
            linear(finite(features.get("gross_margin_change_yoy")), -0.04, 0.06),
            linear(finite(features.get("next_year_revenue_growth_estimate")), -0.02, 0.25),
            linear(finite(features.get("next_year_eps_growth")), -0.10, 0.40),
            linear(finite(features.get("free_cash_flow_margin_change_yoy")), -0.05, 0.08),
        ]
    )


def _revision_pillar(features: dict[str, Any]) -> float:
    return average(
        [
            linear(finite(features.get("eps_revision_30d")), -0.05, 0.15),
            linear(finite(features.get("eps_revision_90d")), -0.10, 0.25),
            linear(finite(features.get("revision_breadth_30d")), -0.75, 0.75),
            linear(finite(features.get("eps_revision_acceleration")), -0.08, 0.12),
            linear(finite(features.get("avg_eps_surprise_last4")), -0.05, 0.15),
        ]
    )


def _valuation_pillar(valuation: dict[str, Any]) -> float:
    return average(
        [
            linear(finite(valuation.get("base_cagr")), 0.02, 0.25),
            linear(finite(valuation.get("expected_cagr")), 0.03, 0.28),
            linear(finite(valuation.get("bear_return")), -0.55, 0.05),
            linear(finite(valuation.get("model_agreement")), 0.40, 0.85),
            linear(float(valuation.get("model_count") or 0), 1, 3),
        ]
    )


def _timing_pillar(features: dict[str, Any], scores: dict[str, Any]) -> float:
    maturity = finite(scores.get("price_maturity"))
    r12 = finite(features.get("return_12m"))
    r3 = finite(features.get("return_3m"))
    # Moderate confirmation is useful; a huge prior rerating is not automatically fatal,
    # but it makes BUY NOW harder because much more success may already be reflected.
    return average(
        [
            linear(100.0 - maturity if maturity is not None else None, 10, 90),
            peaked(r12, -0.35, 0.25, 1.40),
            peaked(r3, -0.20, 0.15, 0.65),
        ]
    )


def _quality_pillar(trust: dict[str, Any]) -> float:
    market_cap = finite(trust.get("market_cap"))
    years = finite(trust.get("years_public"))
    analysts = finite(trust.get("analyst_count"))
    trust_score = finite(trust.get("trust_score"))
    liquidity = finite(trust.get("dollar_volume_20d"))

    size_score = 50.0
    if market_cap is not None and market_cap > 0:
        # $7.5B ~= 35, $15B ~= 55, $25B ~= 67, $50B ~= 82, $100B+ ~= 96.
        size_score = clamp(15.0 + 27.0 * math.log10(max(market_cap, 1) / 1_000_000_000))

    return average(
        [
            trust_score,
            size_score,
            linear(years, 3, 20),
            linear(analysts, 5, 25),
            linear(liquidity, 20_000_000, 500_000_000),
        ]
    )


def _evidence_pillar(evidence_summary: dict[str, Any], trust: dict[str, Any]) -> float:
    filings = finite(trust.get("filing_count")) or 0
    pos = finite(evidence_summary.get("positive_count")) or 0
    neg = finite(evidence_summary.get("negative_count")) or 0
    topics = len(evidence_summary.get("topics_found", []) or [])
    tone = (pos - neg) / max(1.0, pos + neg)
    return average(
        [
            linear(filings, 0, 5),
            linear(topics, 1, 7),
            linear(tone, -0.70, 0.50),
        ]
    )


def build_conviction(
    snapshot: dict[str, Any],
    valuation: dict[str, Any],
    trust: dict[str, Any],
    evidence_summary: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    features = snapshot.get("features", {})
    scores = snapshot.get("scores", {})
    current_price = finite(features.get("price"))
    base = _scenario(valuation, "Base")
    base_fair = finite(base.get("fair_value"))
    horizon = int(valuation.get("horizon_years") or 3)

    required_base_cagr = float(cfg.get("required_base_cagr", 0.15))
    required_expected_cagr = float(cfg.get("required_expected_cagr", 0.18))
    min_bear_return = float(cfg.get("min_bear_return", -0.30))
    buy_now_min = float(cfg.get("buy_now_min_score", 80))
    pullback_min = float(cfg.get("buy_on_pullback_min_score", 74))
    watch_min = float(cfg.get("watch_min_score", 58))
    pillar_min = float(cfg.get("pillar_minimum_for_buy", 55))
    max_buy_zone_premium = float(cfg.get("max_buy_zone_premium", 0.03))
    late_gap = float(cfg.get("late_too_expensive_gap", 0.15))

    buy_below = None
    if base_fair is not None and base_fair > 0:
        buy_below = base_fair / ((1.0 + required_base_cagr) ** horizon)

    gap_to_buy_zone = None
    if current_price is not None and buy_below is not None and buy_below > 0:
        gap_to_buy_zone = current_price / buy_below - 1.0

    pillars = {
        "fundamental_inflection": round(_fundamental_pillar(features), 1),
        "estimate_revision": round(_revision_pillar(features), 1),
        "valuation": round(_valuation_pillar(valuation), 1),
        "price_timing": round(_timing_pillar(features, scores), 1),
        "company_quality": round(_quality_pillar(trust), 1),
        "evidence": round(_evidence_pillar(evidence_summary, trust), 1),
    }

    weights = cfg.get("weights", {}) or {}
    total_weight = sum(float(weights.get(k, 0)) for k in pillars) or 100.0
    conviction_score = sum(
        pillars[k] * float(weights.get(k, 0)) for k in pillars
    ) / total_weight

    expected_cagr = finite(valuation.get("expected_cagr"))
    base_cagr = finite(valuation.get("base_cagr"))
    bear_return = finite(valuation.get("bear_return"))
    model_count = int(valuation.get("model_count") or 0)
    model_agreement = finite(valuation.get("model_agreement"))
    risk_tier = str(trust.get("risk_tier") or "SPECULATIVE")
    trust_score = finite(trust.get("trust_score")) or 0.0

    checks = {
        "large_established_company": risk_tier == "CORE" and bool(trust.get("preferred_large_cap")),
        "data_trust": trust_score >= 85 and not trust.get("critical_flags"),
        "multiple_valuation_methods": model_count >= 2 and (model_agreement or 0) >= 0.60,
        "required_expected_return": expected_cagr is not None and expected_cagr >= required_expected_cagr,
        "required_base_return": base_cagr is not None and base_cagr >= required_base_cagr,
        "bear_case_acceptable": bear_return is not None and bear_return >= min_bear_return,
        "pillar_floor": min(pillars.values()) >= pillar_min,
        "inside_buy_zone": (
            gap_to_buy_zone is not None and gap_to_buy_zone <= max_buy_zone_premium
        ),
    }

    critical = bool(trust.get("critical_flags") or valuation.get("critical_flags"))
    maturity = finite(scores.get("price_maturity")) or 0.0

    if critical:
        action = "REVIEW DATA"
        rationale = "A data or valuation sanity check failed; modeled upside should not be trusted yet."
    elif risk_tier == "SPECULATIVE":
        action = "SPECULATIVE WATCH"
        rationale = "The company is below the default size/history/coverage threshold for normal recommendations."
    elif risk_tier != "CORE":
        action = "WATCH"
        rationale = "The company is researchable but below the default large-established CORE threshold."
    elif not trust.get("preferred_large_cap"):
        action = "WATCH"
        rationale = "The company passes CORE but is below the preferred $25B large-cap threshold for actionable v5 recommendations."
    elif conviction_score >= buy_now_min and all(checks.values()):
        action = "BUY NOW"
        rationale = "All major evidence pillars pass and the current price is inside the return-required buy zone."
    elif (
        conviction_score >= pullback_min
        and checks["data_trust"]
        and checks["multiple_valuation_methods"]
        and checks["bear_case_acceptable"]
        and base_fair is not None
        and buy_below is not None
        and current_price is not None
        and current_price > buy_below * (1.0 + max_buy_zone_premium)
    ):
        action = "BUY ON PULLBACK"
        rationale = "The business/research case is strong, but today’s price does not meet the configured return hurdle."
    elif maturity >= 75 and gap_to_buy_zone is not None and gap_to_buy_zone >= late_gap:
        action = "TOO LATE"
        rationale = "The company may still be good, but the current price is materially above the required-return buy zone."
    elif conviction_score >= watch_min:
        action = "WATCH"
        rationale = "The case is interesting but one or more required buy conditions are not yet strong enough."
    else:
        action = "PASS"
        rationale = "The evidence does not currently justify allocating research or capital at the configured hurdle rate."

    failed_checks = [name for name, passed in checks.items() if not passed]

    return {
        "action": action,
        "conviction_score": round(conviction_score, 1),
        "conviction_level": "HIGH" if conviction_score >= 80 else "MEDIUM" if conviction_score >= 65 else "LOW",
        "pillars": pillars,
        "checks": checks,
        "failed_checks": failed_checks,
        "rationale": rationale,
        "required_base_cagr": required_base_cagr,
        "required_expected_cagr": required_expected_cagr,
        "buy_below_price": round(buy_below, 2) if buy_below is not None else None,
        "gap_to_buy_zone": round(gap_to_buy_zone, 4) if gap_to_buy_zone is not None else None,
        "base_fair_value": round(base_fair, 2) if base_fair is not None else None,
        "current_price": round(current_price, 2) if current_price is not None else None,
    }
