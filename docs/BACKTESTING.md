# Validation and Track Record

V5 separates two things that should not be confused:

1. **Scenario valuation** — a forward-looking research model.
2. **Realized track record** — what actually happened after prior v5 decisions.

## Realized v5 outcomes

Every v5 report is stored in `research_reports` with:

- timestamp
- ticker
- original action
- original price
- original conviction

Once enough time passes, `performance.py` measures realized 90/180/365-day returns from the persistent price warehouse.

The published dashboard reports:

- observation count
- hit rate
- average realized return
- median realized return

A group is not marked as having enough history until it has at least 10 matured observations.

## Why this is not a historical backtest yet

Today's Yahoo analyst estimates cannot be retroactively treated as point-in-time historical estimates. Doing so would create look-ahead bias.

A proper historical model needs point-in-time datasets for:

- estimate consensus and revisions
- filing availability timestamps
- as-reported fundamentals
- survivorship-safe universe membership
- corporate actions / delistings

Until those are available, v5's honest validation path is to accumulate decisions prospectively and measure them later.

## Future calibration

When enough v5 observations accumulate, use chronological cohorts to answer:

- Does `BUY NOW` outperform `WATCH`?
- Does a higher conviction score correspond to higher realized return?
- Does the buy-zone rule reduce drawdown versus buying immediately?
- Which pillars have the most predictive value?
- Are late-stage names being rejected too aggressively or not aggressively enough?
