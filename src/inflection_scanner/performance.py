from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from pathlib import Path
from typing import Any

from . import MODEL_VERSION
from .ledger import read_jsonl


def _parse_iso(value: str) -> datetime | None:
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00")); return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:return None


def _source_decisions(warehouse, model_version: str, ledger_path: str | Path | None):
    if ledger_path:
        rows=[x for x in read_jsonl(ledger_path) if str(x.get("model_version"))==str(model_version)]
        if rows:return rows
    out=[]
    for report in warehouse.list_research_reports(model_version=model_version):
        out.append({"ticker":report.get("ticker"),"asof":report.get("asof"),"action":report.get("conviction",{}).get("action"),"price":report.get("metrics",{}).get("price"),"conviction_score":report.get("conviction",{}).get("conviction_score"),"thesis_score":report.get("conviction",{}).get("thesis_score"),"entry_score":report.get("conviction",{}).get("entry_score")})
    return out


def build_track_record(warehouse,horizons_days=None,model_version: str = MODEL_VERSION,benchmark: str="SPY",ledger_path: str | Path | None="published/decision_ledger.jsonl",now: datetime | None=None) -> dict[str,Any]:
    horizons=horizons_days or [30,90,180,365]; now=now or datetime.now(timezone.utc); observations=[]
    for row in _source_decisions(warehouse,model_version,ledger_path):
        asof=_parse_iso(str(row.get("asof") or "")); start=row.get("price"); action=row.get("action"); ticker=row.get("ticker")
        if asof is None or not start or not action or not ticker:continue
        for h in horizons:
            target=asof+timedelta(days=int(h))
            if now<target:continue
            end=warehouse.price_near_date(ticker,target.date().isoformat(),max_days=10); bstart=warehouse.price_near_date(benchmark,asof.date().isoformat(),max_days=10); bend=warehouse.price_near_date(benchmark,target.date().isoformat(),max_days=10)
            if end is None:continue
            realized=float(end)/float(start)-1; bench=(float(bend)/float(bstart)-1) if bstart and bend else None
            vals=warehouse.price_window(ticker,asof.date().isoformat(),target.date().isoformat()); mae=min((v/float(start)-1 for v in vals),default=None); mfe=max((v/float(start)-1 for v in vals),default=None)
            observations.append({"ticker":ticker,"asof":row.get("asof"),"action":action,"horizon_days":int(h),"start_price":float(start),"end_price":float(end),"realized_return":round(realized,4),"benchmark_return":round(bench,4) if bench is not None else None,"excess_return":round(realized-bench,4) if bench is not None else None,"max_adverse_excursion":round(mae,4) if mae is not None else None,"max_favorable_excursion":round(mfe,4) if mfe is not None else None,"conviction_score":row.get("conviction_score"),"thesis_score":row.get("thesis_score"),"entry_score":row.get("entry_score")})
    summaries=[]
    for action in sorted({x["action"] for x in observations}):
        for h in horizons:
            rows=[x for x in observations if x["action"]==action and x["horizon_days"]==int(h)]
            if not rows:continue
            rets=[x["realized_return"] for x in rows]; excess=[x["excess_return"] for x in rows if x["excess_return"] is not None]
            summaries.append({"action":action,"horizon_days":int(h),"count":len(rows),"hit_rate":round(sum(x>0 for x in rets)/len(rets),4),"average_return":round(sum(rets)/len(rets),4),"median_return":round(median(rets),4),"positive_excess_rate":round(sum(x>0 for x in excess)/len(excess),4) if excess else None,"average_excess_return":round(sum(excess)/len(excess),4) if excess else None,"enough_history":len(rows)>=10})
    return {"model_version":model_version,"generated_at":now.isoformat(timespec="seconds"),"benchmark":benchmark,"observations":observations,"summaries":summaries,"note":"V5.4 track record is cohort-versioned and can rebuild from the durable committed decision ledger even if the Actions warehouse cache is lost."}
