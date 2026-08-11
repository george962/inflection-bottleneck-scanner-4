# V5.1 Build Validation

Run from the repository root:

```bash
python -m compileall -q src dashboard tests scripts
pytest -q
python scripts/validate_publish.py --min-reports 1  # after a live research run
```

V5.1 specifically tests missing first-trade-date handling, known-too-new rejection, empty-publish rejection, large-cap selection, late-stage caps, buy zones, valuation sanity gates, and warehouse behavior.
