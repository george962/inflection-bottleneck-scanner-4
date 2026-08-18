from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--published", default="published")
    ap.add_argument("--min-reports", type=int, default=5)
    ap.add_argument("--min-successful-reports", type=int, default=5)
    ap.add_argument("--max-operational-failure-fraction", type=float, default=0.25)
    args = ap.parse_args()
    p = Path(args.published)
    research = p / "latest_research.json"
    metadata = p / "metadata.json"
    track = p / "track_record.json"
    ledger = p / "decision_ledger.jsonl"
    pit = p / "pit_estimates.jsonl"
    for f in [research, metadata, track, ledger, pit]:
        if not f.exists():
            raise SystemExit(f"Missing required publish artifact: {f}")

    rows = json.loads(research.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) < args.min_reports:
        got = len(rows) if isinstance(rows, list) else "invalid"
        raise SystemExit(f"Expected at least {args.min_reports} reports; got {got}")

    operational = []
    successful = []
    for i, r in enumerate(rows):
        for key in ["model_version", "asof", "ticker", "conviction", "valuation", "trust"]:
            if key not in r:
                raise SystemExit(f"Report {i} missing {key}")
        if "@" in json.dumps(r.get("sec_status", {})):
            raise SystemExit(
                "Published SEC diagnostic appears to contain an email/header value; sanitize before publishing."
            )
        if str(r.get("pipeline_status") or "").upper() == "OPERATIONAL_FAILURE":
            operational.append(r)
        else:
            successful.append(r)

    frac = len(operational) / len(rows) if rows else 1.0
    if len(successful) < args.min_successful_reports:
        raise SystemExit(
            f"Publish unhealthy: only {len(successful)} successful reports; "
            f"minimum is {args.min_successful_reports}."
        )
    if frac > args.max_operational_failure_fraction:
        types = sorted({str(r.get('operational_error_type') or 'UNKNOWN') for r in operational})
        raise SystemExit(
            f"Publish unhealthy: {len(operational)}/{len(rows)} reports ({frac:.1%}) failed operationally; "
            f"maximum is {args.max_operational_failure_fraction:.1%}. Error types: {', '.join(types)}"
        )

    meta = json.loads(metadata.read_text(encoding="utf-8"))
    if str(meta.get("model_version")) != "5.4.1":
        raise SystemExit("metadata model_version is not 5.4.1")
    if str(meta.get("warehouse_schema_version")) != "5.4.1":
        raise SystemExit("warehouse schema version is not 5.4.1")
    if int(meta.get("successful_reports", -1)) != len(successful):
        raise SystemExit("metadata successful_reports does not match latest_research.json")

    # Operational failures must not enter durable investment-decision history.
    ledger_text = ledger.read_text(encoding="utf-8")
    for r in operational:
        if r.get("asof") and r.get("ticker") and r.get("asof") in ledger_text and f'"ticker":"{r.get("ticker")}"' in ledger_text:
            raise SystemExit("Operational failure appears to have been written to decision_ledger.jsonl")

    print(
        f"OK: {len(successful)} successful V5.4.1 reports, "
        f"{len(operational)} operational failures ({frac:.1%})"
    )


if __name__ == "__main__":
    main()
