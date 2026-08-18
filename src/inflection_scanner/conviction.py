from __future__ import annotations

import math
from typing import Any


def finite(value: Any) -> float | None:
    try:
        x=float(value); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def clamp(v,lo=0.0,hi=100.0): return max(lo,min(hi,v))
def linear(value,bad,good,neutral=50.0):
    if value is None or good==bad: return neutral
    return clamp(100.0*(value-bad)/(good-bad))
def peaked(value,lo,ideal,hi,neutral=50.0):
    if value is None: return neutral
    if value<=lo or value>=hi:return 0.0
    return clamp(100*(value-lo)/(ideal-lo)) if value<=ideal else clamp(100*(hi-value)/(hi-ideal))
def average(values,default=50.0):
    clean=[float(x) for x in values if x is not None and math.isfinite(float(x))]; return sum(clean)/len(clean) if clean else default

def _fundamental(f): return average([linear(finite(f.get("revenue_acceleration")),-.10,.15),linear(finite(f.get("operating_margin_change_yoy")),-.05,.08),linear(finite(f.get("gross_margin_change_yoy")),-.04,.06),linear(finite(f.get("next_year_revenue_growth_estimate")),-.02,.25),linear(finite(f.get("next_year_eps_growth")),-.10,.40),linear(finite(f.get("free_cash_flow_margin_change_yoy")),-.05,.08)])
def _revisions(f): return average([linear(finite(f.get("eps_revision_30d")),-.05,.15),linear(finite(f.get("eps_revision_90d")),-.10,.25),linear(finite(f.get("revision_breadth_30d")),-.75,.75),linear(finite(f.get("eps_revision_acceleration")),-.08,.12),linear(finite(f.get("avg_eps_surprise_last4")),-.05,.15)])
def _valuation(v):
    if not v.get("valuation_resolved"): return average([linear(finite(v.get("model_agreement")),.20,.65),linear(float(v.get("model_count") or 0),1,3),20.0])
    return average([linear(finite(v.get("base_cagr")),.02,.25),linear(finite(v.get("expected_cagr")),.03,.28),linear(finite(v.get("bear_return")),-.55,.05),linear(finite(v.get("model_agreement")),.55,.85),linear(float(v.get("model_count") or 0),1,3)])
def _quality(t):
    mc=finite(t.get("market_cap")); size=50.0 if not mc else clamp(15+27*math.log10(max(mc,1)/1e9))
    return average([finite(t.get("trust_score")),size,linear(finite(t.get("years_public")),3,20),linear(finite(t.get("analyst_count")),5,25),linear(finite(t.get("dollar_volume_20d")),20e6,500e6)])
def _evidence(e,t): return average([linear(finite(t.get("trust_score")),65,95),linear(finite(t.get("analyst_count")),5,25),linear(finite(t.get("model_count")),1,3),linear(finite(t.get("model_agreement")),.40,.82)])

def build_entry_timing(snapshot,cfg):
    f=snapshot.get("features",{}); s=snapshot.get("scores",{}); maturity=finite(s.get("price_maturity")) or finite(f.get("price_maturity")) or 0.0
    r1,r3,r6,r12=[finite(f.get(k)) for k in ("return_1m","return_3m","return_6m","return_12m")]; dh=finite(f.get("distance_from_52w_high")); eps30=finite(f.get("eps_revision_30d"))
    late=float(cfg.get("late_maturity",78)); over6=float(cfg.get("overextended_return_6m",.70)); over12=float(cfg.get("overextended_return_12m",1.20)); reset_high=float(cfg.get("reset_distance_from_high",-.18)); reset1=float(cfg.get("reset_return_1m",-.12))
    over=bool(maturity>=late and ((r6 is not None and r6>=over6) or (r12 is not None and r12>=over12)))
    reset=bool(over and ((dh is not None and dh<=reset_high) or (r1 is not None and r1<=reset1))); secondary=bool(reset and eps30 is not None and eps30>=0)
    if over and not reset: state="PAST PRIMARY ENTRY / OVEREXTENDED"
    elif over and reset: state="RESETTING AFTER RERATING"
    elif maturity<=35: state="EARLY / BUILDING"
    elif maturity<=65: state="CONFIRMED / STILL ACTIONABLE"
    else: state="MATURE / WATCH ENTRY"
    score=average([linear(100-maturity,10,90),peaked(r6,-.25,.30,1.25),peaked(r12,-.40,.50,2.20),peaked(r3,-.20,.15,.70)])
    if secondary: score=max(score,58)
    if over and not reset: score=min(score,25)
    return {"entry_state":state,"entry_score":round(score,1),"overextended":over,"meaningful_reset":reset,"secondary_entry_ready":secondary,"distance_from_52w_high":dh,"return_1m":r1,"return_3m":r3,"return_6m":r6,"return_12m":r12,"price_maturity":round(maturity,1)}

