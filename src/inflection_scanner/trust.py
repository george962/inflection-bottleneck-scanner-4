from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


def finite(value: Any) -> float | None:
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def years_public(profile: dict[str, Any]) -> float | None:
    ts = finite(profile.get("first_trade_date_epoch_utc"))
    if ts is None or ts <= 0:
        return None
    if ts > 10_000_000_000:
        ts /= 1000.0
    try:
        first = datetime.fromtimestamp(ts, tz=timezone.utc)
        years = (datetime.now(timezone.utc) - first).total_seconds() / (365.25 * 24 * 3600)
        if years < 0 or years > 200:
            return None
        return round(years, 2)
    except Exception:
        return None


def analyst_count(snapshot: dict[str, Any]) -> int | None:
    value = finite(snapshot.get("features", {}).get("next_year_eps_analyst_count"))
    if value is None:
        value = finite(snapshot.get("profile", {}).get("analyst_count_info"))
    return int(value) if value is not None and value >= 0 else None


def pre_research_tier(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    profile = snapshot.get("profile", {})
    features = snapshot.get("features", {})
    market_cap = finite(profile.get("market_cap"))
    yrs = years_public(profile)
    analysts = analyst_count(snapshot)
    dollar_volume = finite(features.get("dollar_volume_20d"))

    core_cap = float(policy.get("core_min_market_cap", 15_000_000_000))
    core_years = float(policy.get("core_min_years_public", 7))
    core_analysts = int(policy.get("core_min_analysts", 10))
    core_liquidity = float(policy.get("core_min_dollar_volume_20d", 50_000_000))
    preferred_cap = float(policy.get("preferred_min_market_cap", 25_000_000_000))

    mid_cap = float(policy.get("midcap_min_market_cap", 7_500_000_000))
    mid_years = float(policy.get("midcap_min_years_public", 5))
    mid_analysts = int(policy.get("midcap_min_analysts", 7))
    mid_liquidity = float(policy.get("midcap_min_dollar_volume_20d", 25_000_000))

    core_history_ok = yrs is None or yrs >= core_years
    core_coverage_ok = analysts is None or analysts >= core_analysts
    mid_history_ok = yrs is None or yrs >= mid_years
    mid_coverage_ok = analysts is None or analysts >= mid_analysts

    core_metadata_support = yrs is not None or analysts is not None or (
        market_cap is not None and market_cap >= preferred_cap
    )
    core = (
        market_cap is not None
        and market_cap >= core_cap
        and dollar_volume is not None
        and dollar_volume >= core_liquidity
        and core_history_ok
        and core_coverage_ok
        and core_metadata_support
    )

    mid_metadata_support = yrs is not None or analysts is not None
    midcap = (
        market_cap is not None
        and market_cap >= mid_cap
        and dollar_volume is not None
        and dollar_volume >= mid_liquidity
        and mid_history_ok
        and mid_coverage_ok
        and mid_metadata_support
    )

    tier = "CORE" if core else "MIDCAP" if midcap else "SPECULATIVE"
    preferred = bool(core and market_cap is not None and market_cap >= preferred_cap)
    actionable_established = bool(
        preferred
        and analysts is not None
        and analysts >= core_analysts
        and (
            (yrs is not None and yrs >= core_years)
            or (market_cap is not None and market_cap >= max(50_000_000_000, preferred_cap * 2))
        )
    )

    if market_cap is None:
        size_class = "UNKNOWN"
    elif market_cap >= 200_000_000_000:
        size_class = "MEGA_CAP"
    elif market_cap >= preferred_cap:
        size_class = "LARGE_CAP"
    elif market_cap >= 10_000_000_000:
        size_class = "UPPER_MID_CAP"
    else:
        size_class = "SMALLER"

    data_gaps = []
    if yrs is None:
        data_gaps.append("public_history")
    if analysts is None:
        data_gaps.append("analyst_coverage")
    if market_cap is None:
        data_gaps.append("market_cap")
    if dollar_volume is None:
        data_gaps.append("liquidity")

    return {
        "risk_tier": tier,
        "preferred_large_cap": preferred,
        "actionable_established": actionable_established,
        "size_class": size_class,
        "eligible": tier in {"CORE", "MIDCAP"} or bool(policy.get("include_speculative", False)),
        "market_cap": market_cap,
        "years_public": yrs,
        "analyst_count": analysts,
        "dollar_volume_20d": dollar_volume,
        "establishment_data_complete": not data_gaps,
        "establishment_data_gaps": data_gaps,
    }


def _relative_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a == 0 or b == 0:
        return None
    return abs(a - b) / max(abs(a), abs(b))


def evaluate_trust(
    snapshot: dict[str, Any],
    valuation: dict[str, Any],
    filings: list[dict[str, Any]],
    freshness: dict[str, Any],
    policy: dict[str, Any],
    thresholds: dict[str, Any],
    evidence_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = snapshot.get("profile", {})
    features = snapshot.get("features", {})
    tier = pre_research_tier(snapshot, policy)
    market_cap = tier["market_cap"]
    quality = finite(snapshot.get("data_quality")) or 0.0
    evidence_status = evidence_status or {}
    evidence_state = str(evidence_status.get("state") or "UNKNOWN")

    score = 100.0
    warnings: list[str] = []
    critical: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(name: str, status: str, detail: str, penalty: float = 0.0, critical_fail: bool = False):
        nonlocal score
        checks.append({"check": name, "status": status, "detail": detail})
        if status == "FAIL":
            score -= penalty
            (critical if critical_fail else warnings).append(detail)
        elif status == "WARN":
            score -= penalty
            warnings.append(detail)

    if tier["risk_tier"] == "CORE":
        check("Size / liquidity gate", "PASS", f"CORE thresholds pass. Size class {tier['size_class']}.")
    elif tier["risk_tier"] == "MIDCAP":
        check(
            "Size / liquidity gate",
            "WARN",
            "Researchable company, but below the default CORE size/liquidity threshold.",
            12,
        )
    else:
        check(
            "Size / liquidity gate",
            "FAIL",
            "Company is below the default large-established research policy.",
            30,
        )

    core_years = float(policy.get("core_min_years_public", 7))
    core_analysts = int(policy.get("core_min_analysts", 10))
    yrs = tier.get("years_public")
    analysts = tier.get("analyst_count")
    if yrs is None:
        check(
            "Public-history metadata",
            "WARN",
            "Yahoo did not provide a reliable first-trade date. Missing metadata is not treated as proof the company is new.",
            5,
        )
    elif yrs >= core_years:
        check("Public-history metadata", "PASS", f"Approximately {yrs:.1f} years public verified.")
    else:
        check("Public-history metadata", "FAIL", f"Only about {yrs:.1f} years public; below the {core_years:.0f}-year CORE preference.", 12)

    if analysts is None:
        check("Analyst coverage", "WARN", "Analyst-count metadata is unavailable.", 7)
    elif analysts >= core_analysts:
        check("Analyst coverage", "PASS", f"Approximately {analysts} analysts cover forward earnings/company profile.")
    else:
        check("Analyst coverage", "WARN", f"Only about {analysts} analysts detected; below the {core_analysts} analyst CORE preference.", 8)

    if quality >= 82:
        check("Feature coverage", "PASS", f"Data quality {quality:.0f}%.")
    elif quality >= 72:
        check("Feature coverage", "WARN", f"Data quality is only {quality:.0f}%.", 8)
    else:
        check("Feature coverage", "FAIL", f"Data quality is only {quality:.0f}%.", 20, True)

    filing_count = len(filings)
    min_filings = int(thresholds.get("min_sec_filings_for_buy", 2))
    evidence_ready = bool(
        filing_count >= min_filings
        and evidence_state in {"READY", "PARTIAL_ERROR", "CACHED_ONLY", "UNKNOWN"}
    )
    if evidence_ready:
        if evidence_state == "PARTIAL_ERROR":
            check(
                "SEC evidence",
                "WARN",
                f"{filing_count} recent SEC filings are cached, but some additional downloads failed.",
                4,
            )
        else:
            check("SEC evidence", "PASS", f"{filing_count} recent SEC filing documents cached.")
    else:
        errors = evidence_status.get("errors", []) or []
        suffix = f" Error: {errors[0]}" if errors else ""
        check(
            "SEC evidence",
            "FAIL",
            f"Only {filing_count} usable SEC filing documents are available; {min_filings} required for actionable research.{suffix}",
            15,
        )

    market_price = finite(features.get("price"))
    info_price = finite(profile.get("current_price_info"))
    fast_price = finite(profile.get("fast_last_price"))
    max_price_diff = float(thresholds.get("max_price_source_mismatch", 0.12))
    price_cross_checks = 0
    for label, other in [("Yahoo info", info_price), ("Yahoo fast-info", fast_price)]:
        diff = _relative_diff(market_price, other)
        if diff is not None:
            price_cross_checks += 1
            if diff > max_price_diff:
                check("Price cross-check", "FAIL", f"Stored market price and {label} price differ by {diff:.1%}.", 25, True)
    if price_cross_checks and not any(x["check"] == "Price cross-check" and x["status"] == "FAIL" for x in checks):
        check("Price cross-check", "PASS", f"Current price agrees with {price_cross_checks} independent Yahoo price field(s).")

    shares = finite(profile.get("shares_outstanding"))
    if market_cap is not None and shares is not None and shares > 0 and market_price is not None:
        implied_price = market_cap / shares
        diff = _relative_diff(implied_price, market_price)
        max_cap_diff = float(thresholds.get("max_market_cap_price_mismatch", 0.25))
        if diff is not None and diff > max_cap_diff:
            check(
                "Market-cap/share check",
                "FAIL",
                f"Market cap ÷ shares implies ${implied_price:.2f}, but stored price is ${market_price:.2f}; mismatch {diff:.1%}.",
                25,
                True,
            )
        else:
            check("Market-cap/share check", "PASS", "Market cap, shares, and price are internally consistent.")

    fast_mc = finite(profile.get("fast_market_cap"))
    mc_diff = _relative_diff(market_cap, fast_mc)
    if mc_diff is not None and mc_diff > 0.30:
        check("Market-cap cross-check", "FAIL", f"Profile and fast-info market caps differ by {mc_diff:.1%}.", 20, True)

    model_count = int(valuation.get("model_count") or 0)
    model_agreement = finite(valuation.get("model_agreement"))
    if valuation.get("valuation_resolved"):
        check(
            "Valuation triangulation",
            "PASS",
            f"{model_count} valuation methods pass the agreement gate; agreement={model_agreement}.",
        )
    elif model_count >= 2:
        check(
            "Valuation triangulation",
            "WARN",
            f"{model_count} methods exist but disagree too much to create an actionable buy zone (agreement={model_agreement}).",
            8,
        )
    else:
        check(
            "Valuation triangulation",
            "WARN",
            f"Only {model_count} independent valuation method(s) are usable.",
            12,
        )

    warnings.extend(str(x) for x in valuation.get("warning_flags", []))
    for flag in valuation.get("critical_flags", []):
        critical.append(str(flag))
        score -= 25

    for source, meta in freshness.items():
        if not isinstance(meta, dict):
            continue
        if not meta.get("present"):
            # SEC absence is already represented by evidence_status. Avoid double punishment.
            if source != "sec_submissions":
                warnings.append(f"{source} cache object is missing.")
        elif meta.get("stale"):
            score -= 4
            warnings.append(f"{source} cache is stale ({meta.get('age_hours')} hours old).")

    score = max(0.0, min(100.0, score))
    grade = "D" if critical else "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 68 else "D"

    return {
        **tier,
        "trust_score": round(score, 1),
        "trust_grade": grade,
        "critical_flags": list(dict.fromkeys(critical)),
        "warnings": list(dict.fromkeys(warnings)),
        "checks": checks,
        "filing_count": filing_count,
        "evidence_status": evidence_state,
        "evidence_ready": evidence_ready,
        "sec_diagnostics": evidence_status,
        "model_count": model_count,
        "model_agreement": model_agreement,
    }
