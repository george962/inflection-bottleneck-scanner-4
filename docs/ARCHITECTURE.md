# v0.3 Architecture

## Why v0.2 was still wrong

Even after separating strength from opportunity, the system began with a
manually selected watchlist. A watchlist containing MU, AMD, SNDK, INTC, DELL,
STX, etc. makes rediscovering recent winners almost inevitable.

That is selection bias.

## v0.3 principle

Discovery and evaluation are separate stages.

### Stage A — broad discovery

Start with current U.S.-listed equities from exchange symbol directories.

Use only cheap, scalable market data to find:
- early breakouts
- recoveries
- quiet accumulation

Do not require a giant past return.

### Stage B — deep evaluation

Only a small candidate set receives expensive calls for:
- quarterly financial statements
- analyst estimates
- estimate revisions
- analyst targets
- valuation

### Stage C — forward-potential ranking

Rank:
- earnings/revenue acceleration
- revisions
- forward growth
- valuation
- operating leverage
- expectation gap
- early discovery

Then subtract explicit price maturity.

## Why not deep-scan 5,000 Yahoo tickers?

It is slow, fragile, and unnecessarily rate-limit-sensitive.

A staged architecture makes it possible to use broad coverage without making
dozens of expensive endpoints calls for every listed security.

## What would make this institution-grade

Replace the current free-data deep stage with point-in-time bulk datasets and
industry evidence. Then use the same two-stage discovery/evaluation design.
