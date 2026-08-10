from pathlib import Path
import pandas as pd
from inflection_scanner.warehouse import ResearchWarehouse

def test_json_cache(tmp_path:Path):
    w=ResearchWarehouse(tmp_path/"w.db");w.put_json("x",{"a":1},1);assert w.get_json("x")=={"a":1};w.close()
def test_prices_idempotent(tmp_path:Path):
    w=ResearchWarehouse(tmp_path/"w.db");idx=pd.to_datetime(["2026-08-07","2026-08-10"])
    df=pd.DataFrame({"Open":[10,11],"High":[11,12],"Low":[9,10],"Close":[10.5,11.5],"Volume":[1000,1200]},index=idx)
    w.upsert_prices("XYZ",df);w.upsert_prices("XYZ",df);x=w.load_prices("XYZ");assert len(x)==2 and float(x.iloc[-1].Close)==11.5;w.close()
def test_filing_cache(tmp_path:Path):
    w=ResearchWarehouse(tmp_path/"w.db");w.put_filing("XYZ","0001","10-Q","2026-08-01","2026-06-30","https://example.com","Demand increased and backlog improved.")
    assert w.has_filing("XYZ","0001");assert "Demand increased" in w.recent_filings("XYZ",5)[0]["text"];w.close()
