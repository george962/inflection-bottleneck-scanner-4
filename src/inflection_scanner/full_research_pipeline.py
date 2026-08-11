from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone

from .discovery_pipeline import run_discovery
from .performance import build_track_record
from .providers.cached_yahoo import CachedYahooProvider
from .providers.sec_research import CachedSecResearchProvider
from .research_engine import research_one
from .trust import finite, pre_research_tier
from .warehouse import ResearchWarehouse


ACTION_ORDER = {
    "BUY NOW": 0,
    "BUY NOW — RESET ENTRY": 1,
    "BUY ON PULLBACK": 2,
    "WATCH — DEVELOPING": 3,
    "TOO LATE / OVEREXTENDED": 4,
    "VALUATION UNRESOLVED": 5,
    "DATA INCOMPLETE": 6,
    "REVIEW DATA": 7,
    "SPECULATIVE WATCH": 8,
    "PASS": 9,
}


def _report_key(report):
    conviction = report.get("conviction", {})
    action = conviction.get("action", "WATCH — DEVELOPING")
    thesis = finite(conviction.get("thesis_score")) or -999
    market_cap = finite(report.get("trust", {}).get("market_cap")) or 0
    return ACTION_ORDER.get(action, 99), -thesis, -market_cap


def _snapshot_rank(snapshot):
    tier = snapshot.get("_pre_research_tier", {})
    preferred = 1 if tier.get("preferred_large_cap") else 0
    market_cap = finite(tier.get("market_cap")) or 0
    potential = finite(snapshot.get("scores", {}).get("total")) or 0
    revisions = finite(snapshot.get("scores", {}).get("revisions")) or 0
    fundamentals = finite(snapshot.get("scores", {}).get("fundamental")) or 0
    expectation_gap = finite(snapshot.get("scores", {}).get("expectation_gap")) or 0
    liquidity = finite(tier.get("dollar_volume_20d")) or 0
    return (
        preferred,
        potential,
        revisions,
        fundamentals,
        expectation_gap,
        math.log10(max(liquidity, 1)),
        math.log10(max(market_cap, 1)),
    )


def _entry_rank(snapshot):
    tier = snapshot.get("_pre_research_tier", {})
    preferred = 1 if tier.get("preferred_large_cap") else 0
    scores = snapshot.get("scores", {})
    features = snapshot.get("features", {})
    maturity = finite(scores.get("price_maturity")) or 100
    potential = finite(scores.get("total")) or 0
    revisions = finite(scores.get("revisions")) or 0
    fundamentals = finite(scores.get("fundamental")) or 0
    gap = finite(scores.get("expectation_gap")) or 0
    r6 = finite(features.get("return_6m"))
    # Prefer confirmed but not already-explosive moves. This is a research
    # allocation rule, not a buy decision.
    moderate_rerating = 100.0
    if r6 is not None:
        moderate_rerating = max(0.0, 100.0 - max(0.0, r6 - 0.35) * 100.0)
    entry_score = (
        0.25 * potential
        + 0.22 * revisions
        + 0.18 * fundamentals
        + 0.15 * gap
        + 0.12 * max(0.0, 100.0 - maturity)
        + 0.08 * moderate_rerating
    )
    return (
        preferred,
        entry_score,
        potential,
        revisions,
        math.log10(max(finite(tier.get("market_cap")) or 1, 1)),
    )


def _late_rank(snapshot):
    scores = snapshot.get("scores", {})
    features = snapshot.get("features", {})
    return (
        finite(scores.get("total")) or 0,
        finite(scores.get("revisions")) or 0,
        finite(features.get("eps_revision_30d")) or 0,
        finite(scores.get("fundamental")) or 0,
    )


def _take_unique(chosen: list[dict], pool: list[dict], count: int, ranker) -> int:
    if count <= 0:
        return 0
    used = {x["ticker"] for x in chosen}
    ranked = sorted([x for x in pool if x["ticker"] not in used], key=ranker, reverse=True)
    add = ranked[:count]
    chosen.extend(add)
    return len(add)


