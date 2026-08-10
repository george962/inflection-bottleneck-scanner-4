from __future__ import annotations
import math
import pandas as pd
def _f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None
def _ret(c,d):
    if len(c)<=d:return None
    a,b=_f(c.iloc[-d-1]),_f(c.iloc[-1]); return None if a in (None,0) or b is None else b/a-1
def _prior(c,recent,prior):
    if len(c)<recent+prior+1:return None
    e,s=_f(c.iloc[-recent-1]),_f(c.iloc[-recent-prior-1]); return None if e is None or s in (None,0) else e/s-1
def _peak(v,lo,ideal,hi):
    if v is None or v<=lo or v>=hi:return 0.0
    return 100*(v-lo)/(ideal-lo) if v<=ideal else 100*(hi-v)/(hi-ideal)
def _lin(v,bad,good):
    if v is None:return 0.0
    return max(0,min(100,100*(v-bad)/(good-bad)))
def compute_price_discovery_features(df):
    if df is None or df.empty or "Close" not in df:return {}
    c=df["Close"].dropna().astype(float); vol=df["Volume"].dropna().astype(float) if "Volume" in df else pd.Series(dtype=float)
    if len(c)<80:return {}
    price=_f(c.iloc[-1]); r1,r3,r6,r12=(_ret(c,21),_ret(c,63),_ret(c,126),_ret(c,252)); p1,p3=_prior(c,21,21),_prior(c,63,63)
    high=_f(c.tail(min(252,len(c))).max()); dist=price/high-1 if price is not None and high not in (None,0) else None
    dv20=vr=None
    if len(vol)>=25:
        a=pd.DataFrame({"close":c,"volume":vol}).dropna()
        if len(a)>=25:
            dv20=_f((a["close"].tail(20)*a["volume"].tail(20)).mean()); rv=_f(a["volume"].tail(5).mean()); pv=_f(a["volume"].iloc[-25:-5].mean())
            if rv is not None and pv not in (None,0):vr=rv/pv
    ma50=_f(c.tail(50).mean()) if len(c)>=50 else None; above=price/ma50-1 if price is not None and ma50 not in (None,0) else None
    a1=r1-p1 if r1 is not None and p1 is not None else None; a3=r3-p3 if r3 is not None and p3 is not None else None
    maturity=.45*_lin(r6,.35,1.0)+.45*_lin(r12,.55,1.6)+.10*_lin(dist,-.03,.02)
    if (r6 is not None and r6>=.8) or (r12 is not None and r12>=1.1):maturity=max(maturity,80)
    elif (r6 is not None and r6>=.5) or (r12 is not None and r12>=.7):maturity=max(maturity,50)
    early=.28*_peak(r3,-.05,.18,.70)+.22*_lin(a1,-.08,.2)+.18*_peak(dist,-.3,-.06,.03)+.17*_lin(vr,.8,1.8)+.15*_peak(r6,-.1,.3,1.0)
    recovery=.30*_peak(r12,-.65,-.05,.45)+.25*_peak(r3,-.08,.16,.5)+.20*_lin(a1,-.08,.18)+.15*_lin(above,-.12,.12)+.10*_lin(vr,.8,1.7)
    quiet=.30*_peak(r3,-.1,.08,.32)+.25*_lin(vr,.9,2.0)+.20*_lin(a1,-.1,.16)+.15*_peak(dist,-.4,-.12,.02)+.10*_peak(r6,-.15,.18,.65)
    mature=.35*_lin(r3,0,.45)+.25*_lin(vr,.8,1.6)+.20*_lin(a1,-.1,.15)+.20*_lin(maturity,45,90)
    stage="LATE" if maturity>=70 else "MID" if maturity>=40 else "EARLY"
    buckets={"EARLY_BREAKOUT":early,"RECOVERY":recovery,"QUIET_ACCUMULATION":quiet}
    if stage=="LATE":buckets["MATURE_CHALLENGER"]=mature
    bucket=max(buckets,key=buckets.get); best=max(buckets.values()); seed=max(0,best-(.12*maturity if bucket!="MATURE_CHALLENGER" else 0))
    return {"price":price,"days_history":len(c),"dollar_volume_20d":dv20,"return_1m":r1,"return_3m":r3,"return_6m":r6,"return_12m":r12,
            "prior_return_1m":p1,"prior_return_3m":p3,"momentum_accel_1m":a1,"momentum_accel_3m":a3,
            "distance_from_52w_high":dist,"volume_ratio_5v20":vr,"above_ma50":above,"price_maturity_score":round(maturity,2),
            "price_stage":stage,"discovery_bucket":bucket,"early_breakout_score":round(early,2),"recovery_score":round(recovery,2),
            "quiet_accumulation_score":round(quiet,2),"mature_challenger_score":round(mature,2),"discovery_seed_score":round(seed,2)}
def select_deep_candidates(scan,min_price,min_dollar_volume_20d,min_history_days,deep_candidates,bucket_size,max_late_fraction=.25):
    if scan.empty:return scan
    e=scan[(scan.price.fillna(0)>=min_price)&(scan.dollar_volume_20d.fillna(0)>=min_dollar_volume_20d)&(scan.days_history.fillna(0)>=min_history_days)].copy()
    early_budget=max(1,int(deep_candidates*(1-max_late_fraction))); pieces=[]
    for b in ["EARLY_BREAKOUT","RECOVERY","QUIET_ACCUMULATION"]:
        pieces.append(e[(e.discovery_bucket==b)&(e.price_stage!="LATE")].sort_values("discovery_seed_score",ascending=False).head(bucket_size))
    early=pd.concat(pieces,ignore_index=True).drop_duplicates("ticker").sort_values("discovery_seed_score",ascending=False).head(early_budget)
    late_budget=max(0,deep_candidates-len(early)); late_pool=e[e.price_stage=="LATE"].copy(); sort_col="mature_challenger_score" if "mature_challenger_score" in late_pool.columns else "discovery_seed_score"; late=late_pool.sort_values([sort_col,"dollar_volume_20d"],ascending=[False,False]).head(late_budget)
    return pd.concat([early,late],ignore_index=True).drop_duplicates("ticker").head(deep_candidates).reset_index(drop=True)
