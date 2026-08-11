from inflection_scanner.research_evidence import extract_filing_evidence,summarize_evidence
def test_evidence():
    filings=[{"form":"10-Q","filing_date":"2026-08-01","source_url":"x","accession":"1","text":"Customer demand increased significantly and backlog reached a record level. Gross margin improved due to higher pricing. We continue to face supply constraints and regulatory uncertainty."}]
    e=extract_filing_evidence(filings);s=summarize_evidence(e);assert e and "demand" in s["topics_found"] and s["positive_count"]>=1 and s["negative_count"]>=1
