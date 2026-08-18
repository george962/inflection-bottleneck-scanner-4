from datetime import datetime, timezone

from inflection_scanner.trust import years_public, pre_research_tier


def test_years_public_accepts_iso_datetime_string():
    now=datetime(2026,8,18,tzinfo=timezone.utc)
    years=years_public({"first_trade_date_epoch_utc":"2024-03-21 09:30:00-04:00"},now=now)
    assert years is not None
    assert 2.3 < years < 2.5


def test_years_public_accepts_epoch_seconds():
    now=datetime(2026,8,18,tzinfo=timezone.utc)
    ts=datetime(2016,8,18,tzinfo=timezone.utc).timestamp()
    years=years_public({"first_trade_date_epoch_utc":ts},now=now)
    assert 9.9 < years < 10.1


def test_core_tier_uses_parsed_history():
    snap={"profile":{"market_cap":100e9,"first_trade_date_epoch_utc":"2010-01-01T00:00:00+00:00"},"features":{"dollar_volume_20d":500e6,"next_year_eps_analyst_count":20}}
    policy={"core_min_market_cap":15e9,"core_min_years_public":7,"core_min_analysts":10,"core_min_dollar_volume_20d":50e6,"preferred_min_market_cap":25e9}
    tier=pre_research_tier(snap,policy)
    assert tier["risk_tier"]=="CORE"
    assert tier["years_public"] is not None
