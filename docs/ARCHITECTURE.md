# V5.4.1 Architecture

V5.4.1 keeps V5.3's separation of thesis quality and entry timing, but inserts a hard **security-normalization gate** before valuation and adds durable point-in-time validation artifacts after each research run.

```text
broad U.S.-listed discovery
        ↓
batched price/liquidity warehouse
        ↓
entry + challenger + late-diagnostic research allocation
        ↓
profile/fundamental/estimate research
        ↓
large-established gate
        ↓
currency / ADR / share-unit normalization
        ├── unresolved → no valuation model, REVIEW DATA
        └── resolved
              ↓
industry-aware valuation family
              ↓
independent model agreement + sanity gates
        ├── unresolved → no actionable buy zone
        └── resolved → blended scenarios + return-required buy zone
              ↓
thesis score + independent entry score
              ↓
recommendation
              ↓
published dashboard
        + durable decision ledger
        + PIT estimate ledger
        + versioned benchmark-relative realized outcomes
```

## Security normalization contract

Statement values and market/security values are never assumed to share a unit system.

For each researched ticker V5.4.1 records:

- trading currency;
- statement currency;
- FX rate from statement to trading currency;
- underlying shares represented by a traded share/ADR;
- whether conversion is resolved;
- the conversion source.

Statement EPS is a **per-underlying-share** value, so an ADR ratio is applied to EPS. Total FCF is a **total financial amount**, so it receives FX conversion only; division by the traded-security share count then produces per-traded-share cash flow without double-counting the ADR ratio.

## SEC policy

SEC is optional enrichment in V5.4.1. Missing SEC access does not reduce trust by itself and does not block BUY/WATCH decisions. Raw HTTP exceptions are not published.

## Deterministic scoring

LLM output is not part of the deterministic recommendation path. LLM narrative enrichment, if enabled, must not change core scores or actions.
