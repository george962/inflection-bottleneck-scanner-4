from __future__ import annotations

from datetime import datetime, timezone

from .conviction import build_conviction
from .llm_research import synthesize_with_openai
from .research_evidence import extract_filing_evidence, summarize_evidence
from .trust import evaluate_trust, finite
from .valuation import build_valuation


def _pct(value) -> str:
    x = finite(value)
    return "n/a" if x is None else f"{x:.1%}"


def _metrics(snapshot):
    features = snapshot.get("features", {})
    profile = snapshot.get("profile", {})
    scores = snapshot.get("scores", {})
    assessment = snapshot.get("assessment", {})
    keys = [
        "price",
        "dollar_volume_20d",
        "return_1m",
        "return_3m",
        "return_6m",
        "return_12m",
        "revenue_yoy",
        "revenue_acceleration",
        "gross_margin",
        "gross_margin_change_yoy",
        "operating_margin",
        "operating_margin_change_yoy",
        "incremental_operating_margin_yoy",
        "free_cash_flow_margin",
        "free_cash_flow_margin_change_yoy",
        "eps_revision_7d",
        "eps_revision_30d",
        "eps_revision_90d",
        "eps_revision_acceleration",
        "revision_breadth_30d",
        "avg_eps_surprise_last4",
        "next_year_eps_estimate",
        "next_year_eps_growth",
        "next_year_revenue_estimate",
        "next_year_revenue_growth_estimate",
        "next_year_eps_analyst_count",
    ]
    out = {k: features.get(k) for k in keys}
    out.update(
        {
            "price_stage": assessment.get("price_stage"),
            "price_maturity": scores.get("price_maturity"),
            "market_cap": profile.get("market_cap"),
            "shares_outstanding": profile.get("shares_outstanding"),
            "first_trade_date_epoch_utc": profile.get("first_trade_date_epoch_utc"),
            "current_price_info": profile.get("current_price_info"),
            "fast_last_price": profile.get("fast_last_price"),
            "fast_market_cap": profile.get("fast_market_cap"),
            "forward_pe": profile.get("forward_pe"),
            "price_to_sales": profile.get("price_to_sales"),
            "enterprise_to_ebitda": profile.get("enterprise_to_ebitda"),
            "analyst_target_upside": scores.get("analyst_target_upside"),
            "target_mean": profile.get("target_mean"),
            "target_low": profile.get("target_low"),
            "target_high": profile.get("target_high"),
            "data_quality": snapshot.get("data_quality"),
        }
    )
    return out


def _freshness(warehouse, ticker):
    ticker = ticker.upper()
    return {
        "profile": warehouse.cache_metadata(f"yahoo:v5_1:profile:{ticker}"),
        "quarterly_financials": warehouse.cache_metadata(f"yahoo:v5_1:qfin:{ticker}"),
        "annual_financials": warehouse.cache_metadata(f"yahoo:v5_1:afin:{ticker}"),
        "analyst_estimates": warehouse.cache_metadata(f"yahoo:v5_1:analyst:{ticker}"),
        "news": warehouse.cache_metadata(f"yahoo:v5_1:news:{ticker}"),
        "sec_submissions": warehouse.cache_metadata(f"sec:submissions:{ticker}"),
    }


