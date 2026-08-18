from datetime import datetime, timedelta, timezone

import pandas as pd

from inflection_scanner.ledger import merge_jsonl
from inflection_scanner.performance import build_track_record
from inflection_scanner.warehouse import ResearchWarehouse


def _price_df(dates, closes):
    return pd.DataFrame({"Open":closes,"High":[x*1.01 for x in closes],"Low":[x*.99 for x in closes],"Close":closes,"Volume":[1_000_000]*len(closes)},index=pd.to_datetime(dates))


def test_v54_track_record_reads_v54_ledger_and_benchmark(tmp_path):
    w=ResearchWarehouse(tmp_path/"warehouse.db")
    now=datetime(2026,8,18,tzinfo=timezone.utc); asof=now-timedelta(days=120); target=asof+timedelta(days=90)
    dates=[asof.date().isoformat(),(asof+timedelta(days=45)).date().isoformat(),target.date().isoformat()]
    w.upsert_prices("XYZ",_price_df(dates,[100,90,120])); w.upsert_prices("SPY",_price_df(dates,[500,510,550]))
    ledger=tmp_path/"decision_ledger.jsonl"
    merge_jsonl(ledger,[{"model_version":"5.4.1","asof":asof.isoformat(),"ticker":"XYZ","action":"BUY NOW","price":100,"conviction_score":80,"thesis_score":82,"entry_score":75}],("model_version","asof","ticker"))
    track=build_track_record(w,[90],model_version="5.4.1",benchmark="SPY",ledger_path=ledger,now=now)
    w.close()
    assert track["model_version"]=="5.4.1"
    assert len(track["observations"])==1
    obs=track["observations"][0]
    assert obs["realized_return"]==0.2
    assert obs["benchmark_return"]==0.1
    assert obs["excess_return"]==0.1
    assert obs["max_adverse_excursion"]==-0.1
    assert obs["max_favorable_excursion"]==0.2


def test_v54_track_record_does_not_mix_v53(tmp_path):
    w=ResearchWarehouse(tmp_path/"w.db"); now=datetime(2026,8,18,tzinfo=timezone.utc); asof=now-timedelta(days=40); dates=[asof.date().isoformat(),now.date().isoformat()]
    w.upsert_prices("XYZ",_price_df(dates,[100,110]))
    ledger=tmp_path/"l.jsonl"
    merge_jsonl(ledger,[{"model_version":"5.3","asof":asof.isoformat(),"ticker":"XYZ","action":"BUY NOW","price":100}],("model_version","asof","ticker"))
    track=build_track_record(w,[30],model_version="5.4.1",ledger_path=ledger,now=now)
    w.close()
    assert track["observations"]==[]
