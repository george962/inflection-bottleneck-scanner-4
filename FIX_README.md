# Scanner 4 late-stage cap fix

This patch fixes the CI failure:

```text
assert (selected["price_stage"] == "LATE").sum() <= 5
AssertionError: assert 10 <= 5
```

The bug was in `select_deep_candidates()`.

The high-liquidity challenger sleeve was added after the late-stage signal
allocation, and its LATE names were not counted against the overall
`max_late_fraction`.

The corrected selector enforces a single GLOBAL late-stage cap across:

- signal candidates;
- mature challengers;
- high-liquidity challengers;
- filler candidates.

With:

```text
deep_candidates = 20
max_late_fraction = 0.25
```

the final result can contain at most 5 LATE names.

The high-liquidity challenger feature remains intact, so a large/liquid
MID/EARLY company can still enter the deep-research pool.
