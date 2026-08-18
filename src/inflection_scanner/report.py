from __future__ import annotations

from typing import Any


def compact_summary(report: dict[str, Any]) -> dict[str, Any]:
    c=report.get("conviction",{}); v=report.get("valuation",{}); t=report.get("trust",{}); m=report.get("metrics",{})
    return {"ticker":report.get("ticker"),"company":report.get("company"),"action":c.get("action"),"thesis_score":c.get("thesis_score"),"entry_score":c.get("entry_score"),"price":m.get("price"),"buy_below_price":c.get("buy_below_price"),"valuation_status":v.get("valuation_status"),"trust_grade":t.get("trust_grade")}
