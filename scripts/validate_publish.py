from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate that a V5.2 research run produced usable dashboard/evidence data.")
    parser.add_argument("--published", default="published", help="Published directory")
    parser.add_argument("--min-reports", type=int, default=5)
    parser.add_argument("--min-sec-ready-fraction", type=float, default=0.60)
    args = parser.parse_args()

    root = Path(args.published)
    research_path = root / "latest_research.json"
    metadata_path = root / "metadata.json"

    if not research_path.exists():
        print(f"ERROR: {research_path} does not exist.")
        return 2

    try:
        reports = json.loads(research_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot parse {research_path}: {exc}")
        return 2

    metadata = {}
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            metadata = {}

    if not isinstance(reports, list):
        print("ERROR: latest_research.json must contain a JSON list.")
        return 2

    if len(reports) < args.min_reports:
        selection = metadata.get("discovery_run", {}).get("research_selection", {}) or {}
        print(f"ERROR: research produced only {len(reports)} report(s); minimum required is {args.min_reports}.")
        print("Research selection diagnostics:")
        print(json.dumps(selection, indent=2, sort_keys=True))
        return 1

    required = {"ticker", "conviction", "valuation", "trust", "metrics", "sec_status"}
    bad = [i for i, report in enumerate(reports) if not isinstance(report, dict) or not required.issubset(report)]
    if bad:
        print(f"ERROR: malformed report objects at indexes: {bad[:10]}")
        return 2

    sec_ready = sum(bool(report.get("trust", {}).get("evidence_ready")) for report in reports)
    sec_fraction = sec_ready / len(reports) if reports else 0.0
    if sec_fraction < args.min_sec_ready_fraction:
        print(
            f"ERROR: SEC evidence is ready for only {sec_ready}/{len(reports)} reports ({sec_fraction:.0%}); "
            f"minimum is {args.min_sec_ready_fraction:.0%}."
        )
        states = {}
        for report in reports:
            state = str(report.get("sec_status", {}).get("state") or "UNKNOWN")
            states[state] = states.get(state, 0) + 1
        print("SEC state counts:", json.dumps(states, indent=2, sort_keys=True))
        sample_errors = []
        for report in reports:
            errors = report.get("sec_status", {}).get("errors", []) or []
            if errors:
                sample_errors.append({"ticker": report.get("ticker"), "error": errors[0]})
            if len(sample_errors) >= 5:
                break
        if sample_errors:
            print("Sample SEC errors:")
            print(json.dumps(sample_errors, indent=2))
        print("Refusing a green publish because the recommendation layer depends on filing evidence.")
        return 1

    print(f"Publish validation OK: {len(reports)} reports; SEC evidence ready for {sec_ready}/{len(reports)} ({sec_fraction:.0%}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
