# V5.4.1 Build Validation

V5.4.1 is a reliability hotfix for the production SQLite schema-migration failure found on 2026-08-18.

Validation performed on the packaged source tree:

```text
python compileall       PASS
pytest                  PASS (34 tests)
config JSON             PASS
pyproject TOML          PASS
GitHub Actions YAML     PASS
end-to-end fake publish PASS
V5.3 SQLite migration   PASS
publish health gating   PASS
legacy V5.4 quarantine  PASS
```

Key regressions covered:

- a real V5.3-format `price_daily` table is imported into V5.4.1 `prices`;
- a V5.3 compressed `research_reports` table is preserved and imported into versioned cohorts;
- incompatible V5.3 cache/research tables are retained under `legacy_*` audit names;
- migration is idempotent and does not re-import millions of price rows on every process start;
- V5.4.1 can write a new report after migrating a V5.3 database;
- all-operational-failure publishes fail validation;
- a small bounded operational-failure fraction may pass while those failures stay out of decision history;
- the known broken V5.4 zero-score/DATA_ERROR rows are quarantined rather than treated as investments;
- V5.4 currency/ADR, industry-classification, trust, valuation, ledger and performance tests remain green.
