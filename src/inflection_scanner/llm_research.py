from __future__ import annotations

import os
from typing import Any


def llm_enabled() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def enrich_report(report: dict[str, Any]) -> dict[str, Any]:
    # V5.4 deliberately keeps deterministic scoring independent of any LLM.
    # Narrative enrichment can be added by callers without changing decisions.
    return report
