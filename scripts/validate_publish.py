from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--published",default="published"); ap.add_argument("--min-reports",type=int,default=5); args=ap.parse_args(); p=Path(args.published)
    research=p/"latest_research.json"; metadata=p/"metadata.json"; track=p/"track_record.json"; ledger=p/"decision_ledger.jsonl"
    for f in [research,metadata,track,ledger]:
        if not f.exists(): raise SystemExit(f"Missing required publish artifact: {f}")
    rows=json.loads(research.read_text(encoding="utf-8"))
    if not isinstance(rows,list) or len(rows)<args.min_reports: raise SystemExit(f"Expected at least {args.min_reports} reports; got {len(rows) if isinstance(rows,list) else 'invalid'}")
    for i,r in enumerate(rows):
        for key in ["model_version","asof","ticker","conviction","valuation","trust"]:
            if key not in r: raise SystemExit(f"Report {i} missing {key}")
        if "@" in json.dumps(r.get("sec_status",{})):
            raise SystemExit("Published SEC diagnostic appears to contain an email/header value; sanitize before publishing.")
    meta=json.loads(metadata.read_text(encoding="utf-8"))
    if str(meta.get("model_version"))!="5.4": raise SystemExit("metadata model_version is not 5.4")
    print(f"OK: {len(rows)} structurally valid V5.4 reports")

if __name__=="__main__": main()
