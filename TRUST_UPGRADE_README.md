# Trust / Established-Company Upgrade

This is a **drop-in patch for the existing repository**. It does not create a new repository.

## What it fixes

The previous dashboard could produce outputs such as:

- a very small / recently public company receiving BUY;
- an extreme modeled CAGR being treated as high-confidence;
- a positive bear-case return displayed as "bear downside";
- one valuation formula being enough to support a BUY;
- fixed 25/50/25 scenario weights being shown as if they were a real probability of profit.

## New default company policy

### CORE

Normal BUY is restricted to companies meeting all of:

- market cap >= $10B
- public history >= 5 years
- next-year EPS analyst coverage >= 8 analysts

### MIDCAP

- market cap >= $5B
- public history >= 3 years
- analyst coverage >= 5

MIDCAP companies can still be researched, but the normal BUY gate is stricter.

### SPECULATIVE

Everything below those thresholds. SPECULATIVE companies are excluded from full research by default, although they remain in broad discovery files.

## Discovery change

30% of deep-analysis slots are reserved for high-dollar-volume challengers. This prevents the system from becoming a small-cap novelty screener and gives established names a route into deep research even if their raw early-discovery score is lower.

## BUY now requires

- no critical data anomaly;
- CORE established-company status;
- trust score >= 80;
- adequate data coverage;
- recent SEC evidence;
- at least 2 usable valuation methods;
- valuation-method agreement >= 0.55;
- scenario-weighted 3Y CAGR >= 18%;
- base-case CAGR >= 12%;
- bear-case return >= -35%;
- scenario support weight >= 75%.

## Important terminology changes

### scenario_support_weight

This replaces the dashboard's `P(profit)` language. The fixed bear/base/bull weights are NOT statistically calibrated probabilities.

### bear_return

The previous dashboard called this `bear_downside`. That was incorrect when the bear fair value was ABOVE the current price. The dashboard now displays the signed bear-case return.

## Extreme-upside sanity gate

The system changes the decision to `REVIEW DATA` if, for example:

- expected CAGR > 50%;
- expected fair value > 3x current price;
- even the bear case is >100% above current price;
- current price / next-year EPS implies an implausibly tiny forward P/E;
- price, market cap, and share count disagree materially.

This is specifically designed to stop a result like a 96% annualized return from being shown as a trustworthy HIGH-confidence BUY without validation.

## Multi-model valuation

When possible, the engine now uses:

- forward EPS / exit multiple;
- normalized-cycle EPS for cyclicals;
- FCF-yield valuation;
- forward revenue valuation only when earnings are not useful.

Scenario fair values are the MEDIAN of available methods, not the output of one formula. A normal BUY requires at least two usable methods.

## Apply to your existing repository

Unzip this patch over the root of your existing repo and overwrite matching files.

Then run:

```bash
pip install -e ".[dashboard,dev,llm]"
pytest -q

git add .
git commit -m "Add trust-gated established-company research"
git push
```

You do **not** create another repo.

## GitHub Actions

The workflow path stays the same:

```text
.github/workflows/research.yml
```

Run:

```text
Actions → Equity Research Engine → Run workflow
```

The new default deep-candidate count is 160 so the final research stage has enough larger/liquid companies to choose from.

## Streamlit

Your existing Streamlit deployment stays connected to the same GitHub repo. After GitHub Actions commits a new `published/latest_research.json`, the existing Streamlit app updates from that commit.
