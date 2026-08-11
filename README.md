# Large-Cap Inflection Research v5.2

V5.2 is a complete repository for finding **large, established, liquid U.S.-listed companies** whose fundamentals and estimates are improving, then deciding whether the **entry is still attractive today**.

The system deliberately avoids turning a numerical score into a BUY. It separates three questions:

1. **Is the company / thesis attractive?**
2. **Can the valuation be resolved credibly?**
3. **Has the primary entry already passed?**

That distinction is the main change from V5.1.

## Default risk universe

Full research defaults to CORE companies with roughly:

- market cap >= **$15B**
- 20-day average dollar volume >= **$50M/day**
- public history >= **7 years** when known
- next-year EPS analyst coverage >= **10 analysts** when known

Actionable BUY labels additionally require the preferred **$25B+** large-cap tier and stronger establishment evidence.

Small/new companies can still be discovered by the broad scan, but they do not displace large CORE companies in the default research output.

## V5.2 action vocabulary

### `BUY NOW`

The large-company thesis is strong, SEC evidence is ready, independent valuation methods agree, the bear case is acceptable, and the current price is inside the required-return buy zone.

### `BUY NOW — RESET ENTRY`

The stock previously rerated hard, but a meaningful pullback/reset has reopened an entry while revisions remain supportive and valuation is resolved.

### `BUY ON PULLBACK`

The thesis is strong and valuation is resolved, but the current price is above the price required to earn the configured base-case return hurdle.

### `WATCH — DEVELOPING`

The company is worth following, but the thesis/evidence/return hurdle has not matured enough for an actionable entry.

### `TOO LATE / OVEREXTENDED`

The company may still be excellent, but the primary rerating already occurred and price has not reset enough to justify chasing it. This label is **independent of the valuation buy-zone calculation**.

### `VALUATION UNRESOLVED`

Two or more valuation methods disagree too much, or only one method is usable. V5.2 intentionally publishes **no actionable buy-below price** in this state.

### `DATA INCOMPLETE`

Required SEC evidence is missing or failed to download. This is no longer hidden inside a generic WATCH label.

### `REVIEW DATA`

A price/share-count/valuation sanity check failed.

### `SPECULATIVE WATCH`

Below the default large-established risk threshold.

### `PASS`

Insufficient risk/reward at the configured hurdle.

## Why V5.2 is different from V5.1

### 1. Thesis score and entry score are separate

V5.1 could call a strong company `WATCH` because price timing was poor. That mixed together two very different cases:

- an early thesis that is not proven yet;
- a proven thesis whose optimal entry was months ago.

V5.2 computes:

- **Thesis score**: fundamentals, revisions, valuation credibility, company quality and SEC evidence.
- **Entry score**: price maturity, 3/6/12-month rerating and distance from the 52-week high.

The dashboard displays both.

### 2. Research slots explicitly search for entries

The full-research budget is split approximately into:

- **50% entry-opportunity sleeve** — CORE companies that are not yet LATE;
- **30% challenger sleeve** — strongest large-cap fundamental/revision candidates;
- **20% late-leader diagnostic sleeve** — mature winners retained so the engine can explicitly say `TOO LATE` or identify a reset entry.

This reduces the chance that the final list is dominated by companies whose best entry already happened.

### 3. No fake midpoint between conflicting valuation models

V5.1 could combine two wildly different fair values by taking the median. With exactly two models, that is just their arithmetic midpoint and can create a precise-looking but meaningless buy zone.

V5.2 calculates an actionable blended fair value **only after**:

- at least 2 independent models are available;
- model-agreement score >= **0.60**;
- high/low base fair values are no more than **1.9x** apart;
- no critical valuation sanity flag exists.

If those gates fail, the result is `VALUATION UNRESOLVED` and the dashboard shows the individual model ranges instead of a buy price.

### 4. Memory/storage/semiconductor valuation is cycle-aware

V5.1 could treat a memory company with peak-cycle forward EPS as ordinary profitable growth and compound those earnings forward.

V5.2 recognizes:

- memory/storage/computer-hardware cycle-sensitive businesses;
- semiconductor companies with unusually large simultaneous revenue and margin swings;
- energy/materials cyclicals.

Those companies use **normalized-cycle EPS** and **normalized FCF** assumptions rather than blindly extrapolating peak forward EPS.

### 5. SEC failures are no longer silent

Earlier code could swallow filing-download errors and continue with zero documents.

V5.2 records, per ticker:

- SEC state;
- whether submissions were fetched;
- documents requested;
- documents cached;
- documents downloaded this run;
- actual error messages.

GitHub Actions requires `SEC_USER_AGENT`, checks SEC connectivity in `doctor --network`, and fails the publish if fewer than 60% of research reports have enough SEC evidence.

### 6. Buy-zone math only exists when valuation is resolved

Default base-case hurdle:

```text
15% annualized over 3 years
```

When valuation is resolved:

```text
buy_below = base_fair_value / (1 + required_base_CAGR)^3
```

When valuation is unresolved, `buy_below` is intentionally blank.

## Persistent cache

GitHub Actions persists:

```text
data/warehouse.db
data/cache/
```

Historical daily prices are reused. V5.2 changes only the deep mutable-data namespaces:

```text
yahoo:v5_2:...
sec:v5_2:...
```

So the first V5.2 run refreshes profiles/financials/analyst data/SEC submissions while still being able to reuse the large historical price warehouse from prior versions.

## Required GitHub secret

Repository → **Settings → Secrets and variables → Actions**

Create:

```text
SEC_USER_AGENT
```

Example:

```text
George Jiang your-real-email@example.com
```

This is required for the GitHub Actions research workflow.

Optional:

```text
OPENAI_API_KEY
```

The OpenAI key is only used for an additional narrative synthesis. Deterministic discovery, valuation, trust and actions do not depend on it.

## GitHub Actions

Main workflow:

```text
.github/workflows/research.yml
```

Recommended first V5.2 run:

```text
deep_candidates:       180
research_candidates:    24
force_refresh:        false
```

`force_refresh: false` is normally enough because the new `v5_2` deep-data namespaces force the incompatible mutable objects to refresh while retaining the historical price warehouse.

The workflow does this:

```text
checkout
→ restore warehouse cache
→ install
→ compile + pytest
→ require SEC_USER_AGENT
→ Yahoo + SEC network doctor
→ full research
→ validate report count + SEC evidence coverage
→ save warehouse
→ upload full artifact
→ commit published/*
```

## Streamlit

Main file:

```text
dashboard/app.py
```

The dashboard has separate tabs for:

- **Actionable now**
- **Developing**
- **Past primary entry**
- **Unresolved / data**
- **All researched**

Opening Streamlit does not download market data. It only reads the files generated by GitHub Actions:

```text
published/latest_research.json
published/latest_research.csv
published/track_record.json
published/metadata.json
```

## Local validation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dashboard,dev,llm]"
pytest -q
SEC_USER_AGENT="Your Name your@email.com" inflection-scanner doctor --network
```

## Full local run

```bash
SEC_USER_AGENT="Your Name your@email.com" \
inflection-scanner research --deep 180 --research-count 24 --top 30
```

## Important limitation

This is a research prioritization and decision-support engine, not a guarantee of returns. V5.2 is intentionally designed to **refuse false precision**: no forced BUY quota, no fake probability of profit, no midpoint buy zone from contradictory models, and no silent missing SEC evidence.
