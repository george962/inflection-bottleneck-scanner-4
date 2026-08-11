from __future__ import annotations

import math

import pandas as pd


def _f(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _ret(close, days):
    if len(close) <= days:
        return None
    old = _f(close.iloc[-days - 1])
    new = _f(close.iloc[-1])
    return None if old in (None, 0) or new is None else new / old - 1


def _prior(close, recent, prior):
    if len(close) < recent + prior + 1:
        return None
    end = _f(close.iloc[-recent - 1])
    start = _f(close.iloc[-recent - prior - 1])
    return None if end is None or start in (None, 0) else end / start - 1


def _peak(value, lo, ideal, hi):
    if value is None or value <= lo or value >= hi:
        return 0.0
    return 100 * (value - lo) / (ideal - lo) if value <= ideal else 100 * (hi - value) / (hi - ideal)


def _lin(value, bad, good):
    if value is None:
        return 0.0
    return max(0, min(100, 100 * (value - bad) / (good - bad)))


def compute_price_discovery_features(df):
    if df is None or df.empty or "Close" not in df:
        return {}
    close = df["Close"].dropna().astype(float)
    volume = df["Volume"].dropna().astype(float) if "Volume" in df else pd.Series(dtype=float)
    if len(close) < 80:
        return {}

    price = _f(close.iloc[-1])
    r1, r3, r6, r12 = _ret(close, 21), _ret(close, 63), _ret(close, 126), _ret(close, 252)
    p1, p3 = _prior(close, 21, 21), _prior(close, 63, 63)
    high = _f(close.tail(min(252, len(close))).max())
    dist = price / high - 1 if price is not None and high not in (None, 0) else None

    dv20 = volume_ratio = None
    if len(volume) >= 25:
        aligned = pd.DataFrame({"close": close, "volume": volume}).dropna()
        if len(aligned) >= 25:
            dv20 = _f((aligned["close"].tail(20) * aligned["volume"].tail(20)).mean())
            recent_vol = _f(aligned["volume"].tail(5).mean())
            prior_vol = _f(aligned["volume"].iloc[-25:-5].mean())
            if recent_vol is not None and prior_vol not in (None, 0):
                volume_ratio = recent_vol / prior_vol

    ma50 = _f(close.tail(50).mean()) if len(close) >= 50 else None
    above_ma50 = price / ma50 - 1 if price is not None and ma50 not in (None, 0) else None
    accel1 = r1 - p1 if r1 is not None and p1 is not None else None
    accel3 = r3 - p3 if r3 is not None and p3 is not None else None

    maturity = 0.45 * _lin(r6, 0.35, 1.0) + 0.45 * _lin(r12, 0.55, 1.6) + 0.10 * _lin(dist, -0.03, 0.02)
    if (r6 is not None and r6 >= 0.8) or (r12 is not None and r12 >= 1.1):
        maturity = max(maturity, 80)
    elif (r6 is not None and r6 >= 0.5) or (r12 is not None and r12 >= 0.7):
        maturity = max(maturity, 50)

    early = (
        0.28 * _peak(r3, -0.05, 0.18, 0.70)
        + 0.22 * _lin(accel1, -0.08, 0.20)
        + 0.18 * _peak(dist, -0.30, -0.06, 0.03)
        + 0.17 * _lin(volume_ratio, 0.80, 1.80)
        + 0.15 * _peak(r6, -0.10, 0.30, 1.0)
    )
    recovery = (
        0.30 * _peak(r12, -0.65, -0.05, 0.45)
        + 0.25 * _peak(r3, -0.08, 0.16, 0.50)
        + 0.20 * _lin(accel1, -0.08, 0.18)
        + 0.15 * _lin(above_ma50, -0.12, 0.12)
        + 0.10 * _lin(volume_ratio, 0.80, 1.70)
    )
    quiet = (
        0.30 * _peak(r3, -0.10, 0.08, 0.32)
        + 0.25 * _lin(volume_ratio, 0.90, 2.0)
        + 0.20 * _lin(accel1, -0.10, 0.16)
        + 0.15 * _peak(dist, -0.40, -0.12, 0.02)
        + 0.10 * _peak(r6, -0.15, 0.18, 0.65)
    )
    mature = (
        0.35 * _lin(r3, 0, 0.45)
        + 0.25 * _lin(volume_ratio, 0.80, 1.60)
        + 0.20 * _lin(accel1, -0.10, 0.15)
        + 0.20 * _lin(maturity, 45, 90)
    )

    stage = "LATE" if maturity >= 70 else "MID" if maturity >= 40 else "EARLY"
    buckets = {"EARLY_BREAKOUT": early, "RECOVERY": recovery, "QUIET_ACCUMULATION": quiet}
    if stage == "LATE":
        buckets["MATURE_CHALLENGER"] = mature
    bucket = max(buckets, key=buckets.get)
    best = max(buckets.values())
    seed = max(0, best - (0.12 * maturity if bucket != "MATURE_CHALLENGER" else 0))

    return {
        "price": price,
        "days_history": len(close),
        "dollar_volume_20d": dv20,
        "return_1m": r1,
        "return_3m": r3,
        "return_6m": r6,
        "return_12m": r12,
        "prior_return_1m": p1,
        "prior_return_3m": p3,
        "momentum_accel_1m": accel1,
        "momentum_accel_3m": accel3,
        "distance_from_52w_high": dist,
        "volume_ratio_5v20": volume_ratio,
        "above_ma50": above_ma50,
        "price_maturity_score": round(maturity, 2),
        "price_stage": stage,
        "discovery_bucket": bucket,
        "early_breakout_score": round(early, 2),
        "recovery_score": round(recovery, 2),
        "quiet_accumulation_score": round(quiet, 2),
        "mature_challenger_score": round(mature, 2),
        "discovery_seed_score": round(seed, 2),
    }


def select_deep_candidates(
    scan,
    min_price,
    min_dollar_volume_20d,
    min_history_days,
    deep_candidates,
    bucket_size,
    max_late_fraction=0.25,
    liquid_challenger_fraction=0.30,
):
    """Reserve part of deep research for highly liquid established-name proxies."""
    if scan.empty:
        return scan

    eligible = scan[
        (scan.price.fillna(0) >= min_price)
        & (scan.dollar_volume_20d.fillna(0) >= min_dollar_volume_20d)
        & (scan.days_history.fillna(0) >= min_history_days)
    ].copy()

    liquid_budget = max(1, int(deep_candidates * liquid_challenger_fraction))
    signal_budget = max(1, deep_candidates - liquid_budget)
    early_budget = max(1, int(signal_budget * (1 - max_late_fraction)))

    pieces = []
    for bucket in ["EARLY_BREAKOUT", "RECOVERY", "QUIET_ACCUMULATION"]:
        pieces.append(
            eligible[(eligible.discovery_bucket == bucket) & (eligible.price_stage != "LATE")]
            .sort_values("discovery_seed_score", ascending=False)
            .head(bucket_size)
        )

    early = (
        pd.concat(pieces, ignore_index=True)
        .drop_duplicates("ticker")
        .sort_values("discovery_seed_score", ascending=False)
        .head(early_budget)
    )

    late_budget = max(0, signal_budget - len(early))
    late_pool = eligible[eligible.price_stage == "LATE"].copy()
    sort_col = "mature_challenger_score" if "mature_challenger_score" in late_pool.columns else "discovery_seed_score"
    late = late_pool.sort_values([sort_col, "dollar_volume_20d"], ascending=[False, False]).head(late_budget)
    signal = pd.concat([early, late], ignore_index=True).drop_duplicates("ticker")

    liquid = (
        eligible[eligible.discovery_seed_score.fillna(0) >= 10]
        .sort_values(["dollar_volume_20d", "discovery_seed_score"], ascending=[False, False])
        .head(liquid_budget * 3)
    )
    liquid = liquid[~liquid.ticker.isin(signal.ticker)].head(liquid_budget)
    combined = pd.concat([signal, liquid], ignore_index=True).drop_duplicates("ticker")

    if len(combined) < deep_candidates:
        filler = (
            eligible[~eligible.ticker.isin(combined.ticker)]
            .sort_values(["discovery_seed_score", "dollar_volume_20d"], ascending=[False, False])
            .head(deep_candidates - len(combined))
        )
        combined = pd.concat([combined, filler], ignore_index=True)

    return combined.drop_duplicates("ticker").head(deep_candidates).reset_index(drop=True)
