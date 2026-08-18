from __future__ import annotations

from typing import Any


def price_stage(features: dict[str, Any]) -> dict[str, Any]:
    r6=features.get("return_6m"); r12=features.get("return_12m"); high=features.get("distance_from_52w_high")
    vals=[x for x in [r6,r12] if isinstance(x,(int,float))]
    maturity=0.0
    if r6 is not None: maturity+=max(0,min(45,float(r6)*55))
    if r12 is not None: maturity+=max(0,min(45,float(r12)*28))
    if high is not None and float(high)>-.08: maturity+=10
    maturity=max(0.0,min(100.0,maturity))
    stage="EARLY" if maturity<35 else "MID" if maturity<70 else "LATE"
    bucket="QUIET_ACCUMULATION" if stage=="EARLY" else "CONFIRMED_INFLECTION" if stage=="MID" else "LATE_RERATING"
    return {"price_stage":stage,"price_maturity":round(maturity,2),"discovery_bucket":bucket}