def _select_research_candidates(snapshots, research_candidates, research_cfg):
    """Allocate full-research slots to three distinct questions.

    1) Entry-opportunity sleeve: large CORE companies whose inflection is not yet LATE.
    2) Challenger sleeve: strongest large-cap business/estimate inflections regardless of stage.
    3) Late-leader diagnostic sleeve: explicitly identify great companies whose optimal entry may have passed.

    This prevents the output from becoming only post-rerating winners while still
    keeping mature leaders visible for TOO LATE / reset-entry analysis.
    """
    policy = dict(research_cfg.get("universe_policy", {}))
    selection_cfg = dict(research_cfg.get("research_selection", {}))
    entry_fraction = float(selection_cfg.get("entry_opportunity_fraction", 0.50))
    challenger_fraction = float(selection_cfg.get("challenger_fraction", 0.30))
    late_fraction = float(selection_cfg.get("late_diagnostic_fraction", 0.20))

    annotated = []
    for snapshot in snapshots:
        copy = dict(snapshot)
        copy["_pre_research_tier"] = pre_research_tier(copy, policy)
        annotated.append(copy)

    core = [x for x in annotated if x["_pre_research_tier"]["risk_tier"] == "CORE"]
    midcap = [x for x in annotated if x["_pre_research_tier"]["risk_tier"] == "MIDCAP"]
    speculative = [x for x in annotated if x["_pre_research_tier"]["risk_tier"] == "SPECULATIVE"]

    preferred_core = [x for x in core if x["_pre_research_tier"].get("preferred_large_cap")]
    core_source = preferred_core if len(preferred_core) >= max(5, research_candidates // 2) else core

    entry_pool = [
        x for x in core_source
        if x.get("assessment", {}).get("price_stage") != "LATE"
        and (finite(x.get("scores", {}).get("price_maturity")) or 100) <= 68
    ]
    late_pool = [x for x in core_source if x.get("assessment", {}).get("price_stage") == "LATE"]

    entry_slots = min(research_candidates, max(1, int(round(research_candidates * entry_fraction))))
    late_slots = min(research_candidates - entry_slots, max(0, int(round(research_candidates * late_fraction))))
    challenger_slots = max(0, research_candidates - entry_slots - late_slots)

    chosen: list[dict] = []
    selected_entry = _take_unique(chosen, entry_pool, entry_slots, _entry_rank)
    selected_challenger = _take_unique(chosen, core_source, challenger_slots, _snapshot_rank)
    selected_late = _take_unique(chosen, late_pool, late_slots, _late_rank)

    # Fill from remaining CORE names first, prioritizing entry potential.
    if len(chosen) < research_candidates:
        _take_unique(chosen, core, research_candidates - len(chosen), _entry_rank)

    if len(chosen) < research_candidates and policy.get("include_midcap_if_core_short", True):
        max_midcap = max(0, int(research_candidates * float(policy.get("max_midcap_fraction", 0.20))))
        remaining = min(research_candidates - len(chosen), max_midcap)
        _take_unique(chosen, midcap, remaining, _entry_rank)

    if len(chosen) < research_candidates and policy.get("include_speculative", False):
        _take_unique(chosen, speculative, research_candidates - len(chosen), _snapshot_rank)

    chosen = chosen[:research_candidates]
    return chosen, {
        "core_candidates": len(core),
        "preferred_large_cap_candidates": len(preferred_core),
        "midcap_candidates": len(midcap),
        "speculative_candidates": len(speculative),
        "entry_opportunity_candidates": len(entry_pool),
        "late_diagnostic_candidates": len(late_pool),
        "selected_for_research": len(chosen),
        "selected_entry_opportunity": selected_entry,
        "selected_challenger": selected_challenger,
        "selected_late_diagnostic": selected_late,
        "selected_core": sum(x["_pre_research_tier"]["risk_tier"] == "CORE" for x in chosen),
        "selected_midcap": sum(x["_pre_research_tier"]["risk_tier"] == "MIDCAP" for x in chosen),
    }


def _publish(reports, track_record, settings, meta):
    pub = settings.published_dir
    pub.mkdir(parents=True, exist_ok=True)
    reports = sorted(reports, key=_report_key)

    json_path = pub / "latest_research.json"
    json_path.write_text(json.dumps(reports, indent=2, default=str, allow_nan=False), encoding="utf-8")

    rows = []
    for report in reports:
        valuation = report.get("valuation", {})
        conviction = report.get("conviction", {})
        metrics = report.get("metrics", {})
        discovery = report.get("discovery", {})
        trust = report.get("trust", {})
        scenarios = {x.get("name"): x for x in valuation.get("scenarios", [])}
        entry = conviction.get("entry_timing", {})
        rows.append(
            {
                "ticker": report.get("ticker"),
                "company": report.get("company"),
                "action": conviction.get("action"),
                "conviction_score": conviction.get("conviction_score"),
                "thesis_score": conviction.get("thesis_score"),
                "entry_score": conviction.get("entry_score"),
                "entry_state": entry.get("entry_state"),
                "risk_tier": trust.get("risk_tier"),
                "size_class": trust.get("size_class"),
                "market_cap": trust.get("market_cap"),
                "years_public": trust.get("years_public"),
                "analyst_count": trust.get("analyst_count"),
                "dollar_volume_20d": trust.get("dollar_volume_20d"),
                "trust_grade": trust.get("trust_grade"),
                "trust_score": trust.get("trust_score"),
                "evidence_status": trust.get("evidence_status"),
                "filing_count": trust.get("filing_count"),
                "current_price": metrics.get("price"),
                "buy_below_price": conviction.get("buy_below_price"),
                "gap_to_buy_zone": conviction.get("gap_to_buy_zone"),
                "bear_fair_value": scenarios.get("Bear", {}).get("fair_value"),
                "base_fair_value": scenarios.get("Base", {}).get("fair_value"),
                "bull_fair_value": scenarios.get("Bull", {}).get("fair_value"),
                "valuation_status": valuation.get("valuation_status"),
                "company_type": valuation.get("company_type"),
                "expected_cagr": valuation.get("expected_cagr"),
                "base_cagr": valuation.get("base_cagr"),
                "bear_return": valuation.get("bear_return"),
                "valuation_model_count": valuation.get("model_count"),
                "model_agreement": valuation.get("model_agreement"),
                "model_base_ratio": valuation.get("model_base_ratio"),
                "fundamental_pillar": conviction.get("pillars", {}).get("fundamental_inflection"),
                "revision_pillar": conviction.get("pillars", {}).get("estimate_revision"),
                "valuation_pillar": conviction.get("pillars", {}).get("valuation"),
                "timing_pillar": conviction.get("pillars", {}).get("price_timing"),
                "quality_pillar": conviction.get("pillars", {}).get("company_quality"),
                "evidence_pillar": conviction.get("pillars", {}).get("evidence"),
                "price_stage": discovery.get("price_stage"),
                "price_maturity": discovery.get("price_maturity"),
                "return_6m": metrics.get("return_6m"),
                "return_12m": metrics.get("return_12m"),
                "distance_from_52w_high": metrics.get("distance_from_52w_high"),
                "forward_pe": metrics.get("forward_pe"),
                "next_year_eps_growth": metrics.get("next_year_eps_growth"),
                "eps_revision_30d": metrics.get("eps_revision_30d"),
            }
        )

    csv_path = pub / "latest_research.csv"
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")

    track_path = pub / "track_record.json"
    track_path.write_text(json.dumps(track_record, indent=2, default=str, allow_nan=False), encoding="utf-8")

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": "0.5.2",
        "reports": len(reports),
        "discovery_run": meta,
        "methodology": (
            "V5.2 separates business-thesis strength from entry timing. Full-research slots explicitly reserve room for large-cap entry opportunities, "
            "mature leaders are labeled TOO LATE when the primary rerating has already occurred, SEC failures become DATA INCOMPLETE instead of WATCH, "
            "and no buy zone is published when valuation models disagree. Memory/storage and semiconductor companies use cycle-normalized valuation logic."
        ),
    }
    metadata_path = pub / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")

    return {
        "published_json": json_path,
        "published_csv": csv_path,
        "published_track_record": track_path,
        "published_metadata": metadata_path,
    }


