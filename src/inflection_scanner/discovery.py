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
    return (
        100 * (value - lo) / (ideal - lo)
        if value <= ideal
        else 100 * (hi - value) / (hi - ideal)
    )


def _lin(value, bad, good):
    if value is None:
        return 0.0
    return max(0, min(100, 100 * (value - bad) / (good - bad)))


def compute_price_discovery_features(df):
    if df is None or df.empty or "Close" not in df:
        return {}

    close = df["Close"].dropna().astype(float)
    volume = (
        df["Volume"].dropna().astype(float)
        if "Volume" in df
        else pd.Series(dtype=float)
    )

    if len(close) < 80:
        return {}

    price = _f(close.iloc[-1])
    r1 = _ret(close, 21)
    r3 = _ret(close, 63)
    r6 = _ret(close, 126)
    r12 = _ret(close, 252)

    p1 = _prior(close, 21, 21)
    p3 = _prior(close, 63, 63)

    high = _f(close.tail(min(252, len(close))).max())
    dist = (
        price / high - 1
        if price is not None and high not in (None, 0)
        else None
    )

    dv20 = None
    volume_ratio = None

    if len(volume) >= 25:
        aligned = pd.DataFrame(
            {
                "close": close,
                "volume": volume,
            }
        ).dropna()

        if len(aligned) >= 25:
            dv20 = _f(
                (
                    aligned["close"].tail(20)
                    * aligned["volume"].tail(20)
                ).mean()
            )

            recent_vol = _f(aligned["volume"].tail(5).mean())
            prior_vol = _f(aligned["volume"].iloc[-25:-5].mean())

            if recent_vol is not None and prior_vol not in (None, 0):
                volume_ratio = recent_vol / prior_vol

    ma50 = _f(close.tail(50).mean()) if len(close) >= 50 else None
    above_ma50 = (
        price / ma50 - 1
        if price is not None and ma50 not in (None, 0)
        else None
    )

    accel1 = r1 - p1 if r1 is not None and p1 is not None else None
    accel3 = r3 - p3 if r3 is not None and p3 is not None else None

    maturity = (
        0.45 * _lin(r6, 0.35, 1.0)
        + 0.45 * _lin(r12, 0.55, 1.6)
        + 0.10 * _lin(dist, -0.03, 0.02)
    )

    if (r6 is not None and r6 >= 0.8) or (
        r12 is not None and r12 >= 1.1
    ):
        maturity = max(maturity, 80)
    elif (r6 is not None and r6 >= 0.5) or (
        r12 is not None and r12 >= 0.7
    ):
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

    stage = (
        "LATE"
        if maturity >= 70
        else "MID"
        if maturity >= 40
        else "EARLY"
    )

    buckets = {
        "EARLY_BREAKOUT": early,
        "RECOVERY": recovery,
        "QUIET_ACCUMULATION": quiet,
    }

    if stage == "LATE":
        buckets["MATURE_CHALLENGER"] = mature

    bucket = max(buckets, key=buckets.get)
    best = max(buckets.values())

    seed = max(
        0,
        best
        - (
            0.12 * maturity
            if bucket != "MATURE_CHALLENGER"
            else 0
        ),
    )

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
    """
    Select deep-research candidates while enforcing one GLOBAL late-stage cap.

    The liquid-challenger sleeve exists so large/high-liquidity companies can
    reach deep research even if their early-discovery score is only moderate.
    However, those liquid candidates do NOT get to bypass max_late_fraction.

    Example:
        deep_candidates=20 and max_late_fraction=0.25
        => at most 5 total LATE names, regardless of which sleeve selected them.
    """
    if scan.empty:
        return scan

    eligible = scan[
        (scan.price.fillna(0) >= min_price)
        & (
            scan.dollar_volume_20d.fillna(0)
            >= min_dollar_volume_20d
        )
        & (
            scan.days_history.fillna(0)
            >= min_history_days
        )
    ].copy()

    if eligible.empty:
        return eligible.reset_index(drop=True)

    deep_candidates = max(1, int(deep_candidates))

    late_cap = max(
        0,
        min(
            deep_candidates,
            int(deep_candidates * max_late_fraction),
        ),
    )

    liquid_budget = max(
        1,
        min(
            deep_candidates,
            int(deep_candidates * liquid_challenger_fraction),
        ),
    )

    signal_budget = max(0, deep_candidates - liquid_budget)

    # Allocate only part of the GLOBAL late allowance to the signal sleeve.
    # Any unused late capacity remains available to high-liquidity challengers.
    signal_late_budget = min(
        late_cap,
        int(signal_budget * max_late_fraction),
    )
    signal_nonlate_budget = max(
        0,
        signal_budget - signal_late_budget,
    )

    pieces = []

    for bucket in [
        "EARLY_BREAKOUT",
        "RECOVERY",
        "QUIET_ACCUMULATION",
    ]:
        pieces.append(
            eligible[
                (eligible.discovery_bucket == bucket)
                & (eligible.price_stage != "LATE")
            ]
            .sort_values(
                [
                    "discovery_seed_score",
                    "dollar_volume_20d",
                ],
                ascending=[False, False],
            )
            .head(bucket_size)
        )

    if pieces:
        nonlate_signal_pool = (
            pd.concat(pieces, ignore_index=True)
            .drop_duplicates("ticker")
            .sort_values(
                [
                    "discovery_seed_score",
                    "dollar_volume_20d",
                ],
                ascending=[False, False],
            )
        )
    else:
        nonlate_signal_pool = eligible.iloc[0:0].copy()

    nonlate_signal = nonlate_signal_pool.head(
        signal_nonlate_budget
    )

    late_pool = eligible[
        eligible.price_stage == "LATE"
    ].copy()

    late_sort_col = (
        "mature_challenger_score"
        if "mature_challenger_score" in late_pool.columns
        else "discovery_seed_score"
    )

    late_signal = (
        late_pool.sort_values(
            [
                late_sort_col,
                "dollar_volume_20d",
            ],
            ascending=[False, False],
        )
        .head(signal_late_budget)
    )

    selected_rows = []
    seen = set()
    late_count = 0

    def add_rows(frame, max_to_add=None):
        nonlocal late_count

        added = 0

        for _, row in frame.iterrows():
            ticker = row["ticker"]

            if ticker in seen:
                continue

            is_late = row["price_stage"] == "LATE"

            if is_late and late_count >= late_cap:
                continue

            selected_rows.append(row.to_dict())
            seen.add(ticker)

            if is_late:
                late_count += 1

            added += 1

            if max_to_add is not None and added >= max_to_add:
                break

            if len(selected_rows) >= deep_candidates:
                break

        return added

    add_rows(nonlate_signal)
    add_rows(late_signal)

    # High-liquidity challenger sleeve.
    # It may include EARLY, MID, or LATE names, but LATE names still consume
    # the same global late_cap.
    liquid_pool = (
        eligible[
            eligible.discovery_seed_score.fillna(0) >= 10
        ]
        .sort_values(
            [
                "dollar_volume_20d",
                "discovery_seed_score",
            ],
            ascending=[False, False],
        )
    )

    add_rows(
        liquid_pool,
        max_to_add=liquid_budget,
    )

    # Fill any remaining slots with the strongest remaining candidates.
    # Again, the global late cap is enforced here.
    filler_pool = (
        eligible.sort_values(
            [
                "discovery_seed_score",
                "dollar_volume_20d",
            ],
            ascending=[False, False],
        )
    )

    add_rows(
        filler_pool,
        max_to_add=deep_candidates - len(selected_rows),
    )

    # If the late cap prevented us from filling all slots, make one final pass
    # using NON-LATE candidates only.
    if len(selected_rows) < deep_candidates:
        nonlate_filler = (
            eligible[
                eligible.price_stage != "LATE"
            ]
            .sort_values(
                [
                    "discovery_seed_score",
                    "dollar_volume_20d",
                ],
                ascending=[False, False],
            )
        )

        add_rows(
            nonlate_filler,
            max_to_add=deep_candidates - len(selected_rows),
        )

    if not selected_rows:
        return eligible.iloc[0:0].reset_index(drop=True)

    return (
        pd.DataFrame(selected_rows)
        .head(deep_candidates)
        .reset_index(drop=True)
    )
