from __future__ import annotations

import math
from typing import Any


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def scale(value: Any, bad: float, good: float) -> float | None:
    value = _finite(value)
    if value is None:
        return None
    if good == bad:
        return 50.0
    return clamp((value - bad) / (good - bad) * 100.0)


def peaked(value: Any, lo: float, ideal: float, hi: float) -> float | None:
    value = _finite(value)
    if value is None:
        return None
    if value <= lo or value >= hi:
        return 0.0
    if value <= ideal:
        return 100.0 * (value - lo) / (ideal - lo)
    return 100.0 * (hi - value) / (hi - ideal)


def avg_observed(values: list[float | None]) -> float | None:
    observed = [v for v in values if v is not None]
    return sum(observed) / len(observed) if observed else None


def _component(*values: float | None) -> float | None:
    value = avg_observed(list(values))
    return round(value, 2) if value is not None else None


def _maturity(features: dict[str, Any]) -> float:
    explicit = _finite(features.get("price_maturity_score"))
    if explicit is not None:
        return clamp(explicit)

    vals = [
        scale(features.get("return_6m"), 0.35, 1.00),
        scale(features.get("return_12m"), 0.55, 1.60),
        scale(features.get("relative_return_6m"), 0.25, 0.85),
        scale(features.get("relative_return_12m"), 0.40, 1.30),
    ]
    observed = [v for v in vals if v is not None]
    return round(sum(observed) / len(observed), 2) if observed else 0.0


def _target_upside(features: dict[str, Any], profile: dict[str, Any]) -> float | None:
    price = _finite(features.get("price"))
    target = _finite(profile.get("target_mean")) or _finite(profile.get("target_median"))
    if price in (None, 0) or target is None:
        return None
    return target / price - 1.0


def score_snapshot(
    features: dict[str, Any],
    profile: dict[str, Any],
    weights: dict[str, float],
    extension_penalty_max: float = 25.0,
) -> dict[str, float | None]:
    f = features

    fundamental = _component(
        scale(f.get("revenue_yoy"), -0.05, 0.35),
        scale(f.get("revenue_acceleration"), -0.10, 0.20),
        scale(f.get("gross_margin_change_yoy"), -0.03, 0.08),
        scale(f.get("operating_margin_change_yoy"), -0.04, 0.12),
        scale(f.get("free_cash_flow_margin_change_yoy"), -0.05, 0.10),
    )

    revisions = _component(
        scale(f.get("eps_revision_7d"), -0.05, 0.10),
        scale(f.get("eps_revision_30d"), -0.08, 0.18),
        scale(f.get("eps_revision_90d"), -0.12, 0.30),
        scale(f.get("eps_revision_acceleration"), -0.04, 0.08),
        scale(f.get("revision_breadth_30d"), -1.0, 1.0),
    )

    forward_growth = _component(
        scale(f.get("next_year_eps_growth"), -0.10, 0.50),
        scale(f.get("next_year_revenue_growth_estimate"), -0.05, 0.30),
        scale(f.get("next_quarter_eps_growth"), -0.15, 0.50),
        scale(f.get("avg_eps_surprise_last4"), -0.10, 0.20),
    )

    operating_leverage = _component(
        scale(f.get("operating_margin_change_yoy"), -0.04, 0.12),
        scale(f.get("incremental_operating_margin_yoy"), -0.10, 0.80),
        scale(f.get("net_income_yoy"), -0.25, 1.00),
    )

    forward_pe = _finite(profile.get("forward_pe"))
    if forward_pe is not None and forward_pe <= 0:
        forward_pe = None
    eps_growth = _finite(f.get("next_year_eps_growth")) or _finite(f.get("analyst_eps_growth"))
    target_upside = _target_upside(f, profile)
    f["analyst_target_upside"] = target_upside

    peg_score = None
    if forward_pe is not None and eps_growth is not None and eps_growth > 0:
        growth_pct = eps_growth * 100 if eps_growth < 2 else eps_growth
        peg = forward_pe / max(growth_pct, 1e-6)
        peg_score = scale(peg, 3.0, 0.5)

    valuation_upside = _component(
        peg_score,
        scale(forward_pe, 55.0, 12.0) if forward_pe and forward_pe > 0 else None,
        scale(target_upside, -0.10, 0.40),
    )

    maturity = _maturity(f)

    has_discovery_evidence = any(
        _finite(f.get(key)) is not None
        for key in [
            "discovery_seed_score",
            "return_3m",
            "return_6m",
            "return_12m",
            "momentum_accel_1m",
            "price_maturity_score",
        ]
    )
    early_discovery = (
        _component(
            scale(f.get("discovery_seed_score"), 20, 80),
            scale(100.0 - maturity, 20, 90),
            peaked(f.get("return_3m"), -0.10, 0.15, 0.65),
            scale(f.get("momentum_accel_1m"), -0.10, 0.18),
        )
        if has_discovery_evidence
        else None
    )

    underlying_signal = avg_observed(
        [fundamental, revisions, forward_growth, operating_leverage]
    )
    if underlying_signal is None:
        expectation_gap = None
    else:
        # High signal + low/mid maturity = large gap.
        expectation_gap = clamp(underlying_signal - 0.55 * maturity)

    components: dict[str, float | None] = {
        "fundamental": fundamental,
        "revisions": revisions,
        "forward_growth": forward_growth,
        "valuation_upside": valuation_upside,
        "operating_leverage": operating_leverage,
        "expectation_gap": round(expectation_gap, 2) if expectation_gap is not None else None,
        "early_discovery": early_discovery,
    }

    available_weight = sum(weights[k] for k, v in components.items() if v is not None)
    if available_weight <= 0:
        raw = 0.0
        coverage = 0.0
    else:
        raw = sum(
            float(components[k]) * weights[k]
            for k in components
            if components[k] is not None
        ) / available_weight
        coverage = available_weight / 100.0

    # Missing evidence cannot become an artificial 50.
    coverage_multiplier = 0.50 + 0.50 * coverage
    pre_penalty = raw * coverage_multiplier

    # Current price matters explicitly here. A stock that has already rerated
    # 100-160% over 6-12 months needs extraordinary forward evidence to remain
    # near the top.
    penalty_points = extension_penalty_max * maturity / 100.0
    potential = clamp(pre_penalty - penalty_points)

    return {
        **components,
        "price_maturity": round(maturity, 2),
        "analyst_target_upside": round(target_upside, 4) if target_upside is not None else None,
        "weighted_coverage": round(coverage * 100.0, 1),
        "raw_potential": round(raw, 2),
        "extension_penalty_points": round(penalty_points, 2),
        "total": round(potential, 2),
    }


def data_quality(features: dict[str, Any]) -> float:
    important = [
        "return_3m",
        "return_6m",
        "return_12m",
        "price_maturity_score",
        "revenue_yoy",
        "revenue_acceleration",
        "gross_margin_change_yoy",
        "operating_margin_change_yoy",
        "incremental_operating_margin_yoy",
        "eps_revision_30d",
        "eps_revision_90d",
        "next_year_eps_growth",
        "next_year_revenue_growth_estimate",
    ]
    present = sum(_finite(features.get(k)) is not None for k in important)
    return round(100.0 * present / len(important), 1)
