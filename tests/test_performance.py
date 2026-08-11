from datetime import datetime, timedelta, timezone

import pandas as pd

from inflection_scanner.performance import build_track_record
from inflection_scanner.warehouse import ResearchWarehouse


def test_track_record_uses_realized_prices(tmp_path):
    warehouse = ResearchWarehouse(tmp_path / "warehouse.db")
    asof = datetime.now(timezone.utc) - timedelta(days=120)
    start_date = asof.date()
    end_date = (asof + timedelta(days=90)).date()

    prices = pd.DataFrame(
        {
            "Open": [100, 120],
            "High": [101, 121],
            "Low": [99, 119],
            "Close": [100, 120],
            "Volume": [1_000_000, 1_000_000],
        },
        index=pd.to_datetime([start_date.isoformat(), end_date.isoformat()]),
    )
    warehouse.upsert_prices("XYZ", prices)
    report = {
        "model_version": "5.2",
        "asof": asof.isoformat(timespec="seconds"),
        "ticker": "XYZ",
        "metrics": {"price": 100},
        "conviction": {"action": "BUY NOW"},
    }
    warehouse.put_research_report("XYZ", report["asof"], "BUY NOW", 0.2, report)
    track = build_track_record(warehouse, [90])
    warehouse.close()

    assert len(track["observations"]) == 1
    assert track["observations"][0]["realized_return"] == 0.2
