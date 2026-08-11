from inflection_scanner.conviction import build_conviction


CFG = {
    "buy_now_min_score": 75,
    "buy_on_pullback_min_score": 70,
    "watch_min_score": 55,
    "required_base_cagr": 0.15,
    "required_expected_cagr": 0.18,
    "min_bear_return": -0.30,
    "max_buy_zone_premium": 0.03,
    "late_too_expensive_gap": 0.15,
    "pillar_minimum_for_buy": 50,
    "weights": {
        "fundamental_inflection": 22,
        "estimate_revision": 18,
        "valuation": 22,
        "price_timing": 10,
        "company_quality": 18,
        "evidence": 10,
    },
}


def strong_snapshot(price=80, maturity=30):
    return {
        "features": {
            "price": price,
            "revenue_acceleration": 0.10,
            "operating_margin_change_yoy": 0.05,
            "gross_margin_change_yoy": 0.04,
            "next_year_revenue_growth_estimate": 0.22,
            "next_year_eps_growth": 0.35,
            "free_cash_flow_margin_change_yoy": 0.04,
            "eps_revision_30d": 0.10,
            "eps_revision_90d": 0.18,
            "revision_breadth_30d": 0.70,
            "eps_revision_acceleration": 0.04,
            "avg_eps_surprise_last4": 0.10,
            "return_12m": 0.35,
            "return_3m": 0.15,
        },
        "scores": {"price_maturity": maturity},
    }


def strong_trust():
    return {
        "risk_tier": "CORE",
        "preferred_large_cap": True,
        "market_cap": 80_000_000_000,
        "years_public": 15,
        "analyst_count": 24,
        "dollar_volume_20d": 500_000_000,
        "trust_score": 94,
        "filing_count": 5,
        "critical_flags": [],
    }


def valuation(base_fair=140):
    return {
        "horizon_years": 3,
        "scenarios": [
            {"name": "Bear", "fair_value": 75},
            {"name": "Base", "fair_value": base_fair},
            {"name": "Bull", "fair_value": 180},
        ],
        "base_cagr": 0.20,
        "expected_cagr": 0.22,
        "bear_return": -0.06,
        "model_count": 2,
        "model_agreement": 0.78,
    }


def test_strong_large_cap_inside_buy_zone_can_be_buy_now():
    result = build_conviction(
        strong_snapshot(price=80),
        valuation(base_fair=140),
        strong_trust(),
        {"positive_count": 8, "negative_count": 2, "topics_found": ["demand", "pricing", "margins", "catalysts"]},
        CFG,
    )
    assert result["action"] == "BUY NOW"
    assert result["buy_below_price"] > 80


def test_strong_company_above_buy_zone_becomes_pullback_not_buy_now():
    result = build_conviction(
        strong_snapshot(price=125, maturity=70),
        valuation(base_fair=140),
        strong_trust(),
        {"positive_count": 8, "negative_count": 2, "topics_found": ["demand", "pricing", "margins", "catalysts"]},
        CFG,
    )
    assert result["action"] in {"BUY ON PULLBACK", "TOO LATE"}
    assert result["action"] != "BUY NOW"


def test_speculative_company_never_gets_buy_now():
    trust = strong_trust()
    trust["risk_tier"] = "SPECULATIVE"
    result = build_conviction(
        strong_snapshot(price=80),
        valuation(base_fair=140),
        trust,
        {"positive_count": 8, "negative_count": 2, "topics_found": ["demand", "pricing", "margins", "catalysts"]},
        CFG,
    )
    assert result["action"] == "SPECULATIVE WATCH"
