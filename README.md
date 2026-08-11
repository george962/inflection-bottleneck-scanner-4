# Large-Cap Inflection Research v5

V5 is a clean, complete replacement for the earlier scanner versions.

The goal is not to find the highest-scoring obscure stock. The default question is:

> Which **large, established, liquid U.S.-listed companies** are showing a real fundamental/estimate inflection, and is **today's price** attractive enough to meet a demanding forward-return hurdle?

## What changed in v5

### 1. Small/new companies no longer dominate the recommendations

Broad discovery still scans U.S.-listed stocks, but full research defaults to a **CORE** company gate:

- market cap >= **$15B**
- public history >= **7 years**
- next-year EPS analyst coverage >= **10 analysts**
- 20-day average dollar volume >= **$50M/day**

Companies >= $25B are marked as preferred large caps.

A secondary MIDCAP tier exists for research breadth. **Actionable `BUY NOW` / `BUY ON PULLBACK` recommendations additionally require the preferred $25B+ large-cap tier by default.** Smaller CORE/MIDCAP names can still be researched, but remain WATCH unless you deliberately lower the policy thresholds.

All thresholds are editable in `config/default.json`.

### 2. Large names can enter even after a rally

V5 does **not** exclude a company merely because it already rose.

The discovery pool reserves a large high-liquidity challenger sleeve, so established companies can reach deep research even if a smaller stock has a more dramatic short-term breakout.

There is still a global cap on LATE-stage names. The earlier bug where the liquidity sleeve could bypass `max_late_fraction` is fixed and tested.

### 3. `BUY NOW` means more than “high score”

V5 uses six independent conviction pillars:

1. Fundamental inflection
2. Estimate revisions
3. Valuation
4. Price timing
5. Company quality / institutional scale
6. Filing/evidence quality

The dashboard shows every pillar rather than hiding the answer inside one score.

### 4. Buy-zone price instead of just a target price

The model first builds bear/base/bull fair values using multiple valuation methods when possible.

Then it asks:

> What is the **maximum price I can pay today** and still earn at least the configured base-case return hurdle?

Default base-case hurdle: **15% CAGR over 3 years**.

Example conceptually:

```text
Base fair value in 3 years:     $180
Required base-case CAGR:          15%
Maximum buy-zone price today:   $118
Current price:                  $132

Action: BUY ON PULLBACK
```

That directly distinguishes a strong company from a strong company whose stock is already too expensive.

### 5. No fake probability-of-profit number

The bear/base/bull weights are **modeling weights**, not statistically calibrated probabilities.

V5 does not label them `P(profit)`.

### 6. Extreme upside is treated as suspicious

V5 automatically suppresses a normal recommendation and uses `REVIEW DATA` when it encounters anomalies such as:

- expected CAGR > 50%
- fair value > 3x current price
- the bear case is implausibly far above today's price
- market cap, share count, and price disagree
- current price / next-year EPS implies an implausible multiple

This is designed to prevent absurd outputs from being displayed as high-confidence buys.

### 7. Valuation triangulation

For profitable companies, v5 can combine:

- forward EPS / exit P/E
- normalized-cycle EPS for cyclicals
- FCF-yield valuation
- forward-revenue valuation when earnings are not meaningful

Scenario fair values use the median of the usable valuation methods.

A normal `BUY NOW` requires at least two usable methods with reasonable agreement.

### 8. Persistent data cache

The GitHub Actions workflow restores and updates:

```text
data/warehouse.db
```

The warehouse contains:

- daily price history
- cached profiles
- cached financial statements
- cached analyst estimate/revision tables
- cached news
- SEC filing text keyed by accession number
- historical v5 research reports

Historical prices and immutable SEC filing documents are reused. Mutable objects refresh on TTLs in `config/default.json`.

V5 uses a new `yahoo:v5:*` cache namespace so it does not silently reuse incompatible v4 cached objects.

### 9. Realized track record

V5 stores each decision in the warehouse. After enough time passes, it measures the **actual** subsequent stock return at 90, 180, and 365 days.

The Streamlit dashboard shows the realized track record separately from the valuation model.

A decision group is not labeled statistically informative until it has at least 10 matured observations.

## Decision vocabulary

### `BUY NOW`

Preferred $25B+ large-established company + high trust + multiple valuation methods + strong conviction pillars + acceptable bear case + current price inside the required-return buy zone.

### `BUY ON PULLBACK`

The company/research case is strong, but the current price is above the price that meets the required return hurdle.

### `WATCH`

Interesting, but one or more required buy conditions are not strong enough.

### `TOO LATE`

The company may still be excellent, but too much appears reflected in the current price relative to the return hurdle.

### `REVIEW DATA`

A sanity check failed. Do not trust the modeled upside until the data is validated.

### `SPECULATIVE WATCH`

Below the default size/history/coverage/liquidity threshold.

### `PASS`

Insufficient evidence or forward return.

## GitHub Actions: recommended way to run

The main workflow is:

```text
.github/workflows/research.yml
```

It runs automatically on weekdays and can also be started manually.

Default manual inputs:

```text
deep_candidates:       180
research_candidates:    20
force_refresh:        false
```

The workflow runs the full tests **before** starting research.

## Required GitHub secret

Add:

```text
SEC_USER_AGENT
```

Example value:

```text
Your Name your-email@example.com
```

Optional:

```text
OPENAI_API_KEY
```

The OpenAI key is only used to create an additional narrative synthesis of evidence already collected. The deterministic research, trust, valuation, conviction, and buy-zone logic work without it.

## Streamlit

The Streamlit entry point is:

```text
dashboard/app.py
```

The dashboard reads only committed files from `published/`. Opening the dashboard does not rerun the market-data pipeline.

The GitHub Action publishes:

```text
published/latest_research.json
published/latest_research.csv
published/track_record.json
published/metadata.json
```

## Local smoke test

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dashboard,dev,llm]"
pytest -q
inflection-scanner doctor --network
inflection-scanner research --max-universe 500 --deep 80 --research-count 10 --top 15
streamlit run dashboard/app.py
```

## Full local run

```bash
inflection-scanner research --deep 180 --research-count 20 --top 30
```

## Important limitation

This is a research and prioritization engine, not a guarantee of returns. The point of v5 is to make the recommendation **harder to earn and easier to audit**: large-company gate, source checks, multiple valuation methods, explicit buy-zone math, thesis risks, and realized-outcome tracking.
