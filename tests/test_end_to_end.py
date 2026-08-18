from __future__ import annotations

import json

import pandas as pd

from inflection_scanner.discovery_pipeline import run_discovery
from inflection_scanner.full_research_pipeline import run_full_research
from inflection_scanner.warehouse import ResearchWarehouse


class FakeProvider:
    def _history(self, base=100.0):
        idx=pd.date_range("2025-01-01",periods=300,freq="B")
        close=pd.Series([base*(1+i/1200) for i in range(300)],index=idx)
        return pd.DataFrame({"Open":close,"High":close*1.01,"Low":close*.99,"Close":close,"Volume":2_000_000},index=idx)
    def history(self,ticker,period="2y"):
        return self._history(500 if ticker=="SPY" else 100)
    def batch_history(self,tickers,period="2y"):
        return {t:self._history(100+i*5) for i,t in enumerate(tickers)}
    def profile(self,ticker):
        return {"ticker":ticker,"company":ticker+" Corp","sector":"Technology","industry":"Software - Infrastructure","currency":"USD","financial_currency":"USD","market_cap":100e9,"shares_outstanding":1e9,"first_trade_date_epoch_utc":"2010-01-01T00:00:00+00:00","analyst_count_info":20,"current_price_info":124.9,"fast_last_price":124.9,"fast_market_cap":124.9e9,"forward_pe":18,"price_to_sales":5}
    def quarterly_financials(self,ticker):
        cols=["q0","q1","q2","q3","q4","q5"]
        income=pd.DataFrame([[120,115,110,105,100,98],[24,22,20,18,15,14],[70,68,65,62,58,56]],index=["Total Revenue","Operating Income","Gross Profit"],columns=cols)
        cash=pd.DataFrame([[18,17,16,15,12,11]],index=["Free Cash Flow"],columns=cols)
        return {"income":income,"cashflow":cash,"balance":pd.DataFrame()}
    def annual_financials(self,ticker):
        cols=["2025","2024","2023","2022"]
        return {"income":pd.DataFrame([[6.5,6.0,5.5,5.0]],index=["Diluted EPS"],columns=cols),"cashflow":pd.DataFrame([[7e9,6.8e9,6.5e9,6.2e9]],index=["Free Cash Flow"],columns=cols),"balance":pd.DataFrame()}
    def analyst_data(self,ticker):
        ee=pd.DataFrame({"avg":[6,7.2],"numberOfAnalysts":[20,20]},index=["0y","+1y"])
        re=pd.DataFrame({"avg":[120e9,138e9]},index=["0y","+1y"])
        trend=pd.DataFrame({"current":[7.2],"7daysAgo":[7.1],"30daysAgo":[6.9],"90daysAgo":[6.5]},index=["+1y"])
        revisions=pd.DataFrame({"upLast30days":[12],"downLast30days":[3]},index=["+1y"])
        hist=pd.DataFrame({"surprisePercent":[.05,.03,.07,.04]})
        return {"earnings_estimate":ee,"revenue_estimate":re,"eps_trend":trend,"eps_revisions":revisions,"growth_estimates":pd.DataFrame(),"earnings_history":hist}
    def news(self,ticker,limit=12): return []
    def fx_rate(self,a,b): return 1.0


def test_end_to_end_publish_builds_v54_ledgers(tmp_path):
    cfg={
        "model_version":"5.4","benchmark":"SPY","price_period":"2y","discovery":{"batch_size":10,"batch_pause_seconds":0,"min_price":5,"min_dollar_volume_20d":20e6,"deep_candidates":2},
        "research":{"research_candidates":2,"news_items_per_ticker":2,"horizon_years":3,"universe_policy":{"core_min_market_cap":15e9,"core_min_years_public":7,"core_min_analysts":10,"core_min_dollar_volume_20d":50e6,"preferred_min_market_cap":25e9},"trust_thresholds":{"min_valuation_models_for_buy":2,"min_model_agreement_for_buy":.6,"max_model_base_ratio":1.9,"max_price_source_mismatch":.2,"max_market_cap_price_mismatch":.4,"max_extreme_expected_cagr":.5,"max_expected_value_multiple":3,"max_bear_upside_for_sanity":1,"max_individual_model_multiple":4,"min_individual_model_multiple":.15},"conviction":{"required_base_cagr":.15,"required_expected_cagr":.18,"min_bear_return":-.3,"buy_now_min_thesis_score":76,"buy_on_pullback_min_thesis_score":72,"watch_min_thesis_score":58,"minimum_trust_for_buy":82,"max_buy_zone_premium":.03,"max_pullback_gap":.35,"thesis_weights":{"fundamental_inflection":25,"estimate_revision":20,"valuation":25,"company_quality":20,"evidence":10},"entry_timing":{}},"performance_horizons_days":[30],"security_normalization":{"require_explicit_adr_ratio_when_currencies_differ":True}}
    }
    w=ResearchWarehouse(tmp_path/"warehouse.db"); provider=FakeProvider()
    discovery=run_discovery(provider,w,cfg,["AAA","BBB"],deep=2)
    result=run_full_research(provider,w,cfg,discovery,{},2,tmp_path/"published")
    w.close()
    assert len(result["reports"])==2
    meta=json.loads((tmp_path/"published/metadata.json").read_text())
    assert meta["model_version"]=="5.4"
    assert (tmp_path/"published/decision_ledger.jsonl").exists()
    assert (tmp_path/"published/pit_estimates.jsonl").exists()
    assert all(r["model_version"]=="5.4" for r in result["reports"])
