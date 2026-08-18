# V5.4 Validation and Track Record

## No fake historical backtest

A valid historical model requires point-in-time versions of:

- analyst consensus and revisions;
- as-reported fundamentals;
- filing availability timestamps;
- universe membership;
- corporate actions and delistings.

Today's analyst estimates cannot be retroactively inserted into prior dates.

## Prospective V5.4 evidence

Each published run commits:

`published/decision_ledger.jsonl`

and:

`published/pit_estimates.jsonl`

The outcome tracker is explicitly cohort-versioned. A V5.4 report is evaluated as V5.4; it is not silently queried as V5.2 or mixed with a prior rule set.

## Outcome fields

For each matured horizon the engine records:

- realized absolute return;
- SPY return;
- excess return;
- maximum adverse excursion;
- maximum favorable excursion.

Action-level summaries include positive-return hit rate and positive-excess-return rate.

## Calibration gate

A cohort is not considered informative until it contains at least 10 matured observations. For actual parameter recalibration, substantially larger chronological samples are preferable.
