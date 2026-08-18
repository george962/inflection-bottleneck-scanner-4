from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _flat_row(snapshot: dict[str, Any]) -> dict[str, Any]:
    scores = snapshot.get("scores", {})
    features = snapshot.get("features", {})
    profile = snapshot.get("profile", {})
    assessment = snapshot.get("assessment", {})
    return {
        "rank": snapshot.get("rank"),
        "ticker": snapshot.get("ticker"),
        "company": snapshot.get("company"),
        "potential_score": scores.get("total"),
        "score_delta_last": assessment.get("score_delta_last"),
        "action": assessment.get("action"),
        "stage": assessment.get("stage"),
        "price_stage": assessment.get("price_stage"),
        "discovery_bucket": features.get("discovery_bucket"),
        "price": features.get("price"),
        "return_1m": features.get("return_1m"),
        "return_3m": features.get("return_3m"),
        "return_6m": features.get("return_6m"),
        "return_12m": features.get("return_12m"),
        "forward_pe": profile.get("forward_pe"),
        "next_year_eps_growth": features.get("next_year_eps_growth"),
        "next_year_revenue_growth": features.get("next_year_revenue_growth_estimate"),
        "eps_revision_30d": features.get("eps_revision_30d"),
        "eps_revision_90d": features.get("eps_revision_90d"),
        "analyst_target_upside": scores.get("analyst_target_upside"),
        "fundamental": scores.get("fundamental"),
        "revisions": scores.get("revisions"),
        "forward_growth": scores.get("forward_growth"),
        "valuation_upside": scores.get("valuation_upside"),
        "operating_leverage": scores.get("operating_leverage"),
        "expectation_gap": scores.get("expectation_gap"),
        "early_discovery": scores.get("early_discovery"),
        "price_maturity": scores.get("price_maturity"),
        "data_quality": snapshot.get("data_quality"),
        "why_discovered": " | ".join(assessment.get("why_discovered", [])),
        "risk_flags": " | ".join(assessment.get("risk_flags", [])),
        "missing_evidence": " | ".join(assessment.get("missing_evidence", [])),
        "next_triggers": " | ".join(assessment.get("next_triggers", [])),
    }


def write_reports(
    snapshots: list[dict[str, Any]],
    output_dir: str | Path,
    top_n: int = 30,
) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    successful = [s for s in snapshots if not s.get("error")]
    successful.sort(
        key=lambda s: s.get("scores", {}).get("total", -1),
        reverse=True,
    )
    for i, s in enumerate(successful, 1):
        s["rank"] = i

    top = successful[:top_n]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    json_path = out / "latest.json"
    json_path.write_text(
        json.dumps(top, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )

    csv_path = out / "latest.csv"
    rows = [_flat_row(s) for s in top]
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8")

    md_path = out / f"report_{stamp}.md"
    lines = [
        "# Broad-Universe Stock Discovery Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "The list is ranked for **forward potential after price maturity**, not generic company quality.",
        "",
        "| # | Ticker | Potential | Action | Price stage | Bucket | 3M | 12M | Fwd P/E | EPS growth | 30D revisions | Target upside |",
        "|---:|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    def pct(v):
        try:
            return f"{float(v):.1%}"
        except (TypeError, ValueError):
            return ""

    def num(v):
        try:
            return f"{float(v):.1f}"
        except (TypeError, ValueError):
            return ""

    for s in top:
        f = s.get("features", {})
        sc = s.get("scores", {})
        a = s.get("assessment", {})
        p = s.get("profile", {})
        lines.append(
            f"| {s['rank']} | {s['ticker']} | {sc.get('total',0):.1f} | "
            f"{a.get('action','')} | {a.get('price_stage','')} | "
            f"{f.get('discovery_bucket','')} | {pct(f.get('return_3m'))} | "
            f"{pct(f.get('return_12m'))} | {num(p.get('forward_pe'))} | "
            f"{pct(f.get('next_year_eps_growth'))} | "
            f"{pct(f.get('eps_revision_30d'))} | "
            f"{pct(sc.get('analyst_target_upside'))} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "- **CANDIDATE** means the free-data model found enough evidence to justify serious research; it is not an automatic buy order.",
        "- **DEEP RESEARCH** means the setup is interesting but one or more important pieces are weaker or missing.",
        "- **DO NOT CHASE** means the price has already rerated enough that strong fundamentals alone are insufficient.",
        "- Analyst target upside is weak supporting evidence only; it is not treated as a forecast truth.",
    ]

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "markdown": md_path}
