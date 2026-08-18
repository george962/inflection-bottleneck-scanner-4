from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import MODEL_VERSION
from .build_info import source_hash
from .config import config_hash
from .ledger import decision_row, merge_jsonl, pit_row, quarantine_known_v54_operational_placeholders
from .performance import build_track_record
from .research_engine import ResearchEngine
from .sanitize import sanitize_text


def select_research_candidates(discovery: dict[str, Any], count: int) -> list[str]:
    candidates = discovery.get("candidates", [])
    early = [x for x in candidates if x.get("price_stage") != "LATE"]
    late = [x for x in candidates if x.get("price_stage") == "LATE"]
    nlate = min(len(late), max(0, round(count * 0.2)))
    selected = early[: max(0, count - nlate)] + late[:nlate]
    if len(selected) < count:
        used = {x["ticker"] for x in selected}
        for row in candidates:
            if row["ticker"] not in used:
                selected.append(row)
                used.add(row["ticker"])
                if len(selected) >= count:
                    break
    return [x["ticker"] for x in selected[:count]]


def _operational_failure_report(ticker: str, exc: BaseException) -> dict[str, Any]:
    # Keep useful local diagnostics while stripping line breaks/emails/headers.
    detail = sanitize_text(str(exc), max_chars=240)
    diagnostic = f"{exc.__class__.__name__}: {detail}" if detail else exc.__class__.__name__
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "model_version": MODEL_VERSION,
        "asof": now,
        "ticker": ticker,
        "company": ticker,
        "pipeline_status": "OPERATIONAL_FAILURE",
        "operational_error_type": exc.__class__.__name__,
        "operational_error": diagnostic,
        "metrics": {},
        "valuation": {"valuation_status": "DATA_ERROR", "valuation_resolved": False},
        "trust": {
            "trust_grade": "D",
            "trust_score": 0,
            "critical_flags": [f"Research failed: {diagnostic}"],
        },
        "conviction": {
            "action": "REVIEW DATA",
            "conviction_score": 0,
            "thesis_score": 0,
            "entry_score": 0,
            "pillars": {},
            "rationale": "Research pipeline failed operationally; this is not an investment decision.",
        },
        "decision": {
            "decision": "REVIEW DATA",
            "confidence": "LOW",
            "reason": "Research pipeline failed operationally; this is not an investment decision.",
        },
    }


def is_operational_failure(report: dict[str, Any]) -> bool:
    return str(report.get("pipeline_status") or "").upper() == "OPERATIONAL_FAILURE"


def run_full_research(
    provider,
    warehouse,
    cfg,
    discovery,
    security_overrides=None,
    research_count=None,
    published_dir="published",
    force_refresh=False,
):
    count = int(research_count or cfg.get("research", {}).get("research_candidates", 24))
    tickers = select_research_candidates(discovery, count)
    engine = ResearchEngine(provider, warehouse, cfg, security_overrides)
    reports = []
    for ticker in tickers:
        try:
            report = engine.research(ticker, force_refresh=force_refresh)
            report.setdefault("pipeline_status", "OK")
            reports.append(report)
        except Exception as exc:
            reports.append(_operational_failure_report(ticker, exc))

    p = Path(published_dir)
    p.mkdir(parents=True, exist_ok=True)
    ch = config_hash(cfg)
    code_hash = source_hash()
    (p / "latest_research.json").write_text(
        json.dumps(reports, indent=2, default=str), encoding="utf-8"
    )
    _write_csv(p / "latest_research.csv", reports)

    # Remove the known broken V5.4 operational placeholders from durable history
    # while preserving them in a quarantine audit file.
    quarantined_legacy = quarantine_known_v54_operational_placeholders(p)

    # Operational failures are diagnostics, not model decisions. Never pollute
    # the permanent decision/PIT ledgers with infrastructure failures.
    successful = [r for r in reports if not is_operational_failure(r)]
    merge_jsonl(
        p / "decision_ledger.jsonl",
        [decision_row(x, ch, code_hash) for x in successful],
        ("model_version", "asof", "ticker"),
    )
    merge_jsonl(
        p / "pit_estimates.jsonl",
        [pit_row(x, ch, code_hash) for x in successful],
        ("model_version", "asof", "ticker"),
    )

    track = build_track_record(
        warehouse,
        cfg.get("research", {}).get("performance_horizons_days"),
        MODEL_VERSION,
        cfg.get("benchmark", "SPY"),
        p / "decision_ledger.jsonl",
    )
    (p / "track_record.json").write_text(json.dumps(track, indent=2), encoding="utf-8")

    failure_count = len(reports) - len(successful)
    failure_rate = failure_count / len(reports) if reports else 1.0
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": "0.5.4.1",
        "model_version": MODEL_VERSION,
        "config_hash": ch,
        "code_hash": code_hash,
        "reports": len(reports),
        "successful_reports": len(successful),
        "operational_failures": failure_count,
        "operational_failure_fraction": round(failure_rate, 4),
        "warehouse_schema_version": warehouse.schema_version(),
        "quarantined_legacy_operational_decisions": quarantined_legacy,
        "discovery_run": {k: v for k, v in discovery.items() if k != "candidates"},
        "methodology": (
            "V5.4.1 is a reliability hotfix adding explicit V5.3/V5.4 SQLite migration, "
            "schema versioning, publish health gates, and exclusion of operational failures "
            "from durable decision/PIT ledgers, while retaining V5.4 currency/ADR and classification fixes."
        ),
    }
    (p / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"reports": reports, "metadata": meta, "track_record": track}


