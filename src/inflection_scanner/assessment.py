from __future__ import annotations

from typing import Any


def build_assessment(report: dict[str, Any]) -> dict[str, list[str]]:
    f=report.get("metrics",{}); v=report.get("valuation",{}); t=report.get("trust",{}); c=report.get("conviction",{})
    why=[]; why_not=[]
    if t.get("preferred_large_cap"): why.append("Company is in the preferred institutional-scale large-cap tier.")
    if isinstance(f.get("eps_revision_30d"),(int,float)): why.append(f"30-day EPS consensus revision is {f['eps_revision_30d']:.1%}.")
    if isinstance(f.get("operating_margin_change_yoy"),(int,float)) and f["operating_margin_change_yoy"]>0: why.append(f"Operating margin improved {f['operating_margin_change_yoy']:+.1%} year over year.")
    if v.get("valuation_resolved"): why.append(f"{v.get('model_count',0)} independent valuation methods pass the agreement gate.")
    if not v.get("valuation_resolved"): why_not.append(f"Valuation is unresolved: {v.get('reason')}")
    why_not.extend(f"DATA: {x}" for x in v.get("critical_flags",[])); why_not.extend(f"Trust: {x}" for x in t.get("warnings",[])[:4])
    return {"why_buy":why,"why_not":why_not,"what_must_be_true":["Forward revenue/EPS estimates remain achievable.","Margins and free-cash-flow conversion remain consistent with the valuation family.","The industry demand backdrop remains supportive."],"invalidation":["Two consecutive material downward estimate revisions without a compensating valuation reset.","Revenue growth and operating-margin direction both deteriorate.","New credible evidence breaks the balance-sheet, demand, accounting, or customer-concentration assumptions."],"what_changes_decision":c.get("failed_checks",[])}
