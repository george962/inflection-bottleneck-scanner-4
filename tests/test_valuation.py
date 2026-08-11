import pandas as pd

from inflection_scanner.valuation import build_valuation, classify_company, make_decision


SANITY = {
    "max_extreme_expected_cagr": 0.50,
    "max_expected_value_multiple": 3.0,
    "max_bear_upside_for_sanity": 1.00,
    "min_implied_forward_pe": 3.0,
    "max_implied_forward_pe": 80.0,
    "min_valuation_models_for_buy": 2,
    "min_model_agreement_for_buy": 0.60,
    "max_model_base_ratio": 1.90,
    "max_individual_model_multiple": 4.0,
    "min_individual_model_multiple": 0.15,
}

DECISIONS = {
    "buy_min_expected_cagr": 0.18,
    "buy_min_base_cagr": 0.12,
    "buy_min_bear_return": -0.35,
    "watch_min_expected_cagr": 0.08,
}


def empty_financials():
    return {"income": pd.DataFrame(), "cashflow": pd.DataFrame(), "balance": pd.DataFrame()}


def annual_financials(eps=(5.0, 6.0, 7.0, 6.5), fcf=(6.0e9, 6.4e9, 6.8e9, 6.5e9)):
    cols = ["2025", "2024", "2023", "2022"]
    return {
        "income": pd.DataFrame([list(eps)], index=["Diluted EPS"], columns=cols),
        "cashflow": pd.DataFrame([list(fcf)], index=["Free Cash Flow"], columns=cols),
        "balance": pd.DataFrame(),
    }


def test_absurd_low_implied_pe_is_review_data_not_buy():
    profile = {"sector": "Healthcare", "industry": "Medical Devices", "forward_pe": None, "shares_outstanding": 350_000_000}
    features = {
        "price": 6.35,
        "next_year_eps_estimate": 4.0,
        "next_year_eps_growth": 0.25,
        "next_year_revenue_growth_estimate": 0.04,
    }
    valuation = build_valuation(profile, features, empty_financials(), 3, SANITY)
    assert valuation["critical_flags"]
    decision = make_decision(valuation, {"price_maturity": 0}, 90, DECISIONS)
    assert decision["decision"] == "REVIEW DATA"


def test_two_reasonably_agreeing_models_can_resolve():
    profile = {
        "company": "Large Software Corp",
        "sector": "Technology",
        "industry": "Software - Infrastructure",
        "forward_pe": 18,
        "shares_outstanding": 1_000_000_000,
        "free_cashflow": 6_800_000_000,
    }
    features = {
        "price": 100,
        "next_year_eps_estimate": 7.0,
        "next_year_eps_growth": 0.15,
        "next_year_revenue_growth_estimate": 0.13,
    }
    valuation = build_valuation(profile, features, annual_financials(), 3, SANITY)
    assert valuation["model_count"] >= 2
    assert valuation["valuation_resolved"] is True
    assert valuation["scenarios"]
    assert valuation["base_cagr"] is not None


def test_wildly_disagreeing_models_do_not_create_blended_buy_value():
    profile = {
        "company": "Example Corp",
        "sector": "Technology",
        "industry": "Software",
        "forward_pe": 18,
        "shares_outstanding": 1_000_000_000,
        "free_cashflow": 500_000_000,
    }
    features = {
        "price": 100,
        "next_year_eps_estimate": 12.0,
        "next_year_eps_growth": 0.30,
        "next_year_revenue_growth_estimate": 0.20,
    }
    valuation = build_valuation(profile, features, annual_financials(fcf=(0.4e9, 0.5e9, 0.6e9, 0.5e9)), 3, SANITY)
    assert valuation["model_count"] >= 2
    assert valuation["valuation_resolved"] is False
    assert valuation["valuation_status"] == "UNRESOLVED"
    assert valuation["scenarios"] == []
    assert valuation["base_cagr"] is None
    assert valuation["model_ranges"]["Base"]["low"] is not None


def test_memory_storage_cycle_is_detected_from_industry_keyword():
    profile = {"company": "Example Storage", "sector": "Technology", "industry": "Computer Hardware"}
    assert classify_company(profile, {}) == "MEMORY_STORAGE_CYCLICAL"


def test_semiconductor_with_extreme_margin_and_revenue_swing_is_cycle_normalized():
    profile = {"company": "Large Chip Maker", "sector": "Technology", "industry": "Semiconductors"}
    features = {
        "next_year_eps_estimate": 155.0,
        "next_year_eps_growth": 1.10,
        "next_year_revenue_growth_estimate": 0.85,
        "operating_margin_change_yoy": 0.57,
    }
    assert classify_company(profile, features) == "MEMORY_STORAGE_CYCLICAL"


def test_peak_cycle_forward_eps_is_not_used_as_ordinary_growth_model():
    profile = {
        "company": "Large Memory Co",
        "sector": "Technology",
        "industry": "Semiconductors",
        "forward_pe": 5.5,
        "shares_outstanding": 1_000_000_000,
        "free_cashflow": 20_000_000_000,
    }
    features = {
        "price": 800,
        "next_year_eps_estimate": 150.0,
        "next_year_eps_growth": 1.10,
        "next_year_revenue_growth_estimate": 0.85,
        "operating_margin_change_yoy": 0.50,
    }
    financials = annual_financials(eps=(20.0, 5.0, 12.0, 18.0), fcf=(12e9, 4e9, 8e9, 15e9))
    valuation = build_valuation(profile, features, financials, 3, SANITY)
    model_names = {m["name"] for m in valuation["models"]}
    assert "NORMALIZED_MEMORY_STORAGE_EPS" in model_names
    assert "FORWARD_EPS" not in model_names
    # The normalized EPS anchor should be far below the peak-cycle 150 forward EPS.
    cycle_model = next(m for m in valuation["models"] if m["name"] == "NORMALIZED_MEMORY_STORAGE_EPS")
    assert cycle_model["scenarios"][1]["assumptions"]["normalized_eps"] < 60


def test_single_model_returns_valuation_unresolved():
    profile = {
        "company": "Large Growth Co",
        "sector": "Technology",
        "industry": "Software",
        "forward_pe": 20,
        "shares_outstanding": 1_000_000_000,
        "free_cashflow": None,
    }
    features = {
        "price": 100,
        "next_year_eps_estimate": 5.0,
        "next_year_eps_growth": 0.20,
        "next_year_revenue_growth_estimate": 0.15,
    }
    valuation = build_valuation(profile, features, empty_financials(), 3, SANITY)
    assert valuation["model_count"] == 1
    assert valuation["valuation_resolved"] is False
    decision = make_decision(valuation, {"price_maturity": 20}, 90, DECISIONS)
    assert decision["decision"] == "VALUATION UNRESOLVED"
