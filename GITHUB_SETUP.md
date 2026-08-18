# GitHub Setup — V5.4.1

## Important: copy the hidden `.github` directory

The failed upgrade retained the old V5.3 workflow because `.github` is hidden on many systems. Do not drag only visible files into the repo. Use `APPLY_TO_EXISTING_REPO.sh` or an equivalent `rsync -a` command so `.github/workflows/research.yml` is replaced.

## Existing repository

From the extracted V5.4.1 folder:

```bash
./APPLY_TO_EXISTING_REPO.sh /path/to/your/existing/inflection-bottleneck-scanner-4
```

This intentionally preserves:

- `.git/`;
- `data/warehouse.db`;
- `data/cache/`;
- `published/`.

Preserving the warehouse is safe because V5.4.1 migrates it in place. Preserving `published/` allows the first V5.4.1 run to quarantine the known broken V5.4 ledger rows.

Then run:

```bash
cd /path/to/your/existing/inflection-bottleneck-scanner-4
python -m pip install -e ".[dashboard,dev,llm]"
pytest -q
git add -A
git commit -m "fix: V5.4.1 warehouse migration and publish health"
git push
```

## GitHub Actions

Open **Actions → Equity Research Engine → Run workflow**. For the first corrected run use:

```text
deep_candidates: 180
research_candidates: 24
force_refresh: false
```

The `Verify and migrate warehouse schema` step runs before research. The workflow will fail red if fewer than 5 reports succeed or more than 25% of requested reports fail operationally.

## Optional secrets

`SEC_USER_AGENT` remains optional and must contain only the literal SEC-compatible user-agent value. `OPENAI_API_KEY` and `OPENAI_MODEL` remain optional.
