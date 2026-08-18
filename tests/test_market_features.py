import numpy as np
import pandas as pd

from inflection_scanner.features.market import compute_market_features


def test_market_features_positive_trend():
    n = 300
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = pd.Series(np.linspace(100, 200, n), index=idx)
    vol = pd.Series(np.full(n, 1_000_000.0), index=idx)
    hist = pd.DataFrame({"Close": close, "Volume": vol})

    bench_close = pd.Series(np.linspace(100, 130, n), index=idx)
    bench = pd.DataFrame({"Close": bench_close, "Volume": vol})

    f = compute_market_features(hist, bench)
    assert f["return_3m"] > 0
    assert f["relative_return_3m"] > 0
    assert -0.05 < f["distance_from_52w_high"] <= 0
