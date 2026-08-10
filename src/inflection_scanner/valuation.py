from __future__ import annotations
import math,statistics
from typing import Any
import pandas as pd
def finite(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except Exception:return None
def clamp(x,lo,hi):return max(lo,min(hi,x))
def row_values(df,aliases):
    if df is None or df.empty:return []
    norm={str(i).lower().replace(" ",""):i for i in df.index}
    for a in aliases:
        k=a.lower().replace(" ","")
        if k in norm:
            vals=[]
            for v in df.loc[norm[k]].tolist():
                x=finite(v)
                if x is not None:vals.append(x)
            return vals
    return []
def positive_median(vals):
    x=[v for v in vals if v>0];return statistics.median(x) if x else None
def classify_company(profile,features):
    sector=str(profile.get("sector") or "").lower(); fpe=finite(profile.get("forward_pe"))
    ne=finite(features.get("next_year_eps_estimate")); rg=finite(features.get("next_year_revenue_growth_estimate")) or finite(features.get("revenue_yoy")) or 0
    om=finite(features.get("operating_margin")); oc=finite(features.get("operating_margin_change_yoy"))
    if "financial" in sector or "real estate" in sector:return "SPECIAL_CASE"
    if any(x in sector for x in ["energy","basic materials"]):return "CYCLICAL"
    if (fpe is None or fpe<=0) and (ne is None or ne<=0) and rg>.10:return "EARLY_STAGE_GROWTH"
    if om is not None and om<.05 and oc is not None and oc>.02:return "TURNAROUND"
    if ne is not None and ne>0:return "PROFITABLE_GROWTH"
    return "GENERAL"
def sc(name,p,fv,ass):return {"name":name,"probability":p,"fair_value":round(fv,2) if fv is not None else None,"assumptions":ass}
def _earnings(price,eps,g,h):
    g=clamp(g,-.2,.7); yrs=max(1,h-1); bg=clamp(g*.7,-.05,.35); br=clamp(g*.25-.05,-.15,.18); bu=clamp(g*.95+.02,.02,.5)
    bpe=clamp(12+36*max(bg,0),12,28); rpe=clamp(bpe*.65,8,18); upe=clamp(bpe*1.25,16,36)
    return [sc("Bear",.25,eps*((1+br)**yrs)*rpe,{"eps_growth":br,"exit_pe":rpe}),
            sc("Base",.5,eps*((1+bg)**yrs)*bpe,{"eps_growth":bg,"exit_pe":bpe}),
            sc("Bull",.25,eps*((1+bu)**yrs)*upe,{"eps_growth":bu,"exit_pe":upe})]
def _revenue(price,rev,shares,g,h):
    g=clamp(g,-.1,.6);yrs=max(1,h-1);bg=clamp(g*.75,0,.35);br=clamp(g*.3-.03,-.08,.15);bu=clamp(g+0.02,.04,.5)
    bpm=clamp(1.2+8*max(bg,0),1.2,5.5); rpm=clamp(bpm*.55,.7,2.5); upm=clamp(bpm*1.35,1.8,7.5)
    fair=lambda growth,mult:rev*((1+growth)**yrs)*mult/shares
    return [sc("Bear",.25,fair(br,rpm),{"revenue_growth":br,"exit_price_sales":rpm}),
            sc("Base",.5,fair(bg,bpm),{"revenue_growth":bg,"exit_price_sales":bpm}),
            sc("Bull",.25,fair(bu,upm),{"revenue_growth":bu,"exit_price_sales":upm})]
def _cyc(eps):
    return [sc("Bear",.25,eps*.65*8,{"normalized_eps_factor":.65,"exit_pe":8}),
            sc("Base",.5,eps*12,{"normalized_eps_factor":1.0,"exit_pe":12}),
            sc("Bull",.25,eps*1.35*16,{"normalized_eps_factor":1.35,"exit_pe":16})]
def build_valuation(profile,features,annual_financials,horizon_years=3):
    price=finite(features.get("price"))
    if price is None or price<=0:return {"model":"UNAVAILABLE","scenarios":[],"reason":"Current price unavailable."}
    typ=classify_company(profile,features); eps=finite(features.get("next_year_eps_estimate")); eg=finite(features.get("next_year_eps_growth"))
    rev=finite(features.get("next_year_revenue_estimate")); rg=finite(features.get("next_year_revenue_growth_estimate")); shares=finite(profile.get("shares_outstanding"))
    annual_eps=row_values(annual_financials.get("income",pd.DataFrame()),["Diluted EPS","Basic EPS","Diluted EPS Continuing Operations"])
    norm=positive_median(annual_eps); scenarios=[];model="UNAVAILABLE";reason=""
    if typ=="CYCLICAL":
        c=[x for x in [norm,eps] if x is not None and x>0]
        if c:
            scenarios=_cyc(statistics.median(c));model="NORMALIZED_CYCLICAL_EARNINGS";reason="Uses normalized positive annual EPS plus forward EPS instead of capitalizing peak-cycle earnings."
    elif typ in {"PROFITABLE_GROWTH","TURNAROUND","GENERAL"} and eps is not None and eps>0:
        scenarios=_earnings(price,eps,eg if eg is not None else .08,horizon_years);model="FORWARD_EPS_EXIT_MULTIPLE";reason="Projects forward EPS under bear/base/bull growth and exit-multiple assumptions."
    if not scenarios and typ in {"EARLY_STAGE_GROWTH","TURNAROUND","GENERAL"} and rev and rev>0 and shares and shares>0:
        scenarios=_revenue(price,rev,shares,rg if rg is not None else .1,horizon_years);model="FORWARD_REVENUE_MULTIPLE";reason="Earnings are not useful, so forward revenue is valued with restrained scenario multiples."
    if not scenarios:return {"company_type":typ,"model":"NEEDS_SPECIALIST_VALUATION","reason":"Generic earnings/revenue valuation is not reliable for this company.","scenarios":[],"current_price":price}
    ev=sum(s["probability"]*s["fair_value"] for s in scenarios);bear=scenarios[0];base=scenarios[1]
    cagr=(ev/price)**(1/horizon_years)-1 if ev>0 else None;basec=(base["fair_value"]/price)**(1/horizon_years)-1 if base["fair_value"]>0 else None
    downside=bear["fair_value"]/price-1;pp=sum(s["probability"] for s in scenarios if s["fair_value"]>price)
    return {"company_type":typ,"model":model,"reason":reason,"current_price":round(price,2),"horizon_years":horizon_years,"scenarios":scenarios,
            "expected_value":round(ev,2),"expected_cagr":round(cagr,4),"base_cagr":round(basec,4),"bear_downside":round(downside,4),"probability_profit":round(pp,4)}
def make_decision(valuation,scores,data_quality,thresholds,risk_penalty=0):
    c=finite(valuation.get("expected_cagr"));p=finite(valuation.get("probability_profit"));down=finite(valuation.get("bear_downside"));mat=finite(scores.get("price_maturity")) or 0
    if valuation.get("model") in {"UNAVAILABLE","NEEDS_SPECIALIST_VALUATION"}:return {"decision":"WATCH","confidence":"LOW","reason":"Generic valuation model is not reliable enough for an automated buy/pass call."}
    if c is None or p is None or down is None:return {"decision":"WATCH","confidence":"LOW","reason":"Scenario valuation is incomplete."}
    bc=float(thresholds.get("buy_min_expected_cagr",.18));bp=float(thresholds.get("buy_min_probability_profit",.65));bd=float(thresholds.get("buy_max_bear_downside",-.4))
    scg=float(thresholds.get("small_buy_min_expected_cagr",.16));wc=float(thresholds.get("watch_min_expected_cagr",.08));late=float(thresholds.get("too_late_maturity",75))
    adj=c-risk_penalty
    if adj>=bc and p>=bp and down>=bd and data_quality>=70:decision="BUY"
    elif adj>=scg and p>=.5:decision="SMALL BUY / SPECULATIVE"
    elif mat>=late and adj<.15:decision="TOO LATE"
    elif adj>=wc:decision="WATCH"
    else:decision="PASS"
    cov=float(scores.get("weighted_coverage") or 0)/100;conf=.45*min(max(data_quality/100,0),1)+.35*min(max(p,0),1)+.2*min(max(cov,0),1)
    label="HIGH" if conf>=.78 else "MEDIUM" if conf>=.6 else "LOW"
    return {"decision":decision,"confidence":label,"confidence_score":round(conf,3),"adjusted_expected_cagr":round(adj,4),
            "reason":f"Expected {valuation.get('horizon_years',3)}Y CAGR {c:.1%}, scenario profit probability {p:.0%}, bear-case downside {down:.1%}, price maturity {mat:.0f}/100."}
