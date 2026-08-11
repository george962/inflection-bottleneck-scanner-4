from __future__ import annotations

from datetime import datetime, timezone

from .llm_research import synthesize_with_openai
from .research_evidence import extract_filing_evidence, summarize_evidence
from .trust import evaluate_trust, gate_decision
from .valuation import build_valuation, finite, make_decision


def _pct(value):
    x = finite(value)
    return "n/a" if x is None else f"{x:.1%}"


def _risk(profile, summary):
    penalty = 0.0
    debt = finite(profile.get("total_debt"))
    cash = finite(profile.get("total_cash"))
    market_cap = finite(profile.get("market_cap"))
    if market_cap and debt is not None:
        net_debt_ratio = (debt - (cash or 0)) / market_cap
        if net_debt_ratio > 0.60:
            penalty += 0.03
        elif net_debt_ratio > 0.30:
            penalty += 0.015
    if summary.get("negative_count", 0) >= summary.get("positive_count", 0) + 4:
        penalty += 0.02
    return min(penalty, 0.06)


def _metrics(snapshot):
    features = snapshot.get("features", {})
    profile = snapshot.get("profile", {})
    scores = snapshot.get("scores", {})
    assessment = snapshot.get("assessment", {})
    keys = [
        "price",
        "return_1m",
        "return_3m",
        "return_6m",
        "return_12m",
        "revenue_yoy",
        "revenue_acceleration",
        "gross_margin_change_yoy",
        "operating_margin_change_yoy",
        "incremental_operating_margin_yoy",
        "eps_revision_30d",
        "eps_revision_90d",
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
            "data_quality": snapshot.get("data_quality"),
        }
    )
    return out


def _freshness(warehouse, ticker):
    ticker = ticker.upper()
    return {
        "profile": warehouse.cache_metadata(f"yahoo:profile:{ticker}"),
        "quarterly_financials": warehouse.cache_metadata(f"yahoo:qfin:{ticker}"),
        "annual_financials": warehouse.cache_metadata(f"yahoo:afin:{ticker}"),
        "analyst_estimates": warehouse.cache_metadata(f"yahoo:analyst:{ticker}"),
        "news": warehouse.cache_metadata(f"yahoo:news:{ticker}"),
        "sec_submissions": warehouse.cache_metadata(f"sec:submissions:{ticker}"),
    }


def _bullets(snapshot, valuation, summary, trust):
    features = snapshot.get("features", {})
    profile = snapshot.get("profile", {})
    scores = snapshot.get("scores", {})
    buy, avoid, watch = [], [], []

    eps30 = finite(features.get("eps_revision_30d"))
    acceleration = finite(features.get("revenue_acceleration"))
    eps_growth = finite(features.get("next_year_eps_growth"))
    revenue_growth = finite(features.get("next_year_revenue_growth_estimate"))
    forward_pe = finite(profile.get("forward_pe"))
    maturity = finite(scores.get("price_maturity")) or 0
    expected_cagr = finite(valuation.get("expected_cagr"))
    bear_return = finite(valuation.get("bear_return"))

    if trust.get("risk_tier") == "CORE":
        buy.append(
            "Meets the default established-company CORE thresholds for market cap, public history, and analyst coverage."
        )
    if eps30 is not None and eps30 >= 0.05:
        buy.append(f"EPS consensus rose {_pct(eps30)} over 30 days.")
    if acceleration is not None and acceleration >= 0.05:
        buy.append(f"Revenue growth accelerated {acceleration * 100:+.1f} percentage points.")
    if eps_growth is not None and eps_growth >= 0.20:
        buy.append(f"Consensus next-year EPS growth is {_pct(eps_growth)}.")
    if revenue_growth is not None and revenue_growth >= 0.15:
        buy.append(f"Consensus next-year revenue growth is {_pct(revenue_growth)}.")
    if expected_cagr is not None and expected_cagr >= 0.15:
        buy.append(
            f"Scenario-weighted valuation implies approximately {_pct(expected_cagr)} annualized return over the model horizon."
        )
    if valuation.get("model_count", 0) >= 2 and (valuation.get("model_agreement") or 0) >= 0.55:
        buy.append(
            f"{valuation.get('model_count')} valuation methods corroborate the estimate with agreement {valuation.get('model_agreement'):.2f}."
        )

    if maturity >= 75:
        avoid.append("The stock has already rerated materially; future earnings must keep outrunning expectations.")
    if bear_return is not None and bear_return <= -0.35:
        avoid.append(f"Bear scenario return is approximately {_pct(bear_return)}.")
    if forward_pe is not None and forward_pe >= 45:
        avoid.append(f"Forward P/E is approximately {forward_pe:.1f}x.")
    if eps30 is not None and eps30 < 0:
        avoid.append(f"30-day EPS revisions are negative at {_pct(eps30)}.")
    if acceleration is not None and acceleration < 0:
        avoid.append(f"Revenue growth is decelerating {acceleration * 100:+.1f} percentage points.")
    avoid.extend(f"DATA CHECK: {flag}" for flag in trust.get("critical_flags", []))
    avoid.extend(f"Trust warning: {flag}" for flag in trust.get("warnings", [])[:4])
    if summary.get("negative_count", 0) > summary.get("positive_count", 0):
        avoid.append("Recent SEC filing snippets contain more negative than positive keyword evidence; inspect the passages.")

    if eps30 is None:
        watch.append("Obtain a reliable recent EPS-revision history.")
    elif eps30 <= 0:
        watch.append("30-day EPS revisions turn positive.")
    if acceleration is None or acceleration <= 0:
        watch.append("A future quarter confirms positive revenue-growth acceleration.")
    if valuation.get("model_count", 0) < 2:
        watch.append("A second independent valuation method becomes usable.")
    watch.append("Re-run after the next earnings report; cached financials and estimates refresh automatically after their TTL.")

    if not buy:
        buy.append("No strong generic buy factor passed the configured threshold.")
    if not avoid:
        avoid.append("No generic red flag passed the configured threshold; company-specific risks still require filing review.")
    return buy[:8], avoid[:10], watch[:7]


