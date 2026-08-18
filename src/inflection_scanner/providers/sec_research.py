from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup


def fetch_optional_filings(sec_provider,cik: str | None,forms: list[str] | None=None,limit: int=3,max_chars: int=120000) -> tuple[list[dict[str,Any]],dict[str,Any]]:
    if not cik or not sec_provider.available:
        return [],{"state":"DISABLED","available":False,"submission_ok":False,"documents_requested":0,"documents_downloaded":0,"errors":[]}
    submissions,status=sec_provider.submissions(str(cik)); status={**status,"documents_requested":0,"documents_downloaded":0}
    if not submissions or not status.get("submission_ok"):
        return [],status
    recent=(submissions.get("filings") or {}).get("recent") or {}; allowed=set(forms or ["10-K","10-Q","8-K"])
    cols={k:recent.get(k,[]) for k in ["form","filingDate","accessionNumber","primaryDocument"]}; n=max((len(v) for v in cols.values()),default=0); filings=[]; errors=list(status.get("errors",[]))
    for i in range(n):
        form=_get(cols["form"],i)
        if form not in allowed:continue
        accession=_get(cols["accessionNumber"],i); primary=_get(cols["primaryDocument"],i)
        if not accession or not primary:continue
        status["documents_requested"]+=1
        text,error=sec_provider.filing_document(str(cik),str(accession),str(primary))
        if error: errors.append(error)
        else:
            status["documents_downloaded"]+=1
            cleaned=BeautifulSoup(text or "","html.parser").get_text(" ",strip=True)[:max_chars]
            filings.append({"form":form,"filing_date":_get(cols["filingDate"],i),"accession_number":accession,"primary_document":primary,"text_excerpt":cleaned})
        if len(filings)>=limit or status["documents_requested"]>=limit:break
    status["errors"]=list(dict.fromkeys(errors)); status["state"]="OK" if filings and not errors else "PARTIAL_ERROR" if filings else "ERROR" if errors else "NO_MATCHING_FILINGS"
    return filings,status

def _get(values,index):
    try:return values[index]
    except Exception:return None
