from datetime import datetime, timezone

from inflection_scanner.trust import gate_decision, pre_research_tier


def epoch_years_ago(years):
    return datetime.now(timezone.utc).timestamp() - years * 365.25 * 24 * 3600


POLICY = {
    "core_min_market_cap": 10_000_000_000,
    "core_min_years_public": 5,
    "core_min_analysts": 8,
    "midcap_min_market_cap": 5_000_000_000,
    "midcap_min_years_public": 3,
    "midcap_min_analysts": 5,
    "include_speculative": False,
}


def test_large_established_company_is_core():
    snapshot = {
        "profile": {
            "market_cap": 50_000_000_000,
            "first_trade_date_epoch_utc": epoch_years_ago(12),
        },
        "features": {"next_year_eps_analyst_count": 22},
    }
    result = pre_research_tier(snapshot, POLICY)
    assert result["risk_tier"] == "CORE"
    assert result["eligible"] is True


def test_small_new_company_is_speculative():
    snapshot = {
        "profile": {
            "market_cap": 1_000_000_000,
            "first_trade_date_epoch_utc": epoch_years_ago(1),
        },
        "features": {"next_year_eps_analyst_count": 3},
    }
    result = pre_research_tier(snapshot, POLICY)
    assert result["risk_tier"] == "SPECULATIVE"
    assert result["eligible"] is False


def test_trust_gate_suppresses_buy_on_critical_flags():
    out = gate_decision(
        {"decision": "BUY", "confidence": "HIGH"},
        {
            "risk_tier": "CORE",
            "trust_score": 92,
            "trust_grade": "A",
            "critical_flags": ["Extreme valuation anomaly."],
        },
        {"model_count": 2, "model_agreement": 0.8},
        {
            "trust_thresholds": {
                "buy_min_trust_score": 80,
                "min_valuation_models_for_buy": 2,
                "min_model_agreement_for_buy": 0.55,
            }
        },
    )
    assert out["decision"] == "REVIEW DATA"
