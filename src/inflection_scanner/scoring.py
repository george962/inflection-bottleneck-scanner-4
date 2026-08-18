from __future__ import annotations

import math
from typing import Any


def finite(v: Any) -> float | None:
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception: return None

def clamp(x,lo=0.0,hi=100.0): return max(lo,min(hi,x))
def linear(v,bad,good,neutral=50.0):
    if v is None or good==bad:return neutral
    return clamp(100*(v-bad)/(good-bad))

def discovery_score(features: dict[str, Any]) -> dict[str, Any]:
    r3=finite(features.get("relative_return_3m")); r6=finite(features.get("relative_return_6m")); dd=finite(features.get("distance_from_52w_high")); dvol=finite(features.get("dollar_volume_20d")); r12=finite(features.get("return_12m"))
    momentum=(linear(r3,-.20,.25)+linear(r6,-.30,.40))/2
    liquidity=linear(math.log10(dvol) if dvol and dvol>0 else None,7.0,9.5)
    reset=linear(-dd if dd is not None else None,0.0,.35)
    overextension_penalty=max(0.0, linear(r12, .6, 2.5)-50) if r12 is not None else 0.0
    score=0.48*momentum+0.22*liquidity+0.30*reset-0.18*overextension_penalty
    return {"potential_score":round(clamp(score),2),"components":{"momentum":round(momentum,1),"liquidity":round(liquidity,1),"reset":round(reset,1),"overextension_penalty":round(overextension_penalty,1)}}
