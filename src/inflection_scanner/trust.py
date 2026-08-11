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
        return round(
            (datetime.now(timezone.utc) - first).total_seconds()
            / (365.25 * 24 * 3600),
            2,
        )
    except Exception:
        return None


def analyst_count(snapshot: dict[str, Any]) -> int | None:
    value = finite(snapshot.get("features", {}).get("next_year_eps_analyst_count"))
    return int(value) if value is not None else None


def pre_research_tier(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    profile = snapshot.get("profile", {})
    market_cap = finite(profile.get("market_cap"))
    yrs = years_public(profile)
    analysts = analyst_count(snapshot)

    core = (
        market_cap is not None
        and market_cap >= float(policy.get("core_min_market_cap", 10_000_000_000))
        and yrs is not None
        and yrs >= float(policy.get("core_min_years_public", 5))
        and analysts is not None
        and analysts >= int(policy.get("core_min_analysts", 8))
    )
    midcap = (
        market_cap is not None
        and market_cap >= float(policy.get("midcap_min_market_cap", 5_000_000_000))
        and yrs is not None
        and yrs >= float(policy.get("midcap_min_years_public", 3))
        and analysts is not None
        and analysts >= int(policy.get("midcap_min_analysts", 5))
    )

    tier = "CORE" if core else "MIDCAP" if midcap else "SPECULATIVE"
    eligible = tier in {"CORE", "MIDCAP"} or bool(policy.get("include_speculative", False))
    return {
        "risk_tier": tier,
        "eligible": eligible,
        "market_cap": market_cap,
        "years_public": yrs,
        "analyst_count": analysts,
    }


def _relative_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a == 0 or b == 0:
        return None
    return abs(a - b) / max(abs(a), abs(b))


def evaluate_trust(snapshot, valuation, filings, freshness, policy, thresholds):
    profile = snapshot.get("profile", {})
    features = snapshot.get("features", {})
    tier = pre_research_tier(snapshot, policy)
    market_cap = tier["market_cap"]
    quality = finite(snapshot.get("data_quality")) or 0.0

    score = 100.0
    warnings = []
    critical = []
    checks = []

    def add_check(name, status, detail, critical_if_fail=False, penalty=0):
        nonlocal score
        checks.append({"check": name, "status": status, "detail": detail})
        if status == "FAIL":
            score -= penalty
            if critical_if_fail:
                critical.append(detail)
            else:
                warnings.append(detail)

    if tier["risk_tier"] == "CORE":
        add_check("Company size / history", "PASS", "CORE established-company thresholds passed.")
    elif tier["risk_tier"] == "MIDCAP":
        score -= 10
        warnings.append("Company is established but below the default $10B CORE size threshold.")
        checks.append({"check": "Company size / history", "status": "WARN", "detail": "MIDCAP: researchable, but not a normal BUY by default."})
    else:
        score -= 30
        warnings.append("Company fails the default established-company size/history/analyst thresholds.")
        add_check("Company size / history", "FAIL", "SPECULATIVE company under the default policy.")

    if quality >= 80:
        add_check("Feature coverage", "PASS", f"Data quality {quality:.0f}%.")
    elif quality >= 70:
        score -= 8
        warnings.append(f"Feature coverage is only {quality:.0f}%.")
        checks.append({"check": "Feature coverage", "status": "WARN", "detail": f"Data quality {quality:.0f}%."})
    else:
        add_check("Feature coverage", "FAIL", f"Data quality is only {quality:.0f}%.", True, 20)

    filing_count = len(filings)
    min_filings = int(thresholds.get("min_sec_filings_for_buy", 2))
    if filing_count >= min_filings:
        add_check("SEC filings", "PASS", f"{filing_count} recent SEC documents cached.")
    else:
        add_check(
            "SEC filings",
            "FAIL",
            f"Only {filing_count} recent SEC filing documents available; {min_filings} required for a normal BUY.",
            False,
            15,
        )

    market_price = finite(features.get("price"))
    info_price = finite(profile.get("current_price_info"))
    fast_price = finite(profile.get("fast_last_price"))
    max_price_diff = float(thresholds.get("max_price_source_mismatch", 0.12))
    for label, other in [("Yahoo info price", info_price), ("Yahoo fast-info price", fast_price)]:
        diff = _relative_diff(market_price, other)
        if diff is not None and diff > max_price_diff:
            add_check("Price cross-check", "FAIL", f"Stored market price and {label} differ by {diff:.1%}.", True, 25)

    shares = finite(profile.get("shares_outstanding"))
    if market_cap is not None and shares is not None and shares > 0 and market_price is not None:
        implied_price = market_cap / shares
        diff = _relative_diff(implied_price, market_price)
        max_cap_diff = float(thresholds.get("max_market_cap_price_mismatch", 0.25))
        if diff is not None and diff > max_cap_diff:
            add_check(
                "Market-cap/share check",
                "FAIL",
                f"Market cap ÷ shares implies ${implied_price:.2f}, but stored price is ${market_price:.2f}; mismatch {diff:.1%}.",
                True,
                25,
            )
        else:
            add_check("Market-cap/share check", "PASS", "Market cap, shares, and price are internally consistent.")

    fast_mc = finite(profile.get("fast_market_cap"))
    diff_mc = _relative_diff(market_cap, fast_mc)
    if diff_mc is not None and diff_mc > 0.30:
        add_check("Market-cap cross-check", "FAIL", f"Profile and fast-info market caps differ by {diff_mc:.1%}.", True, 20)

    model_count = int(valuation.get("model_count") or 0)
    model_agreement = finite(valuation.get("model_agreement"))
    min_models = int(thresholds.get("min_valuation_models_for_buy", 2))
    min_agreement = float(thresholds.get("min_model_agreement_for_buy", 0.55))

    if model_count >= min_models:
        add_check("Valuation corroboration", "PASS", f"{model_count} independent valuation methods available.")
    else:
        score -= 18
        warnings.append(f"Only {model_count} usable valuation method(s); a single model cannot support a normal BUY.")
        checks.append({"check": "Valuation corroboration", "status": "WARN", "detail": f"{model_count} valuation model(s)."})

    if model_agreement is not None:
        if model_agreement >= min_agreement:
            add_check("Valuation agreement", "PASS", f"Model agreement {model_agreement:.2f}.")
        else:
            score -= 12
            warnings.append(f"Valuation methods disagree materially (agreement {model_agreement:.2f}).")
            checks.append({"check": "Valuation agreement", "status": "WARN", "detail": f"Agreement {model_agreement:.2f}."})

    warnings.extend(str(x) for x in valuation.get("warning_flags", []))
    for flag in valuation.get("critical_flags", []):
        critical.append(str(flag))
        score -= 25

    for source, meta in freshness.items():
        if not isinstance(meta, dict):
            continue
        if not meta.get("present"):
            warnings.append(f"{source} cache object is missing.")
        elif meta.get("stale"):
            score -= 5
            warnings.append(f"{source} cache is stale ({meta.get('age_hours')} hours old).")

    score = max(0.0, min(100.0, score))
    grade = "D" if critical else "A" if score >= 88 else "B" if score >= 78 else "C" if score >= 65 else "D"
    return {
        **tier,
        "trust_score": round(score, 1),
        "trust_grade": grade,
        "critical_flags": list(dict.fromkeys(critical)),
        "warnings": list(dict.fromkeys(warnings)),
        "checks": checks,
        "filing_count": filing_count,
        "model_count": model_count,
        "model_agreement": model_agreement,
    }


def gate_decision(decision, trust, valuation, research_cfg):
    out = dict(decision)
    original = out.get("decision", "WATCH")
    thresholds = dict(research_cfg.get("trust_thresholds", {}))
    reasons = []

    if trust.get("critical_flags"):
        out["decision"] = "REVIEW DATA"
        reasons.append("Critical data/valuation sanity checks failed.")

    if out.get("decision") != "REVIEW DATA" and trust.get("risk_tier") == "SPECULATIVE":
        out["decision"] = "SPECULATIVE WATCH"
        reasons.append("Company does not meet the default established-company size/history policy.")

    if out.get("decision") == "BUY" and trust.get("risk_tier") != "CORE":
        out["decision"] = "WATCH"
        reasons.append("Normal BUY is reserved for CORE established companies by default.")

    min_trust = float(thresholds.get("buy_min_trust_score", 80))
    if out.get("decision") == "BUY" and float(trust.get("trust_score") or 0) < min_trust:
        out["decision"] = "WATCH"
        reasons.append(f"Trust score is below the {min_trust:.0f} BUY threshold.")

    min_models = int(thresholds.get("min_valuation_models_for_buy", 2))
    if out.get("decision") == "BUY" and int(valuation.get("model_count") or 0) < min_models:
        out["decision"] = "WATCH"
        reasons.append("BUY requires at least two usable valuation methods.")

    min_agreement = float(thresholds.get("min_model_agreement_for_buy", 0.55))
    agreement = finite(valuation.get("model_agreement"))
    if out.get("decision") == "BUY" and (agreement is None or agreement < min_agreement):
        out["decision"] = "WATCH"
        reasons.append("Valuation methods do not agree closely enough for BUY.")

    out["pre_trust_decision"] = original
    out["trust_gate_reasons"] = reasons
    out["evidence_confidence"] = "HIGH" if trust.get("trust_grade") == "A" else "MEDIUM" if trust.get("trust_grade") == "B" else "LOW"
    return out
