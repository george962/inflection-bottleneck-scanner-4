import pandas as pd

from inflection_scanner.warehouse import ResearchWarehouse


def test_warehouse_prices_and_reports(tmp_path):
    w=ResearchWarehouse(tmp_path/"w.db")
    df=pd.DataFrame({"Open":[1],"High":[1.1],"Low":[.9],"Close":[1.05],"Volume":[100]},index=pd.to_datetime(["2026-01-01"]))
    assert w.upsert_prices("XYZ",df)==1
    assert w.price_near_date("XYZ","2026-01-01")==1.05
    report={"model_version":"5.4.1","asof":"2026-01-01T00:00:00+00:00","ticker":"XYZ","metrics":{"price":1.05},"conviction":{"action":"WATCH"}}
    w.put_research_report("XYZ",report["asof"],"WATCH",50,report)
    assert len(w.list_research_reports("5.4.1"))==1
    assert len(w.list_research_reports("5.3"))==0
    w.close()
