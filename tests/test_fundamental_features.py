import pandas as pd

from inflection_scanner.features.fundamentals import compute_fundamental_features


def test_fundamental_acceleration_and_operating_leverage():
    cols = pd.to_datetime(
        ["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31"]
    )
    income = pd.DataFrame(
        {
            cols[0]: [150, 75, 40, 30],
            cols[1]: [130, 60, 28, 20],
            cols[2]: [120, 52, 22, 15],
            cols[3]: [115, 48, 18, 12],
            cols[4]: [100, 40, 10, 7],
            cols[5]: [100, 40, 10, 7],
        },
        index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"],
    )

    f = compute_fundamental_features(income)
    assert f["revenue_yoy"] == 0.5
    assert f["revenue_acceleration"] is not None
    assert f["gross_margin_change_yoy"] > 0
    assert f["operating_margin_change_yoy"] > 0
    assert f["incremental_operating_margin_yoy"] > 0.5
