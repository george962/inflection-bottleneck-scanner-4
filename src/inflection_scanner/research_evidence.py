from __future__ import annotations

from typing import Any


def summarize_evidence(filings: list[dict[str, Any]] | None = None, news: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    filings=filings or []; news=news or []
    return {"positive_count":0,"negative_count":0,"mixed_count":0,"topics_found":[],"net_tone":0,"filing_count":len(filings),"news_count":len(news)}
