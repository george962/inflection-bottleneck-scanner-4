from datetime import datetime, timezone

from inflection_scanner.trust import evaluate_trust


def _epoch_years_ago(years: float) -> float:
    return datetime.now(timezone.utc).timestamp() - years * 365.25 * 24 * 3600


def test_missing_sec_is_optional_and_not_a_trust_penalty():
    snapshot = {
        "profile": {
            "market_cap": 80_000_000_000,
            "shares_outstanding": 1_000_000_000,
            "first_trade_date_epoch_utc": _epoch_years_ago(15),
            "current_price_info": 80,
            "fast_last_price": 80,
            "fast_market_cap": 80_000_000_000,
        },
        "features": {
            "price": 80,
            "dollar_volume_20d": 500_000_000,
            "next_year_eps_analyst_count": 20,
        },
        "data_quality": 90,
    }
    valuation = {
        "valuation_resolved": True,
        "model_count": 2,
        "model_agreement": 0.75,
        "critical_flags": [],
        "warning_flags": [],
    }
    policy = {
        "core_min_market_cap": 15_000_000_000,
        "core_min_years_public": 7,
        "core_min_analysts": 10,
        "core_min_dollar_volume_20d": 50_000_000,
        "preferred_min_market_cap": 25_000_000_000,
        "midcap_min_market_cap": 7_500_000_000,
        "midcap_min_years_public": 5,
        "midcap_min_analysts": 7,
        "midcap_min_dollar_volume_20d": 25_000_000,
    }
    result = evaluate_trust(
        snapshot=snapshot,
        valuation=valuation,
        filings=[],
        freshness={},
        policy=policy,
        thresholds={},
        evidence_status={"state": "UNAVAILABLE", "errors": ["disabled"]},
    )
    assert result["trust_score"] >= 90
    assert result["evidence_ready"] is True
    assert result["sec_enrichment_available"] is False
    sec_check = next(x for x in result["checks"] if x["check"] == "Optional SEC enrichment")
    assert sec_check["status"] == "INFO"