def _write_csv(path: Path, reports: list[dict[str, Any]]):
    fields = [
        "ticker", "company", "pipeline_status", "operational_error_type", "action",
        "conviction_score", "thesis_score", "entry_score", "entry_state", "risk_tier",
        "size_class", "market_cap", "years_public", "analyst_count", "trust_grade",
        "trust_score", "current_price", "buy_below_price", "valuation_status", "company_type",
        "expected_cagr", "base_cagr", "bear_return", "valuation_model_count", "model_agreement",
        "fundamental_pillar", "revision_pillar", "valuation_pillar", "timing_pillar",
        "quality_pillar", "evidence_pillar", "price_stage", "price_maturity", "return_6m",
        "return_12m", "distance_from_52w_high", "forward_pe", "next_year_eps_growth",
        "eps_revision_30d",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in reports:
            c = r.get("conviction", {})
            t = r.get("trust", {})
            m = r.get("metrics", {})
            v = r.get("valuation", {})
            pillars = c.get("pillars", {})
            e = c.get("entry_timing", {})
            w.writerow({
                "ticker": r.get("ticker"), "company": r.get("company"),
                "pipeline_status": r.get("pipeline_status"),
                "operational_error_type": r.get("operational_error_type"),
                "action": c.get("action"), "conviction_score": c.get("conviction_score"),
                "thesis_score": c.get("thesis_score"), "entry_score": c.get("entry_score"),
                "entry_state": e.get("entry_state"), "risk_tier": t.get("risk_tier"),
                "size_class": t.get("size_class"), "market_cap": t.get("market_cap"),
                "years_public": t.get("years_public"), "analyst_count": t.get("analyst_count"),
                "trust_grade": t.get("trust_grade"), "trust_score": t.get("trust_score"),
                "current_price": m.get("price"), "buy_below_price": c.get("buy_below_price"),
                "valuation_status": v.get("valuation_status"), "company_type": v.get("company_type"),
                "expected_cagr": v.get("expected_cagr"), "base_cagr": v.get("base_cagr"),
                "bear_return": v.get("bear_return"), "valuation_model_count": v.get("model_count"),
                "model_agreement": v.get("model_agreement"),
                "fundamental_pillar": pillars.get("fundamental_inflection"),
                "revision_pillar": pillars.get("estimate_revision"),
                "valuation_pillar": pillars.get("valuation"), "timing_pillar": pillars.get("price_timing"),
                "quality_pillar": pillars.get("company_quality"), "evidence_pillar": pillars.get("evidence"),
                "price_stage": m.get("price_stage"), "price_maturity": m.get("price_maturity"),
                "return_6m": m.get("return_6m"), "return_12m": m.get("return_12m"),
                "distance_from_52w_high": m.get("distance_from_52w_high"),
                "forward_pe": m.get("forward_pe"), "next_year_eps_growth": m.get("next_year_eps_growth"),
                "eps_revision_30d": m.get("eps_revision_30d"),
            })
