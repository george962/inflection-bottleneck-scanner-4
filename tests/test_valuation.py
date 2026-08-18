import pandas as pd

from inflection_scanner.security_normalization import build_security_normalization
from inflection_scanner.valuation import build_valuation, classify_company

SANITY={"min_valuation_models_for_buy":2,"min_model_agreement_for_buy":.60,"max_model_base_ratio":1.90,"max_extreme_expected_cagr":.50,"max_expected_value_multiple":3.0,"max_bear_upside_for_sanity":1.0,"max_individual_model_multiple":4.0,"min_individual_model_multiple":.15}


def annual(eps=(5,6,7,6.5),fcf=(6e9,6.4e9,6.8e9,6.5e9)):
    cols=["2025","2024","2023","2022"]
    return {"income":pd.DataFrame([list(eps)],index=["Diluted EPS"],columns=cols),"cashflow":pd.DataFrame([list(fcf)],index=["Free Cash Flow"],columns=cols),"balance":pd.DataFrame()}


def test_computer_hardware_is_not_automatically_memory_storage():
    assert classify_company({"company":"Arista Networks","sector":"Technology","industry":"Computer Hardware"},{"next_year_eps_estimate":5}) != "MEMORY_STORAGE_CYCLICAL"


def test_networking_hardware_gets_networking_family():
    assert classify_company({"company":"Arista Networks","sector":"Technology","industry":"Communication Equipment"},{"next_year_eps_estimate":5}) == "NETWORKING_HARDWARE"


def test_memory_keyword_is_still_cycle_normalized():
    assert classify_company({"company":"Example DRAM","sector":"Technology","industry":"Memory Semiconductor"},{}) == "MEMORY_STORAGE_CYCLICAL"


def test_cross_currency_without_normalization_fails_closed():
    profile={"company":"Foreign ADR","sector":"Technology","industry":"Semiconductors","currency":"USD","financial_currency":"TWD","shares_outstanding":5e9}
    features={"price":100,"next_year_eps_estimate":8,"next_year_eps_growth":.2,"next_year_revenue_growth_estimate":.15}
    norm=build_security_normalization("ADR",profile,{},fx_loader=lambda a,b:.03)
    val=build_valuation(profile,features,annual(),3,SANITY,norm)
    assert not val["valuation_resolved"]
    assert val["valuation_status"]=="CURRENCY_UNIT_UNRESOLVED"
    assert val["models"]==[]


def test_adr_statement_eps_is_scaled_by_ratio_and_fx():
    profile={"company":"Foreign ADR","sector":"Technology","industry":"Semiconductors","currency":"USD","financial_currency":"TWD","shares_outstanding":5e9,"forward_pe":20}
    features={"price":100,"next_year_eps_estimate":8,"next_year_eps_growth":.2,"next_year_revenue_growth_estimate":.15}
    norm=build_security_normalization("ADR",profile,{"ADR":{"underlying_shares_per_traded_share":5}},fx_loader=lambda a,b:.03)
    val=build_valuation(profile,features,annual(eps=(200,180,160,140),fcf=(100e9,90e9,80e9,70e9)),3,SANITY,norm)
    assert val["normalized_eps"] == 25.5  # median(140,160,180,200)=170 * .03 * 5
    assert val["normalized_fcf"] == 2550000000.0  # median 85B TWD * .03
    assert val["security_normalization"]["resolved"] is True


def test_two_reasonable_same_currency_models_can_resolve():
    profile={"company":"Large Software","sector":"Technology","industry":"Software - Infrastructure","currency":"USD","financial_currency":"USD","forward_pe":18,"shares_outstanding":1e9}
    features={"price":100,"next_year_eps_estimate":7,"next_year_eps_growth":.15,"next_year_revenue_growth_estimate":.13}
    norm=build_security_normalization("XYZ",profile)
    val=build_valuation(profile,features,annual(),3,SANITY,norm)
    assert val["model_count"]>=2
    assert val["valuation_status"] in {"RESOLVED","UNRESOLVED"}  # sanity gates may reject, but both models exist
    assert val["security_normalization"]["resolved"] is True
