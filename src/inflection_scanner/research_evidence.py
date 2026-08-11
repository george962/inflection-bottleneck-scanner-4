from __future__ import annotations

import re


TOPICS = {
    "demand": ["demand", "bookings", "backlog", "orders", "customer demand", "pipeline"],
    "pricing": ["pricing", "average selling price", "asp", "price increase", "price decreases"],
    "capacity_supply": ["capacity", "supply constraint", "supply constraints", "lead time", "lead times", "utilization", "sold out"],
    "customers": ["customer concentration", "major customer", "largest customer", "hyperscaler", "qualification", "design win"],
    "margins": ["gross margin", "operating margin", "margin expansion", "margin pressure", "profitability"],
    "capital": ["capital expenditure", "capex", "liquidity", "debt", "refinancing", "cash flow", "free cash flow"],
    "catalysts": ["launch", "ramp", "ramping", "qualification", "design win", "new product", "capacity expansion", "commercial production", "shipments"],
    "risks": ["risk", "uncertainty", "competition", "competitive", "shortage", "delay", "delays", "regulatory"],
}

POSITIVE = [
    "increase", "increased", "increasing", "growth", "strong", "improved", "improving", "expansion", "higher",
    "record", "accelerat", "sold out", "fully committed", "design win", "qualification", "ramp",
]
NEGATIVE = [
    "decrease", "decreased", "decline", "declined", "weak", "pressure", "lower", "delay", "uncertain", "risk",
    "constraint", "shortage", "loss", "impairment", "cancellation",
]


def _sentences(text):
    return [
        re.sub(r"\s+", " ", x).strip()
        for x in re.split(r"(?<=[.!?])\s+", text or "")
        if len(x.strip()) >= 45
    ]


def _tone(sentence):
    low = sentence.lower()
    pos = sum(term in low for term in POSITIVE)
    neg = sum(term in low for term in NEGATIVE)
    return "positive" if pos > neg else "negative" if neg > pos else "mixed"


def extract_filing_evidence(filings, max_per_topic=4):
    evidence = []
    seen = set()
    for filing in filings:
        for sentence in _sentences(filing.get("text", "")):
            low = sentence.lower()
            for topic, terms in TOPICS.items():
                if not any(term in low for term in terms):
                    continue
                key = (topic, sentence[:180])
                if key in seen:
                    continue
                seen.add(key)
                evidence.append(
                    {
                        "topic": topic,
                        "tone": _tone(sentence),
                        "text": sentence[:700],
                        "form": filing.get("form"),
                        "filing_date": filing.get("filing_date"),
                        "source_url": filing.get("source_url"),
                        "accession": filing.get("accession"),
                    }
                )
    output = []
    for topic in TOPICS:
        rows = [e for e in evidence if e["topic"] == topic]
        rows.sort(key=lambda x: str(x.get("filing_date") or ""), reverse=True)
        output.extend(rows[:max_per_topic])
    return output


def summarize_evidence(evidence):
    pos = sum(e.get("tone") == "positive" for e in evidence)
    neg = sum(e.get("tone") == "negative" for e in evidence)
    return {
        "positive_count": pos,
        "negative_count": neg,
        "mixed_count": len(evidence) - pos - neg,
        "topics_found": sorted({e["topic"] for e in evidence}),
        "net_tone": pos - neg,
    }
