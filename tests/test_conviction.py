from inflection_scanner.conviction import build_conviction


CFG = {
    "buy_now_min_thesis_score": 70,
    "buy_on_pullback_min_thesis_score": 67,
    "watch_min_thesis_score": 55,
    "required_base_cagr": 0.15,
    "required_expected_cagr": 0.18,
    "min_bear_return": -0.30,
    "max_buy_zone_premium": 0.03,
    "max_pullback_gap": 0.35,
    "minimum_trust_for_buy": 82,
    "thesis_weights": {
        "fundamental_inflection": 25,
        "estimate_revision": 20,
        "valuation": 25,
        "company_quality": 20,
        "evidence": 10,
    },
    "entry_timing": {
        "late_maturity": 78,
        "overextended_return_6m": 0.70,
        "overextended_return_12m": 1.20,
        "extreme_return_6m": 1.00,
        "extreme_return_12m": 2.00,
        "reset_distance_from_high": -0.18,
        "reset_return_1m": -0.12,
    },
}


def strong_snapshot(price=80, maturity=30, r6=0.35, r12=0.50, r1=0.03, distance=-0.04):
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
            "return_1m": r1,
            "return_3m": 0.15,
            "return_6m": r6,
            "return_12m": r12,
            "distance_from_52w_high": distance,
        },
        "scores": {"price_maturity": maturity},
    }


def strong_trust():
    return {
        "risk_tier": "CORE",
        "preferred_large_cap": True,
        "actionable_established": True,
        "market_cap": 80_000_000_000,
        "years_public": 15,
        "analyst_count": 24,
        "dollar_volume_20d": 500_000_000,
        "trust_score": 94,
        "filing_count": 5,
        "evidence_ready": True,
        "evidence_status": "READY",
        "model_count": 2,
        "model_agreement": 0.78,
        "critical_flags": [],
    }


def valuation(base_fair=140):
    return {
        "horizon_years": 3,
        "valuation_resolved": True,
        "valuation_status": "RESOLVED",
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
        "critical_flags": [],
    }


def evidence():
    return {
        "positive_count": 8,
        "negative_count": 2,
        "topics_found": ["demand", "pricing", "margins", "catalysts"],
    }


def test_strong_large_cap_inside_buy_zone_can_be_buy_now():
    result = build_conviction(strong_snapshot(price=80), valuation(140), strong_trust(), evidence(), CFG)
    assert result["action"] == "BUY NOW"
    assert result["buy_below_price"] > 80


def test_strong_company_above_buy_zone_becomes_pullback_not_buy_now():
    result = build_conviction(strong_snapshot(price=110, maturity=60), valuation(140), strong_trust(), evidence(), CFG)
    assert result["action"] == "BUY ON PULLBACK"
    assert result["action"] != "BUY NOW"


def test_overextended_company_is_too_late_even_if_valuation_says_inside_buy_zone():
    result = build_conviction(
        strong_snapshot(price=80, maturity=90, r6=1.10, r12=2.40, r1=0.02, distance=-0.05),
        valuation(180),
        strong_trust(),
        evidence(),
        CFG,
    )
    assert result["buy_below_price"] > 80
    assert result["action"] == "TOO LATE / OVEREXTENDED"


def test_deep_reset_can_reopen_secondary_entry():
    result = build_conviction(
        strong_snapshot(price=80, maturity=90, r6=0.95, r12=1.50, r1=-0.16, distance=-0.22),
        valuation(180),
        strong_trust(),
        evidence(),
        CFG,
    )
    assert result["entry_timing"]["secondary_entry_ready"] is True
    assert result["action"] == "BUY NOW — RESET ENTRY"


def test_unresolved_valuation_has_no_buy_label():
    unresolved = valuation(140)
    unresolved.update({"valuation_resolved": False, "valuation_status": "UNRESOLVED", "scenarios": [], "base_cagr": None, "expected_cagr": None, "bear_return": None})
    result = build_conviction(strong_snapshot(price=80), unresolved, strong_trust(), evidence(), CFG)
    assert result["action"] == "VALUATION UNRESOLVED"
    assert result["buy_below_price"] is None


def test_missing_sec_evidence_does_not_block_buy_in_v53():
    trust = strong_trust()
    trust.update({
        "evidence_ready": True,
        "evidence_status": "UNAVAILABLE",
        "filing_count": 0,
        "model_count": 2,
        "model_agreement": 0.78,
    })
    result = build_conviction(strong_snapshot(price=80), valuation(140), trust, {}, CFG)
    assert result["action"] == "BUY NOW"
    assert "sec_evidence_ready" not in result["checks"]


def test_speculative_company_never_gets_buy_now():
    trust = strong_trust()
    trust["risk_tier"] = "SPECULATIVE"
    result = build_conviction(strong_snapshot(price=80), valuation(140), trust, evidence(), CFG)
    assert result["action"] == "SPECULATIVE WATCH"
