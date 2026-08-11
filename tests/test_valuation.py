import pandas as pd

from inflection_scanner.valuation import build_valuation, make_decision


SANITY = {
    "max_extreme_expected_cagr": 0.50,
    "max_expected_value_multiple": 3.0,
    "max_bear_upside_for_sanity": 1.00,
    "min_implied_forward_pe": 3.0,
    "max_implied_forward_pe": 80.0,
}

DECISIONS = {
    "buy_min_expected_cagr": 0.18,
    "buy_min_base_cagr": 0.12,
    "buy_min_scenario_support": 0.75,
    "buy_min_bear_return": -0.35,
    "small_buy_min_expected_cagr": 0.16,
    "watch_min_expected_cagr": 0.08,
    "too_late_maturity": 75,
}


def empty_financials():
    return {"income": pd.DataFrame(), "cashflow": pd.DataFrame(), "balance": pd.DataFrame()}


def test_absurd_low_implied_pe_is_review_data_not_buy():
    profile = {"sector": "Healthcare", "forward_pe": None, "shares_outstanding": 350_000_000}
    features = {
        "price": 6.35,
        "next_year_eps_estimate": 4.0,
        "next_year_eps_growth": 0.25,
        "next_year_revenue_growth_estimate": 0.04,
    }
    valuation = build_valuation(profile, features, empty_financials(), 3, SANITY)
    assert valuation["critical_flags"]
    decision = make_decision(
        valuation,
        {"price_maturity": 0, "weighted_coverage": 90},
        90,
        DECISIONS,
    )
    assert decision["decision"] == "REVIEW DATA"


def test_single_valuation_model_cannot_get_normal_buy():
    profile = {
        "sector": "Technology",
        "forward_pe": 20,
        "shares_outstanding": 1_000_000_000,
        "free_cashflow": None,
    }
    features = {
        "price": 100,
        "next_year_eps_estimate": 5.0,
        "next_year_eps_growth": 0.25,
        "next_year_revenue_growth_estimate": 0.18,
    }
    valuation = build_valuation(profile, features, empty_financials(), 3, SANITY)
    assert valuation["model_count"] == 1
    decision = make_decision(
        valuation,
        {"price_maturity": 20, "weighted_coverage": 90},
        90,
        DECISIONS,
    )
    assert decision["decision"] != "BUY"


def test_multi_model_output_has_signed_bear_return():
    profile = {
        "sector": "Technology",
        "forward_pe": 18,
        "shares_outstanding": 1_000_000_000,
        "free_cashflow": 8_000_000_000,
    }
    features = {
        "price": 100,
        "next_year_eps_estimate": 7.0,
        "next_year_eps_growth": 0.22,
        "next_year_revenue_growth_estimate": 0.16,
    }
    valuation = build_valuation(profile, features, empty_financials(), 3, SANITY)
    assert "bear_return" in valuation
    assert valuation["model_count"] >= 2
