from inflection_scanner.ledger import merge_jsonl, read_jsonl


def test_merge_jsonl_is_deduplicated(tmp_path):
    p=tmp_path/"ledger.jsonl"
    merge_jsonl(p,[{"model_version":"5.4.1","asof":"2026-01-01","ticker":"A","x":1}],("model_version","asof","ticker"))
    merge_jsonl(p,[{"model_version":"5.4.1","asof":"2026-01-01","ticker":"A","x":2}],("model_version","asof","ticker"))
    rows=read_jsonl(p)
    assert len(rows)==1
    assert rows[0]["x"]==2

from inflection_scanner.ledger import quarantine_known_v54_operational_placeholders


def test_known_broken_v54_rows_are_quarantined(tmp_path):
    p = tmp_path / "published"
    p.mkdir()
    broken = {
        "model_version": "5.4",
        "asof": "2026-08-18T21:18:40+00:00",
        "ticker": "ALAB",
        "action": "REVIEW DATA",
        "price": None,
        "conviction_score": 0,
        "valuation_status": "DATA_ERROR",
        "trust_score": 0,
    }
    good = {
        "model_version": "5.3",
        "asof": "2026-08-17T00:00:00+00:00",
        "ticker": "AAPL",
        "action": "WATCH — DEVELOPING",
        "price": 200,
        "conviction_score": 65,
        "valuation_status": "UNRESOLVED",
        "trust_score": 90,
    }
    merge_jsonl(p / "decision_ledger.jsonl", [broken, good], ("model_version", "asof", "ticker"))
    merge_jsonl(
        p / "pit_estimates.jsonl",
        [{"model_version": "5.4", "asof": broken["asof"], "ticker": "ALAB", "features": {"price": None}}],
        ("model_version", "asof", "ticker"),
    )
    assert quarantine_known_v54_operational_placeholders(p) == 1
    rows = read_jsonl(p / "decision_ledger.jsonl")
    assert [x["ticker"] for x in rows] == ["AAPL"]
    quarantine = read_jsonl(p / "quarantined_operational_failures.jsonl")
    assert any(x["ticker"] == "ALAB" and x["ledger_type"] == "decision" for x in quarantine)
