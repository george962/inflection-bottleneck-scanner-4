# V5.3 Architecture

```text
U.S.-listed equities
       ↓
persistent batched price/liquidity scan
       ↓
inflection sleeve + high-liquidity challenger sleeve
       ↓
deep Yahoo profile / fundamentals / analyst revisions
       ↓
large-established company gate
       ↓
full-research allocation:
  50% entry opportunities
  30% strongest challengers
  20% late-leader diagnostics
       ↓
SEC submissions + filing documents + cached news
       ↓
SEC diagnostics + data trust
       ↓
industry-aware valuation family
       ↓
independent valuation model agreement gate
       ├── resolved → fair-value scenarios + return-required buy zone
       └── unresolved → model ranges only; no actionable buy zone
       ↓
thesis score (business/evidence)
       +
entry score (price maturity/rerating/reset)
       ↓
BUY NOW
BUY NOW — RESET ENTRY
BUY ON PULLBACK
WATCH — DEVELOPING
TOO LATE / OVEREXTENDED
VALUATION UNRESOLVED
DATA INCOMPLETE
REVIEW DATA
PASS
       ↓
published dashboard + realized forward track record
```

## Why research allocation has an entry sleeve

A discovery engine can correctly identify a bottleneck/inflection but still find it after the stock already rerated. V5.3 reserves half of full-research slots for CORE companies that are not yet LATE. Mature leaders remain in a smaller diagnostic sleeve so the system can explicitly identify missed primary entries and later reset opportunities.

## Why thesis and entry are separate

A good company can be a bad entry. V5.3 therefore does not use one conviction score to represent both ideas.

**Thesis score** combines:

- fundamental inflection
- estimate revisions
- valuation credibility
- company quality
- SEC filing evidence

**Entry score** combines:

- price maturity
- 3/6/12-month rerating
- distance from the 52-week high
- whether a meaningful post-rerating reset occurred

## Valuation resolution rule

A precise buy-below price exists only when independent valuation models pass the agreement gate. V5.3 does not average wildly incompatible values.

For cycle-sensitive memory/storage/semiconductor businesses, forward peak earnings are normalized against historical earnings/cash flow before exit multiples are applied.

## SEC evidence is operationally required

The GitHub Actions workflow requires `SEC_USER_AGENT`, verifies SEC access in `doctor --network`, and rejects a green publish if SEC evidence is systematically missing. Individual filing-download errors are stored in each report rather than swallowed.
