from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import MODEL_VERSION
from .assessment import build_assessment
from .conviction import build_conviction
from .discovery import price_stage
from .features.estimates import estimate_features
from .features.fundamentals import fundamental_features
from .features.market import market_features
from .research_evidence import summarize_evidence
from .providers.sec import SECProvider
from .providers.sec_research import fetch_optional_filings
from .security_normalization import build_security_normalization
from .trust import evaluate_trust
from .valuation import build_valuation


class ResearchEngine:
    def __init__(self, provider, warehouse, cfg: dict[str, Any], security_overrides: dict[str, Any] | None = None):
        self.provider=provider; self.warehouse=warehouse; self.cfg=cfg; self.overrides=security_overrides or {}

    def research(self, ticker: str, force_refresh: bool = False) -> dict[str, Any]:
        now=datetime.now(timezone.utc).isoformat(timespec="seconds")
        price_df=self.warehouse.price_history(ticker)
        if price_df.empty:
            price_df=self.provider.history(ticker,self.cfg.get("price_period","2y")); self.warehouse.upsert_prices(ticker,price_df)
        benchmark_ticker=self.cfg.get("benchmark","SPY"); benchmark=self.warehouse.price_history(benchmark_ticker)
        if benchmark.empty:
            benchmark=self.provider.history(benchmark_ticker,self.cfg.get("price_period","2y")); self.warehouse.upsert_prices(benchmark_ticker,benchmark)
        profile=self.provider.profile(ticker)
        quarterly=self.provider.quarterly_financials(ticker)
        annual=self.provider.annual_financials(ticker)
        analyst=self.provider.analyst_data(ticker)
        news=self.provider.news(ticker,int(self.cfg.get("research",{}).get("news_items_per_ticker",12)))
        features={**market_features(price_df,benchmark),**fundamental_features(quarterly,profile),**estimate_features(analyst)}
        stage=price_stage(features); features.update({"price_stage":stage["price_stage"],"price_maturity":stage["price_maturity"]})
        for key in ["market_cap","shares_outstanding","current_price_info","fast_last_price","fast_market_cap","forward_pe","price_to_sales","enterprise_to_ebitda","first_trade_date_epoch_utc"]:
            if key in profile: features[key]=profile.get(key)
        # Feature quality is based on decision-relevant fields, not provider object count.
        quality_keys=["price","dollar_volume_20d","revenue_yoy","operating_margin","free_cash_flow_margin","eps_revision_30d","eps_revision_90d","next_year_eps_estimate","next_year_eps_growth","next_year_revenue_growth_estimate","next_year_eps_analyst_count"]
        features["data_quality"]=round(100*sum(features.get(k) is not None for k in quality_keys)/len(quality_keys),1)
        snapshot={"ticker":ticker.upper(),"profile":profile,"features":features,"scores":{"price_maturity":stage["price_maturity"]},"data_quality":features["data_quality"]}

        r=self.cfg.get("research",{}); npolicy=r.get("security_normalization",{})
        normalization=build_security_normalization(ticker,profile,self.overrides,fx_loader=self.provider.fx_rate,policy=npolicy)
        valuation=build_valuation(profile,features,annual,int(r.get("horizon_years",3)),r.get("trust_thresholds",{}),normalization=normalization)
        sec=SECProvider()
        filings,sec_status=fetch_optional_filings(sec,profile.get("cik"),r.get("filing_forms"),int(r.get("filing_documents_per_ticker",3)),int(r.get("filing_text_max_chars",120000)))
        evidence=summarize_evidence(filings,news)
        freshness={name:{"present":True,"fetched_at":now,"expires_at":None,"age_hours":0.0,"stale":False} for name in ["profile","quarterly_financials","annual_financials","analyst_estimates","news"]}
        freshness["sec_submissions"]={"present":bool(sec_status.get("submission_ok")),"fetched_at":now if sec_status.get("submission_ok") else None,"expires_at":None,"age_hours":0.0 if sec_status.get("submission_ok") else None,"stale":False}
        trust=evaluate_trust(snapshot,valuation,filings,freshness,r.get("universe_policy",{}),r.get("trust_thresholds",{}),sec_status)
        conviction=build_conviction(snapshot,valuation,trust,evidence,r.get("conviction",{}))
        report={"model_version":MODEL_VERSION,"asof":now,"ticker":ticker.upper(),"company":profile.get("company") or ticker.upper(),"sector":profile.get("sector"),"industry":profile.get("industry"),"source":"broad_discovery","discovery":{"potential_score":None,"discovery_bucket":stage["discovery_bucket"],"price_stage":stage["price_stage"],"price_maturity":stage["price_maturity"]},"metrics":features,"valuation":valuation,"trust":trust,"conviction":conviction,"decision":{"decision":conviction["action"],"confidence":conviction["conviction_level"],"reason":conviction["rationale"]},"source_freshness":freshness,"sec_status":sec_status,"filing_evidence_summary":evidence,"filing_evidence":[{k:v for k,v in x.items() if k!="text_excerpt"} for x in filings],"news":news}
        report.update(build_assessment(report))
        self.warehouse.put_research_report(ticker,now,conviction["action"],conviction["conviction_score"],report)
        return report
