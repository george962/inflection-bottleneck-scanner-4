import pandas as pd
from inflection_scanner.valuation import build_valuation,classify_company,make_decision

def empty():return {"income":pd.DataFrame(),"cashflow":pd.DataFrame(),"balance":pd.DataFrame()}
def test_unprofitable_uses_revenue():
    p={"sector":"Industrials","forward_pe":None,"shares_outstanding":100_000_000}
    f={"price":20,"next_year_eps_estimate":-.5,"next_year_revenue_estimate":1_000_000_000,"next_year_revenue_growth_estimate":.25,"revenue_yoy":.2,"operating_margin":-.05}
    assert classify_company(p,f)=="EARLY_STAGE_GROWTH"
    assert build_valuation(p,f,empty(),3)["model"]=="FORWARD_REVENUE_MULTIPLE"
def test_late_not_automatic_exclusion():
    p={"sector":"Technology","forward_pe":18,"shares_outstanding":100_000_000}
    f={"price":50,"next_year_eps_estimate":4,"next_year_eps_growth":.35,"next_year_revenue_growth_estimate":.2,"operating_margin":.2}
    v=build_valuation(p,f,empty(),3)
    d=make_decision(v,{"price_maturity":82,"weighted_coverage":90},90,{"buy_min_expected_cagr":.18,"buy_min_probability_profit":.65,"buy_max_bear_downside":-.4,"small_buy_min_expected_cagr":.16,"watch_min_expected_cagr":.08,"too_late_maturity":75})
    assert d["decision"] in {"BUY","SMALL BUY / SPECULATIVE","WATCH","TOO LATE"}
def test_mature_low_return_is_too_late():
    v={"model":"FORWARD_EPS_EXIT_MULTIPLE","expected_cagr":.09,"probability_profit":.75,"bear_downside":-.3,"horizon_years":3}
    d=make_decision(v,{"price_maturity":90,"weighted_coverage":90},90,{"buy_min_expected_cagr":.18,"buy_min_probability_profit":.65,"buy_max_bear_downside":-.4,"small_buy_min_expected_cagr":.16,"watch_min_expected_cagr":.08,"too_late_maturity":75})
    assert d["decision"]=="TOO LATE"
