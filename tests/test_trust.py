from datetime import datetime, timezone

from inflection_scanner.trust import pre_research_tier


def epoch_years_ago(years):
    return datetime.now(timezone.utc).timestamp() - years * 365.25 * 24 * 3600


POLICY = {
    "core_min_market_cap": 15_000_000_000,
    "core_min_years_public": 7,
    "core_min_analysts": 10,
    "core_min_dollar_volume_20d": 50_000_000,
    "preferred_min_market_cap": 25_000_000_000,
    "midcap_min_market_cap": 7_500_000_000,
    "midcap_min_years_public": 5,
    "midcap_min_analysts": 7,
    "midcap_min_dollar_volume_20d": 25_000_000,
    "include_speculative": False,
}


def test_large_established_liquid_company_is_core():
    snapshot = {
        "profile": {
            "market_cap": 50_000_000_000,
            "first_trade_date_epoch_utc": epoch_years_ago(12),
        },
        "features": {
            "next_year_eps_analyst_count": 22,
            "dollar_volume_20d": 300_000_000,
        },
    }
    result = pre_research_tier(snapshot, POLICY)
    assert result["risk_tier"] == "CORE"
    assert result["preferred_large_cap"] is True
    assert result["eligible"] is True


def test_small_new_company_is_speculative():
    snapshot = {
        "profile": {
            "market_cap": 1_000_000_000,
            "first_trade_date_epoch_utc": epoch_years_ago(1),
        },
        "features": {
            "next_year_eps_analyst_count": 3,
            "dollar_volume_20d": 5_000_000,
        },
    }
    result = pre_research_tier(snapshot, POLICY)
    assert result["risk_tier"] == "SPECULATIVE"
    assert result["eligible"] is False


def test_large_but_thinly_traded_name_does_not_pass_core():
    snapshot = {
        "profile": {
            "market_cap": 40_000_000_000,
            "first_trade_date_epoch_utc": epoch_years_ago(15),
        },
        "features": {
            "next_year_eps_analyst_count": 15,
            "dollar_volume_20d": 10_000_000,
        },
    }
    result = pre_research_tier(snapshot, POLICY)
    assert result["risk_tier"] != "CORE"
