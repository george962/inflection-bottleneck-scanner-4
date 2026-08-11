import numpy as np
import pandas as pd

from inflection_scanner.discovery import (
    compute_price_discovery_features,
    select_deep_candidates,
)


def make_history(values, volume=1_000_000):
    idx = pd.date_range("2025-01-01", periods=len(values), freq="B")
    return pd.DataFrame(
        {
            "Close": values,
            "Volume": np.full(len(values), volume, dtype=float),
        },
        index=idx,
    )


def test_early_move_not_treated_as_late():
    # Long flat period, then a moderate acceleration — exactly the type of
    # pattern the broad scan should prefer over a stock already +200%.
    flat = np.full(210, 100.0)
    recent = np.linspace(100, 125, 60)
    values = np.concatenate([flat, recent])
    f = compute_price_discovery_features(make_history(values))
    assert f["price_stage"] in {"EARLY", "MID"}
    assert f["discovery_seed_score"] > 20


def test_huge_prior_run_is_late():
    values = np.linspace(50, 180, 270)
    f = compute_price_discovery_features(make_history(values))
    assert f["price_stage"] == "LATE"
    assert f["price_maturity_score"] >= 70


def test_candidate_selection_limits_late_names():
    rows = []
    for i in range(30):
        rows.append({
            "ticker": f"E{i}",
            "price": 20,
            "dollar_volume_20d": 20_000_000,
            "days_history": 252,
            "discovery_bucket": "EARLY_BREAKOUT",
            "price_stage": "EARLY",
            "discovery_seed_score": 90 - i,
        })
    for i in range(30):
        rows.append({
            "ticker": f"L{i}",
            "price": 20,
            "dollar_volume_20d": 20_000_000,
            "days_history": 252,
            "discovery_bucket": "EARLY_BREAKOUT",
            "price_stage": "LATE",
            "discovery_seed_score": 100 - i,
        })
    df = pd.DataFrame(rows)
    selected = select_deep_candidates(
        df,
        min_price=3,
        min_dollar_volume_20d=5_000_000,
        min_history_days=130,
        deep_candidates=20,
        bucket_size=20,
        max_late_fraction=0.25,
    )
    assert (selected["price_stage"] == "LATE").sum() <= 5
