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
    "BUY ON PULLBACK": 1,
    "WATCH": 2,
    "TOO LATE": 3,
    "REVIEW DATA": 4,
    "SPECULATIVE WATCH": 5,
    "PASS": 6,
}


def _report_key(report):
    conviction = report.get("conviction", {})
    action = conviction.get("action", "WATCH")
    score = finite(conviction.get("conviction_score")) or -999
    market_cap = finite(report.get("trust", {}).get("market_cap")) or 0
    return ACTION_ORDER.get(action, 9), -score, -market_cap


def _snapshot_rank(snapshot):
    tier = snapshot.get("_pre_research_tier", {})
    preferred = 1 if tier.get("preferred_large_cap") else 0
    market_cap = finite(tier.get("market_cap")) or 0
    potential = finite(snapshot.get("scores", {}).get("total")) or 0
    revision = finite(snapshot.get("features", {}).get("eps_revision_30d")) or 0
    eps_growth = finite(snapshot.get("features", {}).get("next_year_eps_growth")) or 0
    liquidity = finite(tier.get("dollar_volume_20d")) or 0
    # Size/history/liquidity are admission gates, not the thesis itself. Once a
    # company passes CORE, rank primarily by inflection/estimate evidence so the
    # output does not simply become a list of the world's largest companies.
    return (
        preferred,
        potential,
        revision,
        eps_growth,
        math.log10(max(liquidity, 1)),
        math.log10(max(market_cap, 1)),
    )


def _balanced_take(pool, count, late_fraction=0.35):
    if count <= 0 or not pool:
        return []
    early_mid = [x for x in pool if x.get("assessment", {}).get("price_stage") != "LATE"]
    late = [x for x in pool if x.get("assessment", {}).get("price_stage") == "LATE"]
    early_mid.sort(key=_snapshot_rank, reverse=True)
    late.sort(key=_snapshot_rank, reverse=True)
    late_slots = min(int(round(count * late_fraction)), len(late))
    main_slots = max(0, count - late_slots)
    chosen = early_mid[:main_slots] + late[:late_slots]
    if len(chosen) < count:
        used = {x["ticker"] for x in chosen}
        remainder = sorted([x for x in pool if x["ticker"] not in used], key=_snapshot_rank, reverse=True)
        chosen.extend(remainder[: count - len(chosen)])
    return chosen[:count]


def _select_research_candidates(snapshots, research_candidates, research_cfg):
    policy = dict(research_cfg.get("universe_policy", {}))
    annotated = []
    for snapshot in snapshots:
        copy = dict(snapshot)
        copy["_pre_research_tier"] = pre_research_tier(copy, policy)
        annotated.append(copy)

    core = [x for x in annotated if x["_pre_research_tier"]["risk_tier"] == "CORE"]
    midcap = [x for x in annotated if x["_pre_research_tier"]["risk_tier"] == "MIDCAP"]
    speculative = [x for x in annotated if x["_pre_research_tier"]["risk_tier"] == "SPECULATIVE"]

    core.sort(key=_snapshot_rank, reverse=True)
    midcap.sort(key=_snapshot_rank, reverse=True)
    speculative.sort(key=_snapshot_rank, reverse=True)

    chosen = _balanced_take(core, research_candidates, late_fraction=0.35)

    if len(chosen) < research_candidates and policy.get("include_midcap_if_core_short", True):
        max_midcap = max(0, int(research_candidates * float(policy.get("max_midcap_fraction", 0.20))))
        remaining = research_candidates - len(chosen)
        chosen.extend(_balanced_take(midcap, min(remaining, max_midcap), late_fraction=0.30))

    if len(chosen) < research_candidates and policy.get("include_speculative", False):
        used = {x["ticker"] for x in chosen}
        fill = [x for x in speculative if x["ticker"] not in used]
        chosen.extend(fill[: research_candidates - len(chosen)])

    return chosen, {
        "core_candidates": len(core),
        "preferred_large_cap_candidates": sum(bool(x["_pre_research_tier"].get("preferred_large_cap")) for x in core),
        "midcap_candidates": len(midcap),
        "speculative_candidates": len(speculative),
        "selected_for_research": len(chosen),
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
        rows.append(
            {
                "ticker": report.get("ticker"),
                "company": report.get("company"),
                "action": conviction.get("action"),
                "conviction_score": conviction.get("conviction_score"),
                "conviction_level": conviction.get("conviction_level"),
                "risk_tier": trust.get("risk_tier"),
                "size_class": trust.get("size_class"),
                "market_cap": trust.get("market_cap"),
                "years_public": trust.get("years_public"),
                "analyst_count": trust.get("analyst_count"),
                "dollar_volume_20d": trust.get("dollar_volume_20d"),
                "trust_grade": trust.get("trust_grade"),
                "trust_score": trust.get("trust_score"),
                "current_price": metrics.get("price"),
                "buy_below_price": conviction.get("buy_below_price"),
                "gap_to_buy_zone": conviction.get("gap_to_buy_zone"),
                "bear_fair_value": scenarios.get("Bear", {}).get("fair_value"),
                "base_fair_value": scenarios.get("Base", {}).get("fair_value"),
                "bull_fair_value": scenarios.get("Bull", {}).get("fair_value"),
                "expected_cagr": valuation.get("expected_cagr"),
                "base_cagr": valuation.get("base_cagr"),
                "bear_return": valuation.get("bear_return"),
                "valuation_model_count": valuation.get("model_count"),
                "model_agreement": valuation.get("model_agreement"),
                "fundamental_pillar": conviction.get("pillars", {}).get("fundamental_inflection"),
                "revision_pillar": conviction.get("pillars", {}).get("estimate_revision"),
                "valuation_pillar": conviction.get("pillars", {}).get("valuation"),
                "timing_pillar": conviction.get("pillars", {}).get("price_timing"),
                "quality_pillar": conviction.get("pillars", {}).get("company_quality"),
                "evidence_pillar": conviction.get("pillars", {}).get("evidence"),
                "price_stage": discovery.get("price_stage"),
                "price_maturity": discovery.get("price_maturity"),
                "return_12m": metrics.get("return_12m"),
                "forward_pe": metrics.get("forward_pe"),
                "next_year_eps_growth": metrics.get("next_year_eps_growth"),
                "eps_revision_30d": metrics.get("eps_revision_30d"),
            }
        )

    csv_path = pub / "latest_research.csv"
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")

    track_path = pub / "track_record.json"
    track_path.write_text(json.dumps(track_record, indent=2, default=str, allow_nan=False), encoding="utf-8")

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": "0.5.1",
        "reports": len(reports),
        "discovery_run": meta,
        "methodology": (
            "V5.1 defaults to large, established, liquid companies and handles missing Yahoo establishment metadata as an explicit trust gap rather than an automatic speculative classification. BUY NOW requires high data trust, multiple agreeing valuation methods, "
            "strong fundamental/revision evidence, acceptable bear risk, and a current price inside a 15% base-case CAGR buy zone. "
            "The system records realized outcomes over time instead of presenting scenario weights as probabilities."
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
    research_candidates=20,
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
        warehouse.put_research_report(
            ticker=report["ticker"],
            asof=report["asof"],
            decision=report.get("conviction", {}).get("action", "WATCH"),
            expected_cagr=report.get("valuation", {}).get("expected_cagr"),
            payload=report,
        )

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
