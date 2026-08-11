# V5.2 Build Validation

From the repository root:

```bash
python -m compileall -q src dashboard tests scripts
pytest -q
```

After a live research run:

```bash
python scripts/validate_publish.py --min-reports 5 --min-sec-ready-fraction 0.60
```

Current packaged build result: **41 tests passed**.

V5.2 regression coverage includes:

- large-company admission and small/new-company exclusion;
- missing Yahoo listing-age metadata handling;
- global late-stage candidate cap;
- reserved non-LATE entry-opportunity research slots;
- separate thesis and entry timing;
- `TOO LATE / OVEREXTENDED` independent of a calculated buy zone;
- reset-entry reopening after a meaningful pullback;
- `DATA INCOMPLETE` for missing SEC evidence;
- SEC missing-identity diagnostics instead of silent empty evidence;
- memory/storage and high-cycle semiconductor classification;
- normalized-cycle EPS rather than peak forward-EPS extrapolation;
- unresolved valuation when models disagree;
- no blended fair value/buy zone in unresolved state;
- publish rejection for systemic SEC evidence failure;
- warehouse and realized-outcome tracking behavior.