def _build_case(snapshot, valuation, trust, evidence_summary, conviction):
    f = snapshot.get("features", {})
    p = snapshot.get("profile", {})
    scores = snapshot.get("scores", {})

    positives: list[str] = []
    risks: list[str] = []
    must_be_true: list[str] = []
    invalidation: list[str] = []

    if trust.get("preferred_large_cap"):
        positives.append("Company is in the preferred large-cap institutional-scale tier ($25B+ by default).")
    elif trust.get("risk_tier") == "CORE":
        positives.append("Company passes the large-established CORE gate for size, history, coverage, and liquidity.")

    eps30 = finite(f.get("eps_revision_30d"))
    eps90 = finite(f.get("eps_revision_90d"))
    rev_acc = finite(f.get("revenue_acceleration"))
    op_margin_change = finite(f.get("operating_margin_change_yoy"))
    eps_growth = finite(f.get("next_year_eps_growth"))
    rev_growth = finite(f.get("next_year_revenue_growth_estimate"))
    target_upside = finite(scores.get("analyst_target_upside"))

    if eps30 is not None and eps30 >= 0.05:
        positives.append(f"30-day EPS consensus revision is {_pct(eps30)}.")
    if eps90 is not None and eps90 >= 0.08:
        positives.append(f"90-day EPS consensus revision is {_pct(eps90)}.")
    if rev_acc is not None and rev_acc >= 0.04:
        positives.append(f"Reported revenue growth accelerated {rev_acc * 100:+.1f} percentage points.")
    if op_margin_change is not None and op_margin_change >= 0.02:
        positives.append(f"Operating margin improved {op_margin_change * 100:+.1f} percentage points year over year.")
    if eps_growth is not None and eps_growth >= 0.18:
        positives.append(f"Consensus next-year EPS growth is {_pct(eps_growth)}.")
    if rev_growth is not None and rev_growth >= 0.12:
        positives.append(f"Consensus next-year revenue growth is {_pct(rev_growth)}.")
    if target_upside is not None and target_upside > 0.10:
        positives.append(f"Street mean target provides {_pct(target_upside)} upside as corroboration only; it is not used as the core fair-value model.")
    if valuation.get("model_count", 0) >= 2:
        positives.append(
            f"{valuation.get('model_count')} valuation methods triangulate fair value; agreement={valuation.get('model_agreement')}."
        )

    if conviction.get("buy_below_price") is not None:
        positives.append(
            f"Required-return buy zone is at or below ${conviction['buy_below_price']:.2f}, based on the base fair value and a {conviction['required_base_cagr']:.0%} annual return hurdle."
        )

    maturity = finite(scores.get("price_maturity")) or 0
    if maturity >= 75:
        risks.append("The stock has already rerated materially; the business must keep beating expectations to justify today’s price.")
    if eps30 is not None and eps30 < 0:
        risks.append(f"30-day EPS revisions are negative at {_pct(eps30)}.")
    if rev_acc is not None and rev_acc < 0:
        risks.append(f"Revenue growth is decelerating {rev_acc * 100:+.1f} percentage points.")
    bear_return = finite(valuation.get("bear_return"))
    if bear_return is not None and bear_return < -0.25:
        risks.append(f"Bear-case modeled return from today is {_pct(bear_return)}.")
    if valuation.get("model_count", 0) < 2:
        risks.append("Only one usable valuation method is available; that is insufficient for a high-conviction BUY NOW.")
    risks.extend(f"DATA: {x}" for x in trust.get("critical_flags", []))
    risks.extend(f"Trust: {x}" for x in trust.get("warnings", [])[:5])

    must_be_true.extend(
        [
            "Forward revenue/EPS estimates must remain achievable rather than being cut after the next earnings report.",
            "The margin/FCF assumptions embedded in the base valuation must be sustained through the model horizon.",
            "The industry demand cycle must remain strong enough to support the modeled exit multiple.",
        ]
    )
    if conviction.get("action") == "BUY ON PULLBACK":
        must_be_true.append(
            f"Either price should move toward ${conviction.get('buy_below_price'):.2f}, or earnings/fair value must rise enough to move the buy zone upward."
        )

    invalidation.extend(
        [
            "Two consecutive material downward estimate revisions without a compensating valuation reset.",
            "Revenue growth and operating-margin direction both deteriorate versus the current thesis.",
            "New SEC evidence introduces a balance-sheet, customer-concentration, dilution, or demand risk large enough to break the bear-case assumptions.",
        ]
    )

    if evidence_summary.get("negative_count", 0) > evidence_summary.get("positive_count", 0):
        risks.append("Recent filing evidence contains more negative than positive keyword signals; inspect the cited passages before acting.")

    return positives[:10], risks[:12], must_be_true[:8], invalidation[:8]


