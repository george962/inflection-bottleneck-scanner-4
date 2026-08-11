from datetime import datetime, timezone
import sys
import types

sys.modules.setdefault("yfinance", types.ModuleType("yfinance"))

from inflection_scanner.full_research_pipeline import _select_research_candidates


def epoch_years_ago(years):
    return datetime.now(timezone.utc).timestamp() - years * 365.25 * 24 * 3600


CFG = {
    "universe_policy": {
        "core_min_market_cap": 15_000_000_000,
        "core_min_years_public": 7,
        "core_min_analysts": 10,
        "core_min_dollar_volume_20d": 50_000_000,
        "preferred_min_market_cap": 25_000_000_000,
        "midcap_min_market_cap": 7_500_000_000,
        "midcap_min_years_public": 5,
        "midcap_min_analysts": 7,
        "midcap_min_dollar_volume_20d": 25_000_000,
        "include_midcap_if_core_short": True,
        "max_midcap_fraction": 0.20,
        "include_speculative": False,
    }
}


def snap(ticker, cap, score, years=12, analysts=20, dollar_volume=200_000_000):
    return {
        "ticker": ticker,
        "profile": {
            "market_cap": cap,
            "first_trade_date_epoch_utc": epoch_years_ago(years),
        },
        "features": {
            "next_year_eps_analyst_count": analysts,
            "dollar_volume_20d": dollar_volume,
            "eps_revision_30d": 0.05,
            "next_year_eps_growth": 0.20,
        },
        "scores": {"total": score},
        "assessment": {"price_stage": "EARLY"},
    }


def test_obscure_tiny_high_score_does_not_displace_large_core_default():
    snapshots = [
        snap("LARGE1", 80_000_000_000, 72),
        snap("LARGE2", 40_000_000_000, 68),
        snap("TINY", 1_000_000_000, 99, years=2, analysts=3, dollar_volume=8_000_000),
    ]
    chosen, stats = _select_research_candidates(snapshots, 2, CFG)
    tickers = {x["ticker"] for x in chosen}
    assert tickers == {"LARGE1", "LARGE2"}
    assert "TINY" not in tickers
    assert stats["speculative_candidates"] == 1


def test_v52_reserves_research_slots_for_nonlate_entry_opportunities():
    cfg = {
        **CFG,
        "research_selection": {
            "entry_opportunity_fraction": 0.50,
            "challenger_fraction": 0.30,
            "late_diagnostic_fraction": 0.20,
        },
    }
    snapshots = []
    for i in range(12):
        s = snap(f"EARLY{i}", 60_000_000_000 + i * 1_000_000_000, 70 + i * 0.2)
        s["scores"].update({"revisions": 75, "fundamental": 70, "expectation_gap": 65, "price_maturity": 35})
        s["assessment"] = {"price_stage": "EARLY"}
        s["features"].update({"return_6m": 0.25})
        snapshots.append(s)
    for i in range(12):
        s = snap(f"LATE{i}", 100_000_000_000 + i * 1_000_000_000, 90 + i * 0.2)
        s["scores"].update({"revisions": 90, "fundamental": 90, "expectation_gap": 80, "price_maturity": 90})
        s["assessment"] = {"price_stage": "LATE"}
        s["features"].update({"return_6m": 1.2})
        snapshots.append(s)

    chosen, stats = _select_research_candidates(snapshots, 10, cfg)
    early_count = sum(x["assessment"]["price_stage"] != "LATE" for x in chosen)
    assert early_count >= 5
    assert stats["selected_entry_opportunity"] == 5
    assert stats["selected_late_diagnostic"] == 2
