from __future__ import annotations
import json,os
def synthesize_with_openai(report,model="gpt-5-mini"):
    key=os.getenv("OPENAI_API_KEY","").strip()
    if not key:return None
    try:from openai import OpenAI
    except Exception:return None
    compact={"ticker":report.get("ticker"),"company":report.get("company"),"metrics":report.get("metrics"),"valuation":report.get("valuation"),
             "decision":report.get("decision"),"filing_evidence":[{"id":f"F{i+1}","topic":e.get("topic"),"tone":e.get("tone"),"text":e.get("text"),"form":e.get("form"),"filing_date":e.get("filing_date")} for i,e in enumerate(report.get("filing_evidence",[])[:18])],
             "news":[{"id":f"N{i+1}","title":n.get("title"),"publisher":n.get("publisher"),"published":n.get("published"),"summary":n.get("summary")} for i,n in enumerate(report.get("news",[])[:10])]}
    prompt="Use ONLY the supplied JSON. Do not add facts from memory. The deterministic valuation engine already made the decision; do not override it. Summarize: why attractive now, strongest reasons not to buy, valuation assumptions, what changes the decision. Cite evidence IDs like [F1]/[N2]. If evidence is weak, say so.\nDATA:\n"+json.dumps(compact,default=str)
    try:
        r=OpenAI(api_key=key).responses.create(model=os.getenv("OPENAI_MODEL",model),input=prompt)
        text=getattr(r,"output_text",None);return text.strip() if text else None
    except Exception:return None