def research_one(snapshot, yahoo, sec, warehouse, research_cfg, llm_cfg):
    ticker = snapshot["ticker"]
    asof = datetime.now(timezone.utc).isoformat(timespec="seconds")
    annual = yahoo.annual_financials(ticker)
    news = yahoo.news(ticker, int(research_cfg.get("news_items_per_ticker", 12)))

    if sec.available:
        filings = sec.ensure_recent_documents(
            ticker,
            list(research_cfg.get("filing_forms", ["10-K", "10-Q", "8-K"])),
            int(research_cfg.get("filing_documents_per_ticker", 5)),
            int(research_cfg.get("filing_text_max_chars", 300000)),
        )
    else:
        filings = warehouse.recent_filings(
            ticker,
            int(research_cfg.get("filing_documents_per_ticker", 5)),
        )

    evidence = extract_filing_evidence(filings)
    summary = summarize_evidence(evidence)
    trust_thresholds = dict(research_cfg.get("trust_thresholds", {}))

    valuation = build_valuation(
        snapshot.get("profile", {}),
        snapshot.get("features", {}),
        annual,
        int(research_cfg.get("horizon_years", 3)),
        sanity_thresholds=trust_thresholds,
    )

    initial_decision = make_decision(
        valuation,
        snapshot.get("scores", {}),
        float(snapshot.get("data_quality") or 0),
        dict(research_cfg.get("decision_thresholds", {})),
        _risk(snapshot.get("profile", {}), summary),
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
    decision = gate_decision(initial_decision, trust, valuation, research_cfg)
    why, why_not, changes = _bullets(snapshot, valuation, summary, trust)

    report = {
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
        "source_freshness": freshness,
        "decision": decision,
        "why_buy": why,
        "why_not": why_not,
        "what_changes_decision": changes,
        "filing_evidence_summary": summary,
        "filing_evidence": evidence[:24],
        "news": news,
        "methodology_note": (
            "Upside is a scenario valuation estimate, not a prediction guarantee. Fixed bear/base/bull weights are not calibrated probabilities. "
            "Normal BUY requires established-company size/history, high data trust, SEC evidence, and multiple agreeing valuation methods."
        ),
        "cache_note": (
            "Prices, financial statements, analyst data, news, and SEC filings are cached. Immutable SEC filing documents are not downloaded again once stored."
        ),
    }

    report["llm_research_note"] = (
        synthesize_with_openai(report, str(llm_cfg.get("model", "gpt-5-mini")))
        if llm_cfg.get("enabled_if_key_present", True)
        else None
    )
    warehouse.put_research_report(
        ticker,
        asof,
        decision.get("decision", "WATCH"),
        valuation.get("expected_cagr"),
        report,
    )
    return report