def research_one(snapshot, yahoo, sec, warehouse, research_cfg, llm_cfg):
    ticker = snapshot["ticker"]
    asof = datetime.now(timezone.utc).isoformat(timespec="seconds")
    annual = yahoo.annual_financials(ticker)
    news = yahoo.news(ticker, int(research_cfg.get("news_items_per_ticker", 12)))

    if sec.available:
        filings = sec.ensure_recent_documents(
            ticker,
            list(research_cfg.get("filing_forms", ["10-K", "10-Q", "8-K"])),
            int(research_cfg.get("filing_documents_per_ticker", 6)),
            int(research_cfg.get("filing_text_max_chars", 350000)),
        )
    else:
        filings = warehouse.recent_filings(ticker, int(research_cfg.get("filing_documents_per_ticker", 6)))

    evidence = extract_filing_evidence(filings)
    evidence_summary = summarize_evidence(evidence)
    trust_thresholds = dict(research_cfg.get("trust_thresholds", {}))

    valuation = build_valuation(
        snapshot.get("profile", {}),
        snapshot.get("features", {}),
        annual,
        int(research_cfg.get("horizon_years", 3)),
        sanity_thresholds=trust_thresholds,
    )

    freshness = _freshness(warehouse, ticker)
    trust = evaluate_trust(
        snapshot=snapshot,
        valuation=valuation,
        filings=filings,
        freshness=freshness,
        policy=dict(research_cfg.get("universe_policy", {})),
        thresholds=trust_thresholds,
    )

    conviction = build_conviction(
        snapshot=snapshot,
        valuation=valuation,
        trust=trust,
        evidence_summary=evidence_summary,
        cfg=dict(research_cfg.get("conviction", {})),
    )

    positives, risks, must_be_true, invalidation = _build_case(
        snapshot, valuation, trust, evidence_summary, conviction
    )

    report = {
        "model_version": "5.0",
        "asof": asof,
        "ticker": ticker,
        "company": snapshot.get("company"),
        "sector": snapshot.get("sector"),
        "industry": snapshot.get("industry"),
        "source": snapshot.get("source"),
        "discovery": {
            "potential_score": snapshot.get("scores", {}).get("total"),
            "discovery_bucket": snapshot.get("features", {}).get("discovery_bucket"),
            "price_stage": snapshot.get("assessment", {}).get("price_stage"),
            "price_maturity": snapshot.get("scores", {}).get("price_maturity"),
        },
        "metrics": _metrics(snapshot),
        "valuation": valuation,
        "trust": trust,
        "conviction": conviction,
        "decision": {
            "decision": conviction.get("action"),
            "confidence": conviction.get("conviction_level"),
            "evidence_confidence": conviction.get("conviction_level"),
            "reason": conviction.get("rationale"),
        },
        "source_freshness": freshness,
        "why_buy": positives,
        "why_not": risks,
        "what_must_be_true": must_be_true,
        "invalidation": invalidation,
        "what_changes_decision": must_be_true,
        "filing_evidence_summary": evidence_summary,
        "filing_evidence": evidence[:30],
        "news": news,
        "methodology_note": (
            "V5 does not try to persuade with a single score. BUY NOW requires a large-established company, "
            "high data trust, multiple agreeing valuation methods, strong fundamentals/revisions, acceptable bear risk, "
            "and a current price inside a required-return buy zone. Scenario weights are not calibrated probabilities."
        ),
        "cache_note": (
            "Prices, financial statements, analyst data, news, and SEC filings are cached. Immutable SEC filing documents "
            "are reused rather than downloaded each run."
        ),
    }

    report["llm_research_note"] = (
        synthesize_with_openai(report, str(llm_cfg.get("model", "gpt-5-mini")))
        if llm_cfg.get("enabled_if_key_present", True)
        else None
    )
    return report
