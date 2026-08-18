# Large-Cap Inflection Research V5.4.1

## V5.4.1 reliability hotfix

V5.4.1 fixes the failed first V5.4 production run observed on 2026-08-18. The V5.4 engine restored a V5.3 SQLite warehouse whose `research_reports` and cache tables had incompatible schemas; `CREATE TABLE IF NOT EXISTS` did not migrate those tables, so every deep-research report failed at persistence with SQLite `OperationalError`.

V5.4.1 adds:

- explicit warehouse schema version `5.4.1`;
- non-destructive V5.3 → V5.4.1 migration;
- import of legacy `price_daily` history into the canonical `prices` table;
- preservation plus best-effort import of legacy compressed research reports into versioned cohorts;
- preservation of incompatible V5.3 cache/research tables under `legacy_*` names;
- publish-health gates that fail GitHub Actions when operational failures are systemic;
- exclusion of operational failures from permanent decision and PIT ledgers;
- one-time quarantine of the known broken V5.4 zero-score/DATA_ERROR decision rows;
- corrected V5.4.1 cache/artifact/commit names in `.github/workflows/research.yml`; and
- migration/publish-health regression tests covering the exact production failure.

The V5.4 currency/ADR normalization, company-family classification, public-history parsing, and versioned outcome tracking remain in place.


V5.4.1 is a U.S.-listed equity discovery and decision-support system built around one question:

> Which established companies are improving fundamentally, and which of those still offer an attractive entry from today's price?

The engine separates **business-thesis quality** from **entry timing**, refuses to manufacture a buy zone when valuation is unresolved, and now fails closed when foreign-currency / ADR security units cannot be reconciled safely.

## What changed in V5.4 (carried forward)

V5.4 is a correctness-and-validation release.

### 1. Currency / ADR normalization is explicit

The valuation engine now carries a security-normalization contract containing:

- trading currency;
- financial-statement currency;
- financial→trading FX conversion;
- underlying shares represented by one traded share / ADR;
- resolution status and source.

If trading and financial currencies differ, V5.4 requires an explicit share/ADR ratio override by default. If FX or security-unit conversion cannot be resolved, valuation becomes:

`CURRENCY_UNIT_UNRESOLVED`

and no valuation model or buy zone is produced.

`config/security_overrides.json` contains the override registry. TSM is included as an example with a 5:1 underlying-share/ADR ratio; FX is fetched dynamically.

### 2. Company classification is narrower

Generic `Computer Hardware` is no longer treated as memory/storage. V5.4 distinguishes:

- memory/storage cyclicals;
- semiconductor growth;
- extreme semiconductor-cycle cases;
- semiconductor equipment;
- networking hardware;
- software;
- generic profitable growth;
- cyclicals;
- sectors requiring specialist valuation.

This prevents networking companies from inheriting memory-cycle assumptions simply because a broad provider labels them as computer hardware.

### 3. Public-history parsing is fixed

Yahoo can return first-trade metadata either as epoch time or as an ISO/date-time string. V5.4 supports both formats, so `years_public` no longer disappears simply because the provider returned a timestamp string.

### 4. Validation is model-versioned

V5.3 hard-coded the realized-outcome tracker to an older model cohort. V5.4 uses the active model version and does not mix V5.3/V5.4 cohorts.

Prospective outcomes now include:

- absolute realized return;
- SPY benchmark return;
- excess return;
- positive-excess-return rate;
- maximum adverse excursion;
- maximum favorable excursion;
- hit rate;
- average / median return.

### 5. Durable point-in-time ledgers

GitHub Actions cache is treated as a mutable performance cache, not as permanent evidence.

Every successful research publish appends two deduplicated files under `published/`:

- `decision_ledger.jsonl` — original model decision, price, scores, valuation state, trust and config hash;
- `pit_estimates.jsonl` — the point-in-time estimate/revision/features used in that run.

Those files are committed back to GitHub, so future validation can reconstruct the decision cohort even if `data/warehouse.db` is lost.

### 6. SEC remains optional and diagnostics are sanitized

SEC enrichment is not a recommendation gate. V5.4 also refuses to serialize raw HTTP exceptions into public research output because exceptions may contain header values, credentials, personal email addresses, or URLs with secrets.

## Decision labels

The main recommendation layer can emit:

- `BUY NOW`
- `BUY NOW — RESET ENTRY`
- `BUY ON PULLBACK`
- `WATCH — DEVELOPING`
- `TOO LATE / OVEREXTENDED`
- `VALUATION UNRESOLVED`
- `REVIEW DATA`
- `SPECULATIVE WATCH`
- `PASS`

A company is never required to receive a BUY label.

## Architecture

```text
U.S.-listed symbol directory
        ↓
batched 2-year price/liquidity scan
        ↓
market/relative-return discovery score
        ↓
entry opportunity + late diagnostic selection
        ↓
profile + quarterly/annual fundamentals
        ↓
point-in-time analyst estimates/revisions
        ↓
large-established company gate
        ↓
currency / ADR / share-unit normalization
        ├── unresolved → REVIEW DATA / no valuation
        └── resolved
              ↓
industry-aware multi-model valuation
        ↓
model agreement + sanity gates
        ↓
thesis score (business/evidence)
        +
entry score (maturity/reset/extension)
        ↓
recommendation label
        ↓
published dashboard
        +
durable decision/PIT ledgers
        +
prospective benchmark-relative track record
```

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dashboard,dev,llm]"
pytest -q
inflection-scanner doctor --network
```

Run a broad scan:

```bash
inflection-scanner research --deep 180 --research-count 24 --top 30
```

For a fast smoke test on a small explicit universe:

```bash
inflection-scanner research --tickers AAPL,MSFT,NVDA,AVGO,ANET --deep 5 --research-count 5 --top 5
```

Launch the dashboard:

```bash
streamlit run dashboard/app.py
```

## GitHub Actions

Main workflow:

```text
.github/workflows/research.yml
```

The scheduled job:

1. restores the mutable warehouse cache;
2. installs V5.4.1;
3. checks network access;
4. runs discovery and full research;
5. validates the publish;
6. runs the tests;
7. saves the mutable cache;
8. uploads the run artifact;
9. commits `published/`, including the durable decision/PIT ledgers.

`SEC_USER_AGENT` and `OPENAI_API_KEY` are optional.

If `SEC_USER_AGENT` is configured, its secret value must be only the literal SEC user-agent string, for example:

```text
Your Name your.email@example.com
```

Do not paste GitHub UI labels such as `Name:` or `Value:` into the secret.

## Validation philosophy

V5.4 does **not** claim that today's Yahoo analyst estimates can be used to create a valid historical backtest. That would introduce look-ahead bias.

The honest path is:

1. save point-in-time decisions and estimate snapshots now;
2. let those decisions mature chronologically;
3. compare outcomes with SPY and later sector benchmarks;
4. measure whether score bands and actions actually separate future returns;
5. recalibrate weights/thresholds only after enough observations exist.

## Known limitations / V5.5 candidates

V5.4 intentionally does not attempt to solve every valuation problem. Highest-value next steps are:

- peer-relative valuation;
- dedicated financial/REIT models;
- richer software/networking/semiconductor specialist models;
- earnings-call transcript evidence;
- direct industry bottleneck feeds;
- sector benchmarks;
- rank IC / decile-spread calibration;
- true historical point-in-time data if a commercial source is acquired.

## Disclaimer

This is a research and prioritization system, not a guarantee of returns or individualized financial advice. Model labels should be validated and reviewed before capital is committed.
