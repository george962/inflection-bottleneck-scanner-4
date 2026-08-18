# GitHub Actions setup — V5.3

## Required secrets

None.

V5.3 can run fully without SEC credentials.

## Optional secrets

### SEC_USER_AGENT

Optional. If supplied, use a single-line identity such as:

```text
George Jiang your-email@example.com
```

If omitted, SEC filing enrichment is skipped with no trust penalty and no workflow failure.

### OPENAI_API_KEY

Optional. Enables the narrative evidence synthesis. The deterministic scanner, valuation, and action engine do not require it.

## First run

Push the complete V5.3 repository to your existing GitHub repository, then open:

```text
Actions -> Equity Research Engine -> Run workflow
```

Use:

```text
deep_candidates: 180
research_candidates: 24
force_refresh: false
```

The workflow restores prior market-history caches where possible, tests the repository, runs the network doctor, executes research, validates the published dataset, saves the updated cache, uploads an artifact, and commits `published/` back to `main`.

## Expected doctor behavior without SEC

```text
SEC optional enrichment   OK   Not configured; skipped...
```

That is a successful state in V5.3.

## Streamlit

Keep the existing Streamlit app pointed at:

```text
dashboard/app.py
```

After the Action commits new `published/` results, the dashboard updates from the repository commit.
