# V5.4 Build Validation

V5.4 is a correctness-and-validation release built around five regression classes:

1. foreign-currency / ADR unit mismatches must fail closed;
2. networking/computer-hardware names must not be treated as memory solely from a broad label;
3. ISO-formatted first-trade dates must produce `years_public`;
4. outcome tracking must use the active model version and preserve model cohorts;
5. public diagnostics must not echo raw HTTP header/secret values.

Validation performed on the packaged source tree:

```text
python compileall       PASS
pytest                  PASS (28 tests)
config JSON             PASS
pyproject TOML          PASS
GitHub Actions YAML     PASS
end-to-end fake publish PASS
```

The end-to-end test exercises discovery → deep research → valuation/trust/conviction → published metadata → decision ledger → PIT estimate ledger without network access.
