from inflection_scanner.ledger import merge_jsonl, read_jsonl


def test_merge_jsonl_is_deduplicated(tmp_path):
    p=tmp_path/"ledger.jsonl"
    merge_jsonl(p,[{"model_version":"5.4","asof":"2026-01-01","ticker":"A","x":1}],("model_version","asof","ticker"))
    merge_jsonl(p,[{"model_version":"5.4","asof":"2026-01-01","ticker":"A","x":2}],("model_version","asof","ticker"))
    rows=read_jsonl(p)
    assert len(rows)==1
    assert rows[0]["x"]==2
