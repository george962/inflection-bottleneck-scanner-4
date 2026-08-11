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
    if not valuation.get("valuation_resolved"):
        agreement = finite(valuation.get("model_agreement"))
        model_count = float(valuation.get("model_count") or 0)
        return average(
            [
                linear(agreement, 0.20, 0.65),
                linear(model_count, 1, 3),
                20.0,
            ]
        )
    return average(
        [
            linear(finite(valuation.get("base_cagr")), 0.02, 0.25),
            linear(finite(valuation.get("expected_cagr")), 0.03, 0.28),
            linear(finite(valuation.get("bear_return")), -0.55, 0.05),
            linear(finite(valuation.get("model_agreement")), 0.55, 0.85),
            linear(float(valuation.get("model_count") or 0), 1, 3),
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
    """Research-evidence strength with SEC as optional enrichment.

    The core score is based on data trust, analyst coverage, and valuation
    triangulation. SEC filing evidence can refine/boost the score when present,
    but its absence never caps or penalizes the recommendation.
    """
    trust_score = finite(trust.get("trust_score"))
    analysts = finite(trust.get("analyst_count"))
    model_count = finite(trust.get("model_count"))
    agreement = finite(trust.get("model_agreement"))

    core = average(
        [
            linear(trust_score, 65, 95),
            linear(analysts, 5, 25),
            linear(model_count, 1, 3),
            linear(agreement, 0.40, 0.82),
        ]
    )

    filings = finite(trust.get("filing_count")) or 0
    if filings <= 0:
        return core

    pos = finite(evidence_summary.get("positive_count")) or 0
    neg = finite(evidence_summary.get("negative_count")) or 0
    topics = len(evidence_summary.get("topics_found", []) or [])
    tone = (pos - neg) / max(1.0, pos + neg)
    sec_component = average(
        [
            linear(filings, 1, 5),
            linear(topics, 1, 7),
            linear(tone, -0.70, 0.50),
        ]
    )
    # Optional filings influence only 15% of the evidence pillar.
    return 0.85 * core + 0.15 * sec_component


def build_entry_timing(snapshot: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    features = snapshot.get("features", {})
    scores = snapshot.get("scores", {})
    maturity = finite(scores.get("price_maturity")) or 0.0
    r1 = finite(features.get("return_1m"))
    r3 = finite(features.get("return_3m"))
    r6 = finite(features.get("return_6m"))
    r12 = finite(features.get("return_12m"))
    distance_high = finite(features.get("distance_from_52w_high"))
    eps30 = finite(features.get("eps_revision_30d"))

    late_maturity = float(cfg.get("late_maturity", 78))
    overextended_6m = float(cfg.get("overextended_return_6m", 0.70))
    overextended_12m = float(cfg.get("overextended_return_12m", 1.20))
    extreme_6m = float(cfg.get("extreme_return_6m", 1.00))
    extreme_12m = float(cfg.get("extreme_return_12m", 2.00))
    reset_from_high = float(cfg.get("reset_distance_from_high", -0.18))
    reset_1m = float(cfg.get("reset_return_1m", -0.12))

    overextended = bool(
        maturity >= late_maturity
        and (
            (r6 is not None and r6 >= overextended_6m)
            or (r12 is not None and r12 >= overextended_12m)
        )
    )
    extreme_rerating = bool(
        (r6 is not None and r6 >= extreme_6m)
        or (r12 is not None and r12 >= extreme_12m)
    )
    meaningful_reset = bool(
        overextended
        and (
            (distance_high is not None and distance_high <= reset_from_high)
            or (r1 is not None and r1 <= reset_1m)
        )
    )
    revisions_support_reset = eps30 is not None and eps30 >= 0.0
    secondary_entry_ready = meaningful_reset and revisions_support_reset

    if overextended and not meaningful_reset:
        state = "PAST PRIMARY ENTRY / OVEREXTENDED"
    elif overextended and meaningful_reset:
        state = "RESETTING AFTER RERATING"
    elif maturity <= 35:
        state = "EARLY / BUILDING"
    elif maturity <= 65:
        state = "CONFIRMED / STILL ACTIONABLE"
    else:
        state = "MATURE / WATCH ENTRY"

    timing_score = average(
        [
            linear(100.0 - maturity, 10, 90),
            peaked(r6, -0.25, 0.30, 1.25),
            peaked(r12, -0.40, 0.50, 2.20),
            peaked(r3, -0.20, 0.15, 0.70),
        ]
    )
    if secondary_entry_ready:
        timing_score = max(timing_score, 58.0)
    if overextended and not meaningful_reset:
        timing_score = min(timing_score, 25.0)

    return {
        "entry_state": state,
        "entry_score": round(timing_score, 1),
        "overextended": overextended,
        "extreme_rerating": extreme_rerating,
        "meaningful_reset": meaningful_reset,
        "secondary_entry_ready": secondary_entry_ready,
        "distance_from_52w_high": distance_high,
        "return_1m": r1,
        "return_3m": r3,
        "return_6m": r6,
        "return_12m": r12,
        "price_maturity": round(maturity, 1),
    }


def build_conviction(
    snapshot: dict[str, Any],
    valuation: dict[str, Any],
    trust: dict[str, Any],
    evidence_summary: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    features = snapshot.get("features", {})
    current_price = finite(features.get("price"))
    base = _scenario(valuation, "Base")
    base_fair = finite(base.get("fair_value")) if valuation.get("valuation_resolved") else None
    horizon = int(valuation.get("horizon_years") or 3)

    required_base_cagr = float(cfg.get("required_base_cagr", 0.15))
    required_expected_cagr = float(cfg.get("required_expected_cagr", 0.18))
    min_bear_return = float(cfg.get("min_bear_return", -0.30))
    buy_now_min = float(cfg.get("buy_now_min_thesis_score", cfg.get("buy_now_min_score", 76)))
    pullback_min = float(cfg.get("buy_on_pullback_min_thesis_score", cfg.get("buy_on_pullback_min_score", 72)))
    watch_min = float(cfg.get("watch_min_thesis_score", cfg.get("watch_min_score", 58)))
    max_buy_zone_premium = float(cfg.get("max_buy_zone_premium", 0.03))
    max_pullback_gap = float(cfg.get("max_pullback_gap", 0.35))

    entry_cfg = dict(cfg.get("entry_timing", {}))
    entry = build_entry_timing(snapshot, entry_cfg)

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
        "price_timing": entry["entry_score"],
        "company_quality": round(_quality_pillar(trust), 1),
        "evidence": round(_evidence_pillar(evidence_summary, trust), 1),
    }

    # Thesis score intentionally excludes price timing. This lets the system say
    # "excellent company, missed entry" instead of collapsing both concepts into WATCH.
    thesis_weights = cfg.get("thesis_weights", {}) or {
        "fundamental_inflection": 25,
        "estimate_revision": 20,
        "valuation": 25,
        "company_quality": 20,
        "evidence": 10,
    }
    thesis_keys = ["fundamental_inflection", "estimate_revision", "valuation", "company_quality", "evidence"]
    thesis_weight_total = sum(float(thesis_weights.get(k, 0)) for k in thesis_keys) or 100.0
    thesis_score = sum(pillars[k] * float(thesis_weights.get(k, 0)) for k in thesis_keys) / thesis_weight_total

    conviction_score = 0.82 * thesis_score + 0.18 * pillars["price_timing"]

    expected_cagr = finite(valuation.get("expected_cagr"))
    base_cagr = finite(valuation.get("base_cagr"))
    bear_return = finite(valuation.get("bear_return"))
    risk_tier = str(trust.get("risk_tier") or "SPECULATIVE")
    trust_score = finite(trust.get("trust_score")) or 0.0
    evidence_ready = bool(trust.get("evidence_ready", True))

    checks = {
        "large_established_company": risk_tier == "CORE" and bool(trust.get("preferred_large_cap")) and bool(trust.get("actionable_established")),
        "data_trust": trust_score >= float(cfg.get("minimum_trust_for_buy", 82)) and not trust.get("critical_flags"),
        "research_evidence_ready": evidence_ready,
        "valuation_resolved": bool(valuation.get("valuation_resolved")),
        "required_expected_return": expected_cagr is not None and expected_cagr >= required_expected_cagr,
        "required_base_return": base_cagr is not None and base_cagr >= required_base_cagr,
        "bear_case_acceptable": bear_return is not None and bear_return >= min_bear_return,
        "thesis_strength": thesis_score >= buy_now_min,
        "inside_buy_zone": gap_to_buy_zone is not None and gap_to_buy_zone <= max_buy_zone_premium,
        "entry_not_overextended": not entry["overextended"] or entry["secondary_entry_ready"],
    }

    critical = bool(trust.get("critical_flags") or valuation.get("critical_flags"))
    if critical:
        action = "REVIEW DATA"
        rationale = "A data or valuation sanity check failed; modeled upside should not be trusted yet."
    elif risk_tier == "SPECULATIVE":
        action = "SPECULATIVE WATCH"
        rationale = "The company is below the default large-established risk threshold."
    elif risk_tier != "CORE" or not trust.get("preferred_large_cap") or not trust.get("actionable_established"):
        action = "WATCH — DEVELOPING"
        rationale = "The company is researchable but does not pass the full large-established action gate."
    elif not valuation.get("valuation_resolved"):
        action = "VALUATION UNRESOLVED"
        rationale = "The business may be interesting, but independent valuation methods disagree too much to calculate a credible buy zone."
    elif entry["overextended"] and not entry["secondary_entry_ready"]:
        action = "TOO LATE / OVEREXTENDED"
        rationale = "The primary rerating already occurred and price has not reset enough to create a credible secondary entry."
    elif thesis_score >= buy_now_min and all(
        checks[k]
        for k in [
            "large_established_company",
            "data_trust",
            "research_evidence_ready",
            "valuation_resolved",
            "required_expected_return",
            "required_base_return",
            "bear_case_acceptable",
            "inside_buy_zone",
            "entry_not_overextended",
        ]
    ):
        if entry["secondary_entry_ready"]:
            action = "BUY NOW — RESET ENTRY"
            rationale = "The thesis and valuation pass, and a meaningful post-rerating reset has reopened the entry window."
        else:
            action = "BUY NOW"
            rationale = "The thesis, research evidence, valuation and current entry price all pass the configured hurdles."
    elif (
        thesis_score >= pullback_min
        and checks["data_trust"]
        and checks["research_evidence_ready"]
        and checks["valuation_resolved"]
        and checks["bear_case_acceptable"]
        and buy_below is not None
        and current_price is not None
        and gap_to_buy_zone is not None
        and gap_to_buy_zone > max_buy_zone_premium
        and gap_to_buy_zone <= max_pullback_gap
        and not entry["overextended"]
    ):
        action = "BUY ON PULLBACK"
        rationale = "The thesis is strong, but today’s price is above the return-required buy zone."
    elif thesis_score >= watch_min:
        action = "WATCH — DEVELOPING"
        rationale = "The thesis has merit, but the evidence, valuation, return hurdle, or entry setup is not yet strong enough."
    else:
        action = "PASS"
        rationale = "The current large-cap risk/reward does not justify further capital attention at the configured hurdles."

    failed_checks = [name for name, passed in checks.items() if not passed]

    return {
        "action": action,
        "conviction_score": round(conviction_score, 1),
        "thesis_score": round(thesis_score, 1),
        "entry_score": entry["entry_score"],
        "conviction_level": "HIGH" if thesis_score >= 80 else "MEDIUM" if thesis_score >= 65 else "LOW",
        "pillars": pillars,
        "entry_timing": entry,
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
