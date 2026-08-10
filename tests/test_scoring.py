from inflection_scanner.scoring import score_snapshot


WEIGHTS = {
    "fundamental": 18,
    "revisions": 18,
    "forward_growth": 16,
    "valuation_upside": 16,
    "operating_leverage": 10,
    "expectation_gap": 12,
    "early_discovery": 10,
}


def early_features():
    return {
        "price": 50,
        "return_3m": 0.15,
        "return_6m": 0.22,
        "return_12m": 0.28,
        "price_maturity_score": 18,
        "discovery_seed_score": 78,
        "momentum_accel_1m": 0.12,
        "revenue_yoy": 0.32,
        "revenue_acceleration": 0.16,
        "gross_margin_change_yoy": 0.07,
        "operating_margin_change_yoy": 0.09,
        "free_cash_flow_margin_change_yoy": 0.08,
        "incremental_operating_margin_yoy": 0.60,
        "net_income_yoy": 0.80,
        "eps_revision_7d": 0.06,
        "eps_revision_30d": 0.12,
        "eps_revision_90d": 0.22,
        "eps_revision_acceleration": 0.05,
        "revision_breadth_30d": 0.8,
        "next_year_eps_growth": 0.35,
        "next_year_revenue_growth_estimate": 0.22,
        "next_quarter_eps_growth": 0.30,
        "avg_eps_surprise_last4": 0.08,
    }


def test_early_high_growth_candidate_can_score_high():
    f = early_features()
    profile = {"forward_pe": 22, "target_mean": 65}
    s = score_snapshot(f, profile, WEIGHTS, extension_penalty_max=25)
    assert s["total"] > 70
    assert s["price_maturity"] < 30
    assert s["valuation_upside"] > 50


def test_same_fundamentals_after_huge_run_score_lower():
    early = early_features()
    late = dict(early)
    late["price"] = 130
    late["return_6m"] = 1.10
    late["return_12m"] = 1.80
    late["price_maturity_score"] = 92
    late["discovery_seed_score"] = 35

    profile_early = {"forward_pe": 22, "target_mean": 65}
    profile_late = {"forward_pe": 55, "target_mean": 135}

    a = score_snapshot(early, profile_early, WEIGHTS, 25)
    b = score_snapshot(late, profile_late, WEIGHTS, 25)

    assert a["total"] > b["total"] + 15
    assert b["price_maturity"] > 80


def test_no_data_does_not_become_fifty():
    s = score_snapshot({}, {}, WEIGHTS, 25)
    assert s["total"] == 0
