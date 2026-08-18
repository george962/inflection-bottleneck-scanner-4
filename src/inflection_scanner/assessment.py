from __future__ import annotations

from typing import Any


def _f(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _pct(value, digits=1) -> str:
    v = _f(value)
    return "n/a" if v is None else f"{v * 100:.{digits}f}%"


def _pp(value, digits=1) -> str:
    v = _f(value)
    return "n/a" if v is None else f"{v * 100:+.{digits}f} pp"


def compare_with_previous(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    if not previous:
        return {
            "previous_score": None,
            "score_delta_last": None,
            "component_deltas": {},
        }

    cs = current.get("scores", {})
    ps = previous.get("scores", {})

    def delta(key: str):
        a, b = _f(cs.get(key)), _f(ps.get(key))
        return round(a - b, 2) if a is not None and b is not None else None

    keys = [
        "fundamental",
        "revisions",
        "forward_growth",
        "valuation_upside",
        "operating_leverage",
        "expectation_gap",
        "early_discovery",
        "price_maturity",
    ]
    return {
        "previous_score": ps.get("total"),
        "score_delta_last": delta("total"),
        "component_deltas": {
            k: delta(k) for k in keys if delta(k) is not None
        },
    }


def build_assessment(
    snapshot: dict[str, Any],
    previous: dict[str, Any] | None,
    minimum_actionable_quality: float,
    watch_threshold: float,
    deep_research_threshold: float,
    candidate_threshold: float,
) -> dict[str, Any]:
    f = snapshot.get("features", {})
    s = snapshot.get("scores", {})
    p = snapshot.get("profile", {})
    quality = _f(snapshot.get("data_quality")) or 0.0
    potential = _f(s.get("total")) or 0.0
    maturity = _f(s.get("price_maturity")) or 0.0
    revisions = _f(s.get("revisions")) or 0.0
    forward_growth = _f(s.get("forward_growth")) or 0.0
    fundamental = _f(s.get("fundamental")) or 0.0
    gap = _f(s.get("expectation_gap")) or 0.0
    discovery = _f(s.get("early_discovery")) or 0.0

    change = compare_with_previous(snapshot, previous)

    if maturity >= 70:
        price_stage = "LATE"
    elif maturity >= 40:
        price_stage = "MID"
    else:
        price_stage = "EARLY"

    if quality < minimum_actionable_quality:
        action = "INSUFFICIENT DATA"
    elif maturity >= 72 and potential < candidate_threshold + 4:
        action = "DO NOT CHASE"
    elif potential >= candidate_threshold and price_stage != "LATE":
        action = "CANDIDATE"
    elif potential >= deep_research_threshold:
        action = "DEEP RESEARCH"
    elif potential >= watch_threshold:
        action = "WATCH"
    else:
        action = "PASS"

    if price_stage == "EARLY" and revisions >= 60 and fundamental >= 55:
        stage = "EARLY FUNDAMENTAL INFLECTION"
    elif price_stage == "EARLY" and revisions >= 65:
        stage = "ESTIMATES TURNING FIRST"
    elif price_stage == "EARLY" and discovery >= 60:
        stage = "EARLY PRICE DISCOVERY"
    elif price_stage == "MID" and gap >= 55:
        stage = "MID-STAGE / FUNDAMENTALS AHEAD"
    elif price_stage == "LATE":
        stage = "LATE / NEEDS EXCEPTIONAL GROWTH"
    else:
        stage = "MIXED"

    # Why discovered — specifically emphasize things not requiring the stock
    # to have already exploded.
    reasons: list[tuple[float, str]] = []

    bucket = f.get("discovery_bucket")
    if bucket:
        reasons.append((
            _f(f.get("discovery_seed_score")) or 0,
            f"Broad-universe price scan classified it as {bucket.replace('_', ' ').lower()} rather than starting from a hand-picked watchlist."
        ))

    accel = _f(f.get("revenue_acceleration"))
    if accel is not None and accel > 0:
        reasons.append((accel * 120, f"Revenue growth accelerated {_pp(accel)} versus the previous comparable-quarter growth rate."))

    eps30 = _f(f.get("eps_revision_30d"))
    if eps30 is not None and eps30 > 0:
        reasons.append((eps30 * 150, f"Forward EPS estimate increased {_pct(eps30)} over 30 days."))

    eps90 = _f(f.get("eps_revision_90d"))
    if eps90 is not None and eps90 > 0:
        reasons.append((eps90 * 100, f"Forward EPS estimate increased {_pct(eps90)} over 90 days."))

    ny_eps = _f(f.get("next_year_eps_growth"))
    if ny_eps is not None and ny_eps > 0:
        reasons.append((ny_eps * 60, f"Consensus next-year EPS growth is about {_pct(ny_eps)}."))

    ny_rev = _f(f.get("next_year_revenue_growth_estimate"))
    if ny_rev is not None and ny_rev > 0:
        reasons.append((ny_rev * 50, f"Consensus next-year revenue growth is about {_pct(ny_rev)}."))

    target_up = _f(s.get("analyst_target_upside"))
    if target_up is not None and target_up > 0:
        reasons.append((min(target_up, 0.60) * 35, f"Mean analyst target is about {_pct(target_up)} above the current price; this is supporting evidence, not the primary signal."))

    r12 = _f(f.get("return_12m"))
    r6 = _f(f.get("return_6m"))
    if price_stage == "EARLY":
        reasons.append((25, f"Price maturity is still EARLY: 6-month return {_pct(r6)} and 12-month return {_pct(r12)}."))

    reasons.sort(key=lambda x: x[0], reverse=True)
    why = [text for _, text in reasons[:6]]

    risks: list[str] = []
    if price_stage == "LATE":
        risks.append(
            f"Price is already late-stage: 6-month return {_pct(r6)}, 12-month return {_pct(r12)}. Strong fundamentals alone are not enough."
        )
    elif price_stage == "MID":
        risks.append("The stock has already partially rerated; further upside needs continued estimate and earnings growth.")

    fpe = _f(p.get("forward_pe"))
    if fpe is not None and fpe > 50:
        risks.append(f"Forward P/E is roughly {fpe:.1f}x.")
    if eps30 is not None and eps30 < 0:
        risks.append(f"30-day EPS revisions are negative at {_pct(eps30)}.")
    if accel is not None and accel < 0:
        risks.append(f"Revenue growth is decelerating by {_pp(accel)}.")
    if gap < 45:
        risks.append("Expectation-gap score is weak: the forward evidence may not be strong enough relative to the current price.")
    if quality < 80:
        risks.append(f"Data quality is {quality:.0f}%; confirm missing fields manually.")

    missing: list[str] = []
    if eps30 is None:
        missing.append("No reliable 30-day EPS revision signal.")
    if ny_eps is None:
        missing.append("No usable next-year EPS growth estimate.")
    if fpe is None:
        missing.append("Forward P/E unavailable.")
    if target_up is None:
        missing.append("Analyst target-price upside unavailable.")
    if accel is None:
        missing.append("Quarterly revenue acceleration unavailable.")

    triggers: list[str] = []
    if eps30 is None or eps30 <= 0:
        triggers.append("30-day EPS revisions turn positive.")
    if accel is None or accel <= 0:
        triggers.append("Next quarter confirms positive revenue-growth acceleration.")
    if price_stage == "EARLY":
        triggers.append("Price confirmation improves without price maturity moving into LATE territory.")
    if price_stage == "LATE":
        triggers.append("EPS/revenue estimates rise enough to make valuation cheaper despite the prior price run.")
    if potential >= deep_research_threshold:
        triggers.append("Potential score remains above the deep-research threshold on the next scan.")

    return {
        **change,
        "price_stage": price_stage,
        "stage": stage,
        "action": action,
        "why_discovered": why,
        "risk_flags": risks[:6],
        "missing_evidence": missing[:6],
        "next_triggers": triggers[:6],
    }
