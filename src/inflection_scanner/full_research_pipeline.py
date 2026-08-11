from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from .discovery_pipeline import run_discovery
from .providers.cached_yahoo import CachedYahooProvider
from .providers.sec_research import CachedSecResearchProvider
from .research_engine import research_one
from .trust import pre_research_tier
from .warehouse import ResearchWarehouse


ORDER = {
    "BUY": 0,
    "SMALL BUY / SPECULATIVE": 1,
    "WATCH": 2,
    "TOO LATE": 3,
    "REVIEW DATA": 4,
    "SPECULATIVE WATCH": 5,
    "PASS": 6,
}


def _key(report):
    decision = report.get("decision", {}).get("decision", "WATCH")
    cagr = report.get("valuation", {}).get("expected_cagr")
    return ORDER.get(decision, 9), -(float(cagr) if cagr is not None else -999)


def _balanced_take(pool, count):
    if count <= 0 or not pool:
        return []
    early_mid = [x for x in pool if x.get("assessment", {}).get("price_stage") != "LATE"]
    late = [x for x in pool if x.get("assessment", {}).get("price_stage") == "LATE"]
    late_slots = min(max(2, count // 4), len(late))
    main_slots = max(0, count - late_slots)
    chosen = early_mid[:main_slots] + late[:late_slots]
    if len(chosen) < count:
        used = {x["ticker"] for x in chosen}
        remainder = [x for x in pool if x["ticker"] not in used]
        chosen.extend(remainder[: count - len(chosen)])
    return chosen[:count]


def _select_research_candidates(snapshots, research_candidates, research_cfg):
    policy = dict(research_cfg.get("universe_policy", {}))
    annotated = []
    for snapshot in snapshots:
        copy = dict(snapshot)
        copy["_pre_research_tier"] = pre_research_tier(copy, policy)
        annotated.append(copy)

    core = sorted(
        [x for x in annotated if x["_pre_research_tier"]["risk_tier"] == "CORE"],
        key=lambda x: x.get("scores", {}).get("total", -1),
        reverse=True,
    )
    midcap = sorted(
        [x for x in annotated if x["_pre_research_tier"]["risk_tier"] == "MIDCAP"],
        key=lambda x: x.get("scores", {}).get("total", -1),
        reverse=True,
    )
    speculative = sorted(
        [x for x in annotated if x["_pre_research_tier"]["risk_tier"] == "SPECULATIVE"],
        key=lambda x: x.get("scores", {}).get("total", -1),
        reverse=True,
    )

    chosen = _balanced_take(core, research_candidates)

    if len(chosen) < research_candidates and policy.get("include_midcap_if_core_short", True):
        max_midcap = max(1, int(research_candidates * float(policy.get("max_midcap_fraction", 0.25))))
        remaining = research_candidates - len(chosen)
        chosen.extend(_balanced_take(midcap, min(remaining, max_midcap)))

    if len(chosen) < research_candidates and policy.get("include_speculative", False):
        used = {x["ticker"] for x in chosen}
        fill = [x for x in speculative if x["ticker"] not in used]
        chosen.extend(fill[: research_candidates - len(chosen)])

    return chosen, {
        "core_candidates": len(core),
        "midcap_candidates": len(midcap),
        "speculative_candidates": len(speculative),
        "selected_for_research": len(chosen),
    }


def _publish(reports, settings, meta):
    pub = settings.published_dir
    pub.mkdir(parents=True, exist_ok=True)
    reports = sorted(reports, key=_key)

    json_path = pub / "latest_research.json"
    json_path.write_text(json.dumps(reports, indent=2, default=str, allow_nan=False), encoding="utf-8")

    rows = []
    for report in reports:
        valuation = report.get("valuation", {})
        decision = report.get("decision", {})
        metrics = report.get("metrics", {})
        discovery = report.get("discovery", {})
        trust = report.get("trust", {})
        scenarios = {x.get("name"): x for x in valuation.get("scenarios", [])}
        rows.append(
            {
                "ticker": report.get("ticker"),
                "company": report.get("company"),
                "decision": decision.get("decision"),
                "evidence_confidence": decision.get("evidence_confidence"),
                "trust_grade": trust.get("trust_grade"),
                "trust_score": trust.get("trust_score"),
                "risk_tier": trust.get("risk_tier"),
                "market_cap": trust.get("market_cap"),
                "years_public": trust.get("years_public"),
                "analyst_count": trust.get("analyst_count"),
                "current_price": metrics.get("price"),
                "bear_fair_value": scenarios.get("Bear", {}).get("fair_value"),
                "base_fair_value": scenarios.get("Base", {}).get("fair_value"),
                "bull_fair_value": scenarios.get("Bull", {}).get("fair_value"),
                "expected_value_3y": valuation.get("expected_value"),
                "expected_cagr": valuation.get("expected_cagr"),
                "base_cagr": valuation.get("base_cagr"),
                "bear_return": valuation.get("bear_return"),
                "scenario_support_weight": valuation.get("scenario_support_weight"),
                "valuation_model": valuation.get("model"),
                "valuation_model_count": valuation.get("model_count"),
                "model_agreement": valuation.get("model_agreement"),
                "critical_flag_count": len(trust.get("critical_flags", [])),
                "warning_count": len(trust.get("warnings", [])),
                "potential_score": discovery.get("potential_score"),
                "price_stage": discovery.get("price_stage"),
                "price_maturity": discovery.get("price_maturity"),
                "forward_pe": metrics.get("forward_pe"),
                "next_year_eps_growth": metrics.get("next_year_eps_growth"),
                "eps_revision_30d": metrics.get("eps_revision_30d"),
                "return_12m": metrics.get("return_12m"),
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

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": "0.4-trust-upgrade",
        "reports": len(reports),
        "discovery_run": meta,
        "methodology": (
            "Normal BUY is restricted to established CORE companies with strong data trust, SEC evidence, and at least two agreeing valuation methods. "
            "Scenario weights are not calibrated probabilities."
        ),
    }
    metadata_path = pub / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    return {
        "published_json": json_path,
        "published_csv": csv_path,
        "published_metadata": metadata_path,
    }


def run_full_research(
    settings,
    deep_candidates=160,
    research_candidates=20,
    top_n=30,
    refresh_universe=False,
    max_universe=None,
    force_refresh=False,
    offline=False,
    progress_callback=None,
):
    snapshots, meta = run_discovery(
        settings,
        deep_candidates,
        top_n,
        refresh_universe,
        max_universe,
        force_refresh,
        offline,
        progress_callback,
    )
    successful = sorted(
        [x for x in snapshots if not x.get("error")],
        key=lambda x: x.get("scores", {}).get("total", -1),
        reverse=True,
    )
    chosen, selection_stats = _select_research_candidates(successful, research_candidates, settings.research)

    warehouse = ResearchWarehouse(settings.warehouse_path)
    yahoo = CachedYahooProvider(
        warehouse,
        settings.cache_ttl_hours,
        settings.request_pause_seconds,
        offline,
    )
    sec = CachedSecResearchProvider(
        warehouse,
        float(settings.cache_ttl_hours.get("sec_submissions", 12)),
        offline=offline,
    )

    reports = []
    for i, snapshot in enumerate(chosen, 1):
        if progress_callback:
            progress_callback("research", i, len(chosen), snapshot["ticker"])
        reports.append(research_one(snapshot, yahoo, sec, warehouse, settings.research, settings.llm))

    info = warehouse.cache_info()
    warehouse.close()
    publish_paths = _publish(
        reports,
        settings,
        {
            "run_id": meta.get("run_id"),
            "universe_count": meta.get("universe_count"),
            "price_scan_count": meta.get("price_scan_count"),
            "seed_count": meta.get("seed_count"),
            "market_stats": meta.get("market_stats"),
            "warehouse": info,
            "research_selection": selection_stats,
        },
    )
    meta["research_count"] = len(reports)
    meta["research_selection"] = selection_stats
    meta["published"] = publish_paths
    meta["warehouse_after_research"] = info
    return reports, meta
