# Backtesting Rules

The easiest way to fool yourself with this project is accidental look-ahead bias.

## Never do this

Do not take today's:
- quarterly financial statement history
- current analyst consensus
- current "historical" estimate table
- current constituent universe

and pretend those values were available on a past date.

## V1 baseline

`inflection-scanner backtest` uses only adjusted historical prices.

At each month-end:
1. Calculate trailing 3-month and 6-month momentum.
2. Rank the configured universe.
3. Hold the top K names for the next month.
4. Compare with SPY.

This is not the final strategy. It is a plumbing check for:
- walk-forward timing
- ranking
- portfolio formation
- output metrics

## Required data for the real model

For a valid historical inflection model, acquire point-in-time:

- SEC filing acceptance timestamps
- as-reported quarterly fundamentals
- analyst consensus snapshots by date
- historical estimate revisions
- historical industry price/capacity data
- delisting/corporate-action history
- a survivorship-bias-safe universe

## Validation scheme

Use chronological walk-forward folds.

Example:

```text
Train: 2013-2018
Validate: 2019
Test: 2020

Train: 2013-2019
Validate: 2020
Test: 2021

...
```

No random train/test splits.

## Primary prediction targets

Do not use only "did stock double?"

Prefer:
- forward 3M sector-relative return
- forward 6M sector-relative return
- forward 12M sector-relative return
- top-decile outcome
- >20% sector outperformance
- >50% absolute return
- maximum forward drawdown

## Evaluation

Report:
- rank IC
- top-decile return
- top-decile hit rate
- sector-neutral return
- max drawdown
- turnover
- calibration
- precision at K
- results by sector and market regime

## Multiple testing

Every new feature family should have:
- a hypothesis before test
- an ablation
- out-of-sample evaluation
- a recorded experiment ID

Do not keep adding variants until one backtest looks good.
