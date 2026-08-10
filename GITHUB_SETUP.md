# GitHub Actions + Streamlit Setup

1. Push this repository to GitHub.
2. Add Actions secret `SEC_USER_AGENT`.
3. Optionally add `OPENAI_API_KEY`.
4. If desired, add repository variable `OPENAI_MODEL=gpt-5-mini`.
5. Ensure Actions is allowed to use `contents: write` because the workflow
   commits `published/` after a successful run.
6. GitHub → Actions → **Equity Research Engine** → **Run workflow**.
7. After the first run, verify `published/latest_research.json` is committed.
8. In Streamlit Community Cloud, create an app from this repository with
   entrypoint `dashboard/app.py`.

Architecture:

```text
GitHub Actions
  ├─ restore big warehouse from Actions cache
  ├─ update stale/missing data
  ├─ research + valuation
  ├─ save warehouse to Actions cache
  ├─ upload full artifact
  └─ commit small published/*.json
              ↓
          GitHub repo
              ↓
     Streamlit Community Cloud
```

The Streamlit app itself does not need Yahoo/SEC/OpenAI access just to display
the latest research.

If Actions cache is evicted, the next run rebuilds it. Published dashboard data
remains in Git.
