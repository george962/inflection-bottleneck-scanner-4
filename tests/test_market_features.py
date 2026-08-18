import pandas as pd

from inflection_scanner.features.market import market_features


def test_market_features_basic():
    idx=pd.date_range("2025-01-01",periods=300,freq="B")
    close=pd.Series(range(100,400),index=idx,dtype=float)
    df=pd.DataFrame({"Close":close,"Volume":1_000_000},index=idx)
    out=market_features(df)
    assert out["price"]==399
    assert out["return_12m"] is not None
    assert out["dollar_volume_20d"]>0