def build_conviction(snapshot,valuation,trust,evidence_summary,cfg):
    f=snapshot.get("features",{}); price=finite(f.get("price")); horizon=int(valuation.get("horizon_years") or 3); required_base=float(cfg.get("required_base_cagr",.15)); required_expected=float(cfg.get("required_expected_cagr",.18)); min_bear=float(cfg.get("min_bear_return",-.30)); buy_min=float(cfg.get("buy_now_min_thesis_score",76)); pull_min=float(cfg.get("buy_on_pullback_min_thesis_score",72)); watch_min=float(cfg.get("watch_min_thesis_score",58)); max_premium=float(cfg.get("max_buy_zone_premium",.03)); max_gap=float(cfg.get("max_pullback_gap",.35))
    entry=build_entry_timing(snapshot,cfg.get("entry_timing",{})); scenarios={x.get("name"):x for x in valuation.get("scenarios",[])}; base_fair=finite((scenarios.get("Base") or {}).get("fair_value")) if valuation.get("valuation_resolved") else None
    buy_below=base_fair/((1+required_base)**horizon) if base_fair else None; gap=price/buy_below-1 if price and buy_below else None
    pillars={"fundamental_inflection":round(_fundamental(f),1),"estimate_revision":round(_revisions(f),1),"valuation":round(_valuation(valuation),1),"price_timing":entry["entry_score"],"company_quality":round(_quality(trust),1),"evidence":round(_evidence(evidence_summary,trust),1)}
    w=cfg.get("thesis_weights",{}) or {"fundamental_inflection":25,"estimate_revision":20,"valuation":25,"company_quality":20,"evidence":10}; keys=["fundamental_inflection","estimate_revision","valuation","company_quality","evidence"]; total=sum(float(w.get(k,0)) for k in keys) or 100; thesis=sum(pillars[k]*float(w.get(k,0)) for k in keys)/total; conviction=.82*thesis+.18*pillars["price_timing"]
    expected=finite(valuation.get("expected_cagr")); base=finite(valuation.get("base_cagr")); bear=finite(valuation.get("bear_return")); tier=str(trust.get("risk_tier") or "SPECULATIVE"); trust_score=finite(trust.get("trust_score")) or 0
    checks={"large_established_company":tier=="CORE" and bool(trust.get("preferred_large_cap")) and bool(trust.get("actionable_established")),"data_trust":trust_score>=float(cfg.get("minimum_trust_for_buy",82)) and not trust.get("critical_flags"),"research_evidence_ready":bool(trust.get("evidence_ready",True)),"valuation_resolved":bool(valuation.get("valuation_resolved")),"required_expected_return":expected is not None and expected>=required_expected,"required_base_return":base is not None and base>=required_base,"bear_case_acceptable":bear is not None and bear>=min_bear,"thesis_strength":thesis>=buy_min,"inside_buy_zone":gap is not None and gap<=max_premium,"entry_not_overextended":not entry["overextended"] or entry["secondary_entry_ready"]}
    critical=bool(trust.get("critical_flags") or valuation.get("critical_flags"))
    if critical: action,rationale="REVIEW DATA","A data, unit-normalization, or valuation sanity check failed."
    elif valuation.get("valuation_status")=="CURRENCY_UNIT_UNRESOLVED": action,rationale="REVIEW DATA","Currency/security units cannot be reconciled safely."
    elif tier=="SPECULATIVE": action,rationale="SPECULATIVE WATCH","Company is below the default large-established risk threshold."
    elif tier!="CORE" or not trust.get("preferred_large_cap") or not trust.get("actionable_established"): action,rationale="WATCH — DEVELOPING","Researchable, but does not pass the full large-established action gate."
    elif not valuation.get("valuation_resolved"): action,rationale="VALUATION UNRESOLVED","Independent valuation methods do not support a credible buy zone."
    elif entry["overextended"] and not entry["secondary_entry_ready"]: action,rationale="TOO LATE / OVEREXTENDED","The primary rerating occurred and price has not reset enough."
    elif thesis>=buy_min and all(checks[k] for k in ["large_established_company","data_trust","research_evidence_ready","valuation_resolved","required_expected_return","required_base_return","bear_case_acceptable","inside_buy_zone","entry_not_overextended"]): action,rationale=("BUY NOW — RESET ENTRY","A meaningful post-rerating reset reopened the entry window.") if entry["secondary_entry_ready"] else ("BUY NOW","Thesis, valuation, evidence and entry price pass configured hurdles.")
    elif thesis>=pull_min and checks["data_trust"] and checks["valuation_resolved"] and checks["bear_case_acceptable"] and gap is not None and gap>max_premium and gap<=max_gap and not entry["overextended"]: action,rationale="BUY ON PULLBACK","Thesis is strong, but price is above the return-required buy zone."
    elif thesis>=watch_min: action,rationale="WATCH — DEVELOPING","Thesis has merit, but valuation/return/entry evidence is insufficient."
    else: action,rationale="PASS","Current risk/reward does not justify capital attention at configured hurdles."
    return {"action":action,"conviction_score":round(conviction,1),"thesis_score":round(thesis,1),"entry_score":entry["entry_score"],"conviction_level":"HIGH" if thesis>=80 else "MEDIUM" if thesis>=65 else "LOW","pillars":pillars,"entry_timing":entry,"checks":checks,"failed_checks":[k for k,v in checks.items() if not v],"rationale":rationale,"required_base_cagr":required_base,"required_expected_cagr":required_expected,"buy_below_price":round(buy_below,2) if buy_below else None,"gap_to_buy_zone":round(gap,4) if gap is not None else None,"base_fair_value":round(base_fair,2) if base_fair else None,"current_price":round(price,2) if price else None}
