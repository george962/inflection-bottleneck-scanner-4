# GitHub + Streamlit Setup for v5

## 1. Create or replace the repository

Unzip the v5 package so the repository root directly contains:

```text
.github/
config/
dashboard/
src/
tests/
pyproject.toml
README.md
```

Do not place the entire v5 folder inside another scanner folder.

## 2. Push to GitHub

```bash
git init
git add .
git commit -m "Large-Cap Inflection Research v5"
git branch -M main
git remote add origin <YOUR_REPO_URL>
git push -u origin main
```

If replacing an existing repository, remove/replace the old working tree first rather than merging patch folders into it.

## 3. Add SEC secret

Repository → Settings → Secrets and variables → Actions → New repository secret.

Name:

```text
SEC_USER_AGENT
```

Value example:

```text
Your Name your-email@example.com
```

Optional secret:

```text
OPENAI_API_KEY
```

## 4. Run research

Repository → Actions → **Equity Research Engine** → Run workflow.

Recommended first run:

```text
deep_candidates:       180
research_candidates:    20
force_refresh:         true
```

After the first successful v5 run, normal runs can use `force_refresh: false`.

The workflow has its own v5 cache namespace and does not reuse the old v4 Actions cache.

## 5. Confirm published files

After the workflow completes, the repository should contain:

```text
published/latest_research.json
published/latest_research.csv
published/track_record.json
published/metadata.json
```

## 6. Streamlit Community Cloud

Deploy the same GitHub repository with:

```text
Main file path: dashboard/app.py
```

The app is read-only with respect to market data. GitHub Actions does the expensive research and commits the small `published/` payload.

## 7. Normal operation

```text
GitHub Actions
    ↓
restore v5 warehouse cache
    ↓
refresh only missing/stale data
    ↓
large-cap research + valuation + conviction
    ↓
commit published/*
    ↓
Streamlit shows new results
```


## V5.1 first run

After uploading V5.1, run **Equity Research Engine** once. The Yahoo deep-data namespace changed to `v5_1`, so profile/history/analyst metadata is refreshed while the large historical price warehouse can still be reused from the V5 Actions cache.
