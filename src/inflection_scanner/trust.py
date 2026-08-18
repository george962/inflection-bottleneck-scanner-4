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


def _parse_first_trade(value: Any) -> datetime | None:
    if value is None:
        return None
    # Epoch seconds/milliseconds.
    try:
        x = float(value)
        if x > 10_000_000_000:
            x /= 1000.0
        if x > 0:
            return datetime.fromtimestamp(x, tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        pass
    # ISO/Yahoo datetime strings such as 2024-03-21 09:30:00-04:00.
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def years_public(profile: dict[str, Any], now: datetime | None = None) -> float | None:
    first = _parse_first_trade(profile.get("first_trade_date_epoch_utc"))
    if first is None:
        return None
    now = now or datetime.now(timezone.utc)
    if first > now:
        return None
    years = (now - first.astimezone(timezone.utc)).total_seconds() / (365.25 * 24 * 3600)
    return round(years, 2) if 0 <= years <= 200 else None


def analyst_count(snapshot: dict[str, Any]) -> int | None:
    value = finite(snapshot.get("features", {}).get("next_year_eps_analyst_count"))
    if value is None:
        value = finite(snapshot.get("profile", {}).get("analyst_count_info"))
    return int(value) if value is not None and value >= 0 else None


def pre_research_tier(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    profile, features = snapshot.get("profile", {}), snapshot.get("features", {})
    market_cap = finite(profile.get("market_cap")); yrs = years_public(profile); analysts = analyst_count(snapshot); dvol = finite(features.get("dollar_volume_20d"))
    core_cap = float(policy.get("core_min_market_cap", 15e9)); core_years = float(policy.get("core_min_years_public", 7)); core_analysts = int(policy.get("core_min_analysts", 10)); core_liq = float(policy.get("core_min_dollar_volume_20d", 50e6)); preferred_cap=float(policy.get("preferred_min_market_cap",25e9))
    mid_cap=float(policy.get("midcap_min_market_cap",7.5e9)); mid_years=float(policy.get("midcap_min_years_public",5)); mid_analysts=int(policy.get("midcap_min_analysts",7)); mid_liq=float(policy.get("midcap_min_dollar_volume_20d",25e6))

    core = bool(market_cap is not None and market_cap >= core_cap and dvol is not None and dvol >= core_liq and (yrs is None or yrs >= core_years) and (analysts is None or analysts >= core_analysts) and (yrs is not None or analysts is not None or market_cap >= preferred_cap))
    mid = bool(market_cap is not None and market_cap >= mid_cap and dvol is not None and dvol >= mid_liq and (yrs is None or yrs >= mid_years) and (analysts is None or analysts >= mid_analysts) and (yrs is not None or analysts is not None))
    tier = "CORE" if core else "MIDCAP" if mid else "SPECULATIVE"
    preferred = bool(core and market_cap is not None and market_cap >= preferred_cap)
    actionable = bool(preferred and analysts is not None and analysts >= core_analysts and ((yrs is not None and yrs >= core_years) or (market_cap is not None and market_cap >= max(50e9, preferred_cap*2))))
    if market_cap is None: size="UNKNOWN"
    elif market_cap >= 200e9: size="MEGA_CAP"
    elif market_cap >= preferred_cap: size="LARGE_CAP"
    elif market_cap >= 10e9: size="UPPER_MID_CAP"
    else: size="SMALLER"
    gaps=[]
    if yrs is None: gaps.append("public_history")
    if analysts is None: gaps.append("analyst_coverage")
    if market_cap is None: gaps.append("market_cap")
    if dvol is None: gaps.append("liquidity")
    return {"risk_tier":tier,"preferred_large_cap":preferred,"actionable_established":actionable,"size_class":size,"eligible":tier in {"CORE","MIDCAP"} or bool(policy.get("include_speculative",False)),"market_cap":market_cap,"years_public":yrs,"analyst_count":analysts,"dollar_volume_20d":dvol,"establishment_data_complete":not gaps,"establishment_data_gaps":gaps}


def _relative_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a == 0 or b == 0: return None
    return abs(a-b)/max(abs(a),abs(b))


def evaluate_trust(snapshot, valuation, filings, freshness, policy, thresholds, evidence_status=None):
    profile=snapshot.get("profile",{}); features=snapshot.get("features",{}); tier=pre_research_tier(snapshot,policy); quality=finite(snapshot.get("data_quality")) or finite(features.get("data_quality")) or 0.0
    score=100.0; warnings=[]; critical=[]; checks=[]
    def check(name,status,detail,penalty=0.0,critical_fail=False):
        nonlocal score
        checks.append({"check":name,"status":status,"detail":detail})
        if status in {"FAIL","WARN"}:
            score-=penalty
            (critical if critical_fail and status=="FAIL" else warnings).append(detail)
    if tier["risk_tier"]=="CORE": check("Size / liquidity gate","PASS",f"CORE thresholds pass. Size class {tier['size_class']}.")
    elif tier["risk_tier"]=="MIDCAP": check("Size / liquidity gate","WARN","Researchable company, but below default CORE policy.",12)
    else: check("Size / liquidity gate","FAIL","Company is below the default large-established research policy.",30)
    yrs=tier.get("years_public"); analysts=tier.get("analyst_count"); cy=float(policy.get("core_min_years_public",7)); ca=int(policy.get("core_min_analysts",10))
    if yrs is None: check("Public-history metadata","WARN","First-trade date is unavailable or unparseable.",5)
    elif yrs>=cy: check("Public-history metadata","PASS",f"Approximately {yrs:.1f} years public verified.")
    else: check("Public-history metadata","FAIL",f"Only about {yrs:.1f} years public; below the {cy:.0f}-year CORE preference.",12)
    if analysts is None: check("Analyst coverage","WARN","Analyst-count metadata is unavailable.",7)
    elif analysts>=ca: check("Analyst coverage","PASS",f"Approximately {analysts} analysts cover forward earnings.")
    else: check("Analyst coverage","WARN",f"Only about {analysts} analysts detected; below the {ca} analyst preference.",8)
    if quality>=82: check("Feature coverage","PASS",f"Data quality {quality:.0f}%.")
    elif quality>=72: check("Feature coverage","WARN",f"Data quality is only {quality:.0f}%.",8)
    else: check("Feature coverage","FAIL",f"Data quality is only {quality:.0f}%.",20,True)

    norm=valuation.get("security_normalization") or {}
    if norm and not norm.get("resolved",False):
        check("Currency / security units","FAIL",str(norm.get("reason") or "Currency/security-unit normalization unresolved."),25,True)
    elif norm:
        check("Currency / security units","PASS",f"{norm.get('financial_currency')}→{norm.get('trading_currency')} and share units reconciled.")

    filing_count=len(filings or [])
    check("Optional SEC enrichment","PASS" if filing_count else "INFO",f"{filing_count} SEC filing document(s) available." if filing_count else "SEC filing enrichment unavailable/disabled; no trust penalty.")
    market_price=finite(features.get("price")); info_price=finite(profile.get("current_price_info")); fast_price=finite(profile.get("fast_last_price")); max_diff=float(thresholds.get("max_price_source_mismatch",0.12))
    n=0
    for label,other in [("Yahoo info",info_price),("Yahoo fast-info",fast_price)]:
        diff=_relative_diff(market_price,other)
        if diff is not None:
            n+=1
            if diff>max_diff: check("Price cross-check","FAIL",f"Stored market price and {label} price differ by {diff:.1%}.",25,True)
    if n and not any(x["check"]=="Price cross-check" and x["status"]=="FAIL" for x in checks): check("Price cross-check","PASS",f"Current price agrees with {n} independent Yahoo price field(s).")
    shares=finite(profile.get("shares_outstanding")); mc=tier.get("market_cap")
    if mc and shares and market_price:
        implied=mc/shares; diff=_relative_diff(implied,market_price)
        if diff is not None and diff>float(thresholds.get("max_market_cap_price_mismatch",0.25)): check("Market-cap/share check","FAIL",f"Market cap ÷ shares implies ${implied:.2f}, but stored price is ${market_price:.2f}; mismatch {diff:.1%}.",25,True)
        else: check("Market-cap/share check","PASS","Market cap, shares, and price are internally consistent.")
    if valuation.get("valuation_resolved"): check("Valuation triangulation","PASS",f"{valuation.get('model_count',0)} valuation methods pass the agreement gate; agreement={valuation.get('model_agreement')}.")
    elif int(valuation.get("model_count") or 0)>=2: check("Valuation triangulation","WARN",f"Valuation methods disagree or fail sanity gates (agreement={valuation.get('model_agreement')}).",8)
    else: check("Valuation triangulation","WARN",f"Only {valuation.get('model_count',0)} independent valuation method(s) are usable.",12)
    warnings.extend(str(x) for x in valuation.get("warning_flags",[])); critical.extend(str(x) for x in valuation.get("critical_flags",[])); score-=25*len(valuation.get("critical_flags",[]))
    score=max(0.0,min(100.0,score)); grade="D" if critical else "A" if score>=90 else "B" if score>=80 else "C" if score>=68 else "D"
    return {**tier,"trust_score":round(score,1),"trust_grade":grade,"critical_flags":list(dict.fromkeys(critical)),"warnings":list(dict.fromkeys(warnings)),"checks":checks,"filing_count":filing_count,"evidence_status":str((evidence_status or {}).get("state") or "UNKNOWN"),"evidence_ready":bool(quality>=72 and not critical),"sec_optional":True,"sec_enrichment_available":filing_count>0,"model_count":int(valuation.get("model_count") or 0),"model_agreement":valuation.get("model_agreement")}
