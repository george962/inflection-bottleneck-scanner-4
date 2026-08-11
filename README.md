# Large-Cap Inflection Research v5.3

V5.3 is a large-cap stock discovery and decision-support system built around one question:

> Which established companies are improving fundamentally **and** still offer an attractive entry from today's price?

It does **not** require SEC access. SEC filings are optional enrichment only.

## Core philosophy

The system deliberately separates two questions:

1. **Is this a strong investment thesis?**
2. **Is this still a good entry, or did the primary rerating already happen?**

This lets the output distinguish:

- `BUY NOW`
- `BUY NOW — RESET ENTRY`
- `BUY ON PULLBACK`
- `WATCH — DEVELOPING`
- `TOO LATE / OVEREXTENDED`
- `VALUATION UNRESOLVED`
- `REVIEW DATA`
- `SPECULATIVE WATCH`
- `PASS`

A company is never required to receive a BUY label. If nothing clears the configured hurdles, the correct output is no BUY.

## Default risk universe

The final recommendation layer is intentionally biased toward established institutional-scale companies rather than obscure small caps.

### CORE research company

Default requirements are approximately:

- market cap >= $15B;
- 20-day average dollar volume >= $50M/day;
- preferably 7+ years public when reliable metadata exists;
- preferably 10+ forward-earnings analysts.

### Actionable BUY company

Normal BUY decisions additionally prefer:

- market cap >= $25B;
- strong analyst coverage / established-company evidence;
- high data trust;
- at least two usable valuation models;
- valuation models that agree sufficiently;
- required forward return from **today's price**;
- acceptable bear case;
- an entry that is not already overextended, unless a meaningful reset reopened the window.

Small/new names may still appear in broad discovery, but they cannot become a normal large-cap BUY.

## Why SEC is optional in v5.3

The core engine already uses:

- historical prices and liquidity;
- market cap and share-count cross-checks;
- quarterly/annual financial statements;
- revenue and margin acceleration;
- free cash flow;
- analyst EPS/revenue estimates;
- 7/30/90-day estimate revisions;
- revision breadth and earnings surprises;
- analyst coverage;
- multiple valuation methods;
- current-price maturity / rerating / reset logic;
- cached news headlines;
- realized forward track record of prior model actions.

SEC filings can add useful company-specific detail, but V5.3 treats them as a supplement. If `SEC_USER_AGENT` is absent or malformed:

- GitHub Actions still runs;
- trust receives **no SEC absence penalty**;
- BUY/WATCH/TOO LATE decisions continue normally;
- the dashboard simply shows SEC enrichment as unavailable.

If SEC is configured and works, filing evidence is incorporated as a small supplemental component and can surface risks.

## Valuation credibility

V5.3 will not manufacture a precise buy zone from contradictory models.

When multiple valuation models disagree beyond the configured gate, the result is:

`VALUATION UNRESOLVED`

and the dashboard shows the model range rather than treating the midpoint as a real fair value.

Memory/storage/semiconductor cyclicals use normalized-cycle logic rather than simply compounding peak forward EPS.

## Entry timing

A strong business can still be a poor entry.

The engine explicitly models:

- price maturity;
- 1/3/6/12-month returns;
- distance from the 52-week high;
- overextension;
- large prior rerating;
- meaningful post-rerating resets;
- whether estimates remain supportive after a reset.

That allows an excellent company to be classified `TOO LATE / OVEREXTENDED` rather than hidden inside a generic WATCH bucket.

## Persistent cache

The research warehouse is stored at:

```text
data/warehouse.db
```

Historical market data is retained and updated incrementally. Yahoo profile/fundamental/analyst/news data uses TTL caching. GitHub Actions restores and saves the warehouse cache between runs.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dashboard,dev,llm]"
pytest -q
inflection-scanner doctor --network
```

No SEC secret is required.

Then run:

```bash
inflection-scanner research --deep 180 --research-count 24 --top 30
streamlit run dashboard/app.py
```

## GitHub Actions

Main workflow:

```text
.github/workflows/research.yml
```

Run from GitHub:

```text
Actions -> Equity Research Engine -> Run workflow
```

Recommended defaults:

```text
deep_candidates: 180
research_candidates: 24
force_refresh: false
```

`SEC_USER_AGENT` is optional. If you already created the secret, you may keep it; if it is absent, the workflow simply skips SEC enrichment.

The workflow validates that a non-empty, structurally valid research publish was produced. It does **not** require any percentage of companies to have SEC filings.

## Streamlit

Use:

```text
dashboard/app.py
```

The Streamlit app reads the committed files under `published/`; opening the dashboard does not rerun the market scanner.

## Track record

V5.3 records prior actions and evaluates realized 90/180/365-day outcomes as enough time passes. Scenario weights are not called probabilities. The forward realized record is the empirical evidence that matters over time.

## Disclaimer

This is a research and prioritization system, not a guarantee of returns or individualized financial advice. BUY labels are model decisions under configured assumptions and should still be reviewed before capital is committed.