def run_full_research(
    settings,
    deep_candidates=180,
    research_candidates=24,
    top_n=30,
    refresh_universe=False,
    max_universe=None,
    force_refresh=False,
    offline=False,
    progress_callback=None,
):
    snapshots, meta = run_discovery(
        settings=settings,
        deep_candidates=deep_candidates,
        top_n=top_n,
        refresh_universe=refresh_universe,
        max_universe=max_universe,
        force_refresh=force_refresh,
        offline=offline,
        progress_callback=progress_callback,
    )

    successful = [x for x in snapshots if not x.get("error")]
    chosen, selection_stats = _select_research_candidates(successful, research_candidates, settings.research)

    warehouse = ResearchWarehouse(settings.warehouse_path)
    yahoo = CachedYahooProvider(
        warehouse=warehouse,
        ttl_hours=settings.cache_ttl_hours,
        pause_seconds=settings.request_pause_seconds,
        offline=offline,
    )
    sec = CachedSecResearchProvider(
        warehouse=warehouse,
        ttl_hours=float(settings.cache_ttl_hours.get("sec_submissions", 12)),
        offline=offline,
    )

    reports = []
    for i, snapshot in enumerate(chosen, 1):
        if progress_callback:
            progress_callback("research", i, len(chosen), snapshot["ticker"])
        report = research_one(
            snapshot=snapshot,
            yahoo=yahoo,
            sec=sec,
            warehouse=warehouse,
            research_cfg=settings.research,
            llm_cfg=settings.llm,
        )
        reports.append(report)

    track_record = build_track_record(
        warehouse,
        [int(x) for x in settings.research.get("performance_horizons_days", [90, 180, 365])],
    )
    warehouse_info = warehouse.cache_info()
    warehouse.close()

    publish_paths = _publish(
        reports,
        track_record,
        settings,
        {
            "run_id": meta.get("run_id"),
            "universe_count": meta.get("universe_count"),
            "price_scan_count": meta.get("price_scan_count"),
            "seed_count": meta.get("seed_count"),
            "market_stats": meta.get("market_stats"),
            "warehouse": warehouse_info,
            "research_selection": selection_stats,
        },
    )

    meta["research_count"] = len(reports)
    meta["research_selection"] = selection_stats
    meta["published"] = publish_paths
    meta["warehouse_after_research"] = warehouse_info
    meta["track_record_observations"] = len(track_record.get("observations", []))
    return reports, meta
