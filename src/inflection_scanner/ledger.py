from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ordered = list(rows)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", dir=str(p.parent))
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for row in ordered:
                f.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def merge_jsonl(path: str | Path, rows: Iterable[dict[str, Any]], key_fields: tuple[str, ...]) -> int:
    p = Path(path)
    existing = read_jsonl(p)
    by_key = {_key(x, key_fields): x for x in existing}
    before = len(by_key)
    for row in rows:
        by_key[_key(row, key_fields)] = row
    ordered = sorted(by_key.values(), key=lambda x: tuple(str(x.get(k, "")) for k in key_fields))
    _write_jsonl(p, ordered)
    return len(by_key) - before


def quarantine_known_v54_operational_placeholders(published_dir: str | Path) -> int:
    """Move known broken V5.4 infrastructure placeholders out of durable ledgers.

    The 2026-08-18 V5.4 migration bug produced rows with no market price,
    DATA_ERROR valuation, REVIEW DATA action, and zero conviction/trust. Those
    were infrastructure failures, not investment decisions. Preserve them in a
    quarantine file, but remove them from decision/PIT history.
    """
    p = Path(published_dir)
    decision_path = p / "decision_ledger.jsonl"
    pit_path = p / "pit_estimates.jsonl"
    decisions = read_jsonl(decision_path)
    bad = [x for x in decisions if _is_known_v54_operational_placeholder(x)]
    if not bad:
        return 0

    bad_keys = {_key(x, ("model_version", "asof", "ticker")) for x in bad}
    keep_decisions = [x for x in decisions if _key(x, ("model_version", "asof", "ticker")) not in bad_keys]
    _write_jsonl(decision_path, keep_decisions)

    pits = read_jsonl(pit_path)
    bad_pits = [x for x in pits if _key(x, ("model_version", "asof", "ticker")) in bad_keys]
    keep_pits = [x for x in pits if _key(x, ("model_version", "asof", "ticker")) not in bad_keys]
    _write_jsonl(pit_path, keep_pits)

    quarantine_rows = []
    for row in bad:
        quarantine_rows.append({
            **row,
            "ledger_type": "decision",
            "quarantine_reason": "Known V5.4 operational placeholder from warehouse schema mismatch; not an investment decision.",
        })
    for row in bad_pits:
        quarantine_rows.append({
            **row,
            "ledger_type": "pit_estimate",
            "quarantine_reason": "Associated with known V5.4 operational placeholder from warehouse schema mismatch.",
        })
    merge_jsonl(
        p / "quarantined_operational_failures.jsonl",
        quarantine_rows,
        ("ledger_type", "model_version", "asof", "ticker"),
    )
    return len(bad)


def _is_known_v54_operational_placeholder(row: dict[str, Any]) -> bool:
    return bool(
        str(row.get("model_version")) == "5.4"
        and str(row.get("action") or "").upper() == "REVIEW DATA"
        and row.get("price") is None
        and str(row.get("valuation_status") or "").upper() == "DATA_ERROR"
        and float(row.get("conviction_score") or 0) == 0.0
        and float(row.get("trust_score") or 0) == 0.0
    )


def decision_row(report: dict[str, Any], config_hash: str, code_hash: str | None = None) -> dict[str, Any]:
    c = report.get("conviction", {})
    m = report.get("metrics", {})
    v = report.get("valuation", {})
    t = report.get("trust", {})
    return {
        "model_version": report.get("model_version"),
        "asof": report.get("asof"),
        "ticker": report.get("ticker"),
        "company": report.get("company"),
        "action": c.get("action"),
        "price": m.get("price"),
        "conviction_score": c.get("conviction_score"),
        "thesis_score": c.get("thesis_score"),
        "entry_score": c.get("entry_score"),
        "pillars": c.get("pillars"),
        "buy_below_price": c.get("buy_below_price"),
        "valuation_status": v.get("valuation_status"),
        "expected_cagr": v.get("expected_cagr"),
        "base_cagr": v.get("base_cagr"),
        "bear_return": v.get("bear_return"),
        "trust_score": t.get("trust_score"),
        "config_hash": config_hash,
        "code_hash": code_hash,
        "input_fingerprint": _fingerprint({
            "metrics": m,
            "normalization": v.get("security_normalization"),
            "asof": report.get("asof"),
        }),
    }


def pit_row(report: dict[str, Any], config_hash: str, code_hash: str | None = None) -> dict[str, Any]:
    m = report.get("metrics", {})
    keys = [
        "price", "revenue_yoy", "revenue_acceleration", "operating_margin",
        "operating_margin_change_yoy", "free_cash_flow_margin", "eps_revision_7d",
        "eps_revision_30d", "eps_revision_90d", "revision_breadth_30d",
        "next_year_eps_estimate", "next_year_eps_growth", "next_year_revenue_estimate",
        "next_year_revenue_growth_estimate", "next_year_eps_analyst_count", "forward_pe",
    ]
    return {
        "model_version": report.get("model_version"),
        "asof": report.get("asof"),
        "ticker": report.get("ticker"),
        "features": {k: m.get(k) for k in keys},
        "source_freshness": report.get("source_freshness", {}),
        "config_hash": config_hash,
        "code_hash": code_hash,
    }


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _key(row, fields):
    return tuple(str(row.get(x, "")) for x in fields)
