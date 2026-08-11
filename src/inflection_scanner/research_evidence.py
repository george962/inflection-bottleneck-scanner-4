from __future__ import annotations
import re
TOPICS={
"demand":["demand","bookings","backlog","orders","customer demand","pipeline"],
"pricing":["pricing","average selling price","asp","price increase","price decreases"],
"capacity_supply":["capacity","supply constraint","supply constraints","lead time","lead times","utilization","sold out"],
"customers":["customer concentration","major customer","largest customer","hyperscaler","qualification"],
"margins":["gross margin","operating margin","margin expansion","margin pressure","profitability"],
"capital":["capital expenditure","capex","liquidity","debt","refinancing","cash flow","free cash flow"],
"risks":["risk","uncertainty","competition","competitive","shortage","delay","delays","regulatory"]}
POS=["increase","increased","increasing","growth","strong","improved","improving","expansion","higher","record","accelerat","sold out","fully committed"]
NEG=["decrease","decreased","decline","declined","weak","pressure","lower","delay","uncertain","risk","constraint","shortage","loss","impairment"]
def _sentences(text):return [re.sub(r"\s+"," ",x).strip() for x in re.split(r"(?<=[.!?])\s+",text or "") if len(x.strip())>=45]
def _tone(s):
    z=s.lower(); p=sum(x in z for x in POS); n=sum(x in z for x in NEG)
    return "positive" if p>n else "negative" if n>p else "mixed"
def extract_filing_evidence(filings,max_per_topic=4):
    ev=[]; seen=set()
    for filing in filings:
        for s in _sentences(filing.get("text","")):
            low=s.lower()
            for topic,terms in TOPICS.items():
                if not any(t in low for t in terms):continue
                key=(topic,s[:180])
                if key in seen:continue
                seen.add(key); ev.append({"topic":topic,"tone":_tone(s),"text":s[:700],"form":filing.get("form"),
                    "filing_date":filing.get("filing_date"),"source_url":filing.get("source_url"),"accession":filing.get("accession")})
    out=[]
    for topic in TOPICS:
        rows=[e for e in ev if e["topic"]==topic]; rows.sort(key=lambda x:str(x.get("filing_date") or ""),reverse=True); out.extend(rows[:max_per_topic])
    return out
def summarize_evidence(ev):
    p=sum(e.get("tone")=="positive" for e in ev); n=sum(e.get("tone")=="negative" for e in ev)
    return {"positive_count":p,"negative_count":n,"mixed_count":len(ev)-p-n,"topics_found":sorted({e["topic"] for e in ev}),"net_tone":p-n}
