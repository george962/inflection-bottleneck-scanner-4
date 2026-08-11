from inflection_scanner.assessment import build_assessment


def test_late_stock_can_be_do_not_chase():
    snapshot = {
        "data_quality": 90,
        "profile": {"forward_pe": 45},
        "features": {
            "return_6m": 1.1,
            "return_12m": 1.8,
            "eps_revision_30d": 0.05,
            "next_year_eps_growth": 0.25,
            "revenue_acceleration": 0.08,
        },
        "scores": {
            "total": 72,
            "price_maturity": 90,
            "revisions": 60,
            "forward_growth": 65,
            "fundamental": 70,
            "expectation_gap": 25,
            "early_discovery": 20,
        },
    }
    a = build_assessment(snapshot, None, 65, 58, 66, 74)
    assert a["price_stage"] == "LATE"
    assert a["action"] == "DO NOT CHASE"


def test_early_strong_setup_becomes_candidate():
    snapshot = {
        "data_quality": 90,
        "profile": {"forward_pe": 20},
        "features": {
            "discovery_bucket": "RECOVERY",
            "discovery_seed_score": 80,
            "return_6m": 0.18,
            "return_12m": -0.05,
            "eps_revision_30d": 0.12,
            "eps_revision_90d": 0.20,
            "next_year_eps_growth": 0.35,
            "revenue_acceleration": 0.14,
        },
        "scores": {
            "total": 79,
            "price_maturity": 18,
            "revisions": 80,
            "forward_growth": 82,
            "fundamental": 75,
            "expectation_gap": 70,
            "early_discovery": 85,
            "analyst_target_upside": 0.25,
        },
    }
    a = build_assessment(snapshot, None, 65, 58, 66, 74)
    assert a["price_stage"] == "EARLY"
    assert a["action"] == "CANDIDATE"
    assert a["why_discovered"]
