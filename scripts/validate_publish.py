from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that a V5.3 research run produced usable dashboard data. SEC evidence is optional."
    )
    parser.add_argument("--published", default="published", help="Published directory")
    parser.add_argument("--min-reports", type=int, default=5)
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

    required = {"ticker", "conviction", "valuation", "trust", "metrics"}
    bad = [
        i for i, report in enumerate(reports)
        if not isinstance(report, dict) or not required.issubset(report)
    ]
    if bad:
        print(f"ERROR: malformed report objects at indexes: {bad[:10]}")
        return 2

    sec_ready = sum(
        bool((report.get("sec_status") or {}).get("documents_cached"))
        for report in reports
    )
    print(
        f"Publish validation OK: {len(reports)} reports. "
        f"Optional SEC enrichment is present for {sec_ready}/{len(reports)} report(s); SEC is not required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
