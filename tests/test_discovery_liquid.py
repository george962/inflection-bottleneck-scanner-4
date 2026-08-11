import pandas as pd

from inflection_scanner.discovery import select_deep_candidates


def test_high_liquidity_challenger_gets_a_deep_slot():
    rows = []
    for i in range(40):
        rows.append(
            {
                "ticker": f"E{i}",
                "price": 20,
                "dollar_volume_20d": 20_000_000 + i,
                "days_history": 300,
                "discovery_bucket": "EARLY_BREAKOUT",
                "price_stage": "EARLY",
                "discovery_seed_score": 90 - i * 0.5,
                "mature_challenger_score": 0,
            }
        )
    rows.append(
        {
            "ticker": "BIG",
            "price": 100,
            "dollar_volume_20d": 3_000_000_000,
            "days_history": 300,
            "discovery_bucket": "QUIET_ACCUMULATION",
            "price_stage": "MID",
            "discovery_seed_score": 25,
            "mature_challenger_score": 0,
        }
    )
    selected = select_deep_candidates(
        pd.DataFrame(rows),
        min_price=3,
        min_dollar_volume_20d=10_000_000,
        min_history_days=220,
        deep_candidates=20,
        bucket_size=30,
        max_late_fraction=0.25,
        liquid_challenger_fraction=0.30,
    )
    assert "BIG" in set(selected["ticker"])
