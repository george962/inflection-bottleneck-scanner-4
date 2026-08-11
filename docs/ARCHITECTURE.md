# V5 Architecture

```text
U.S.-listed equities
       ↓
batched price/liquidity scan
       ↓
inflection sleeve + high-liquidity challenger sleeve
       ↓
deep Yahoo profile / quarterly fundamentals / analyst revisions
       ↓
large-established company gate
       ↓
SEC filings + cached news
       ↓
data-trust checks
       ↓
valuation triangulation
       ↓
six conviction pillars
       ↓
required-return buy-zone calculation
       ↓
BUY NOW / BUY ON PULLBACK / WATCH / TOO LATE / REVIEW DATA / PASS
       ↓
published dashboard + historical realized-outcome tracking
```

## Why high-liquidity challengers exist

A discovery system based only on the strongest short-term inflection score tends to surface smaller volatile companies. V5 reserves more than half of deep-analysis slots for high-dollar-volume candidates. This gives established companies a direct route to deep research without manually seeding specific tickers.

## Why the company gate is after deep discovery

Market cap, analyst coverage, and first-trade history come from the deep profile stage. Price/liquidity data is cheap to scan broadly; deep company metadata is more expensive. The pipeline therefore scans broadly, deep-loads a bounded candidate pool, and then applies the large-established gate.

## Why BUY NOW is rare

A candidate must pass:

- institutional-scale company gate
- data consistency checks
- SEC evidence requirement
- two or more valuation methods
- valuation-method agreement
- conviction pillar floor
- expected-return hurdle
- base-case return hurdle
- acceptable bear case
- current price inside the buy zone

This intentionally favors false negatives over confident false positives.
