from inflection_scanner.discovery import price_stage
from inflection_scanner.scoring import discovery_score


def test_late_stage_detected():
    out=price_stage({"return_6m":1.2,"return_12m":2.0,"distance_from_52w_high":-.02})
    assert out["price_stage"]=="LATE"


def test_discovery_score_is_bounded():
    s=discovery_score({"relative_return_3m":.2,"relative_return_6m":.3,"distance_from_52w_high":-.2,"dollar_volume_20d":1e9,"return_12m":.4})
    assert 0<=s["potential_score"]<=100
