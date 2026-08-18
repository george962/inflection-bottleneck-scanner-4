from inflection_scanner.conviction import build_conviction


def base_snapshot():
    return {"features":{"price":100,"revenue_acceleration":.1,"operating_margin_change_yoy":.05,"gross_margin_change_yoy":.03,"next_year_revenue_growth_estimate":.2,"next_year_eps_growth":.25,"free_cash_flow_margin_change_yoy":.04,"eps_revision_30d":.1,"eps_revision_90d":.15,"revision_breadth_30d":.6,"eps_revision_acceleration":.02,"avg_eps_surprise_last4":.1,"return_1m":0,"return_3m":.1,"return_6m":.2,"return_12m":.3,"distance_from_52w_high":-.1},"scores":{"price_maturity":30}}


def cfg():
    return {"required_base_cagr":.15,"required_expected_cagr":.18,"min_bear_return":-.3,"buy_now_min_thesis_score":70,"buy_on_pullback_min_thesis_score":65,"watch_min_thesis_score":50,"minimum_trust_for_buy":80,"max_buy_zone_premium":.03,"max_pullback_gap":.35,"entry_timing":{},"thesis_weights":{"fundamental_inflection":25,"estimate_revision":20,"valuation":25,"company_quality":20,"evidence":10}}


def test_unresolved_currency_units_never_buy():
    valuation={"valuation_status":"CURRENCY_UNIT_UNRESOLVED","valuation_resolved":False,"model_count":0,"model_agreement":None,"critical_flags":[],"warning_flags":[]}
    trust={"risk_tier":"CORE","preferred_large_cap":True,"actionable_established":True,"trust_score":95,"critical_flags":[],"evidence_ready":True,"market_cap":100e9,"years_public":10,"analyst_count":20,"dollar_volume_20d":1e9,"model_count":0,"model_agreement":None}
    result=build_conviction(base_snapshot(),valuation,trust,{},cfg())
    assert result["action"]=="REVIEW DATA"
