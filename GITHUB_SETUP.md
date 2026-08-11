# GitHub + Streamlit Setup — V5.2

This ZIP is a **complete repository**, not a patch.

## Replace your existing scanner-4 working tree safely

Do not drag folders in Finder and choose Replace. That can delete files that are not present in the incoming folder.

Use `rsync` so the repository structure is merged while your existing `.git` directory is preserved:

```bash
rm -rf /tmp/scanner-v52
mkdir -p /tmp/scanner-v52
unzip -o ~/Downloads/inflection-bottleneck-scanner-v5.2.zip -d /tmp/scanner-v52

cd "/path/to/your/inflection-bottleneck-scanner-4"
rsync -av --exclude=".git" /tmp/scanner-v52/ ./

python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -e ".[dashboard,dev,llm]"
pytest -q

git status
git add -A
git commit -m "Upgrade equity research engine to v5.2"
git push origin main
```

## Required secret

GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**

Name:

```text
SEC_USER_AGENT
```

Value example:

```text
George Jiang your-real-email@example.com
```

V5.2 intentionally fails the Action if this is missing because SEC evidence is part of the recommendation gate.

Optional:

```text
OPENAI_API_KEY
```

## Run the workflow

GitHub → **Actions → Equity Research Engine → Run workflow**

Use:

```text
deep_candidates:       180
research_candidates:    24
force_refresh:        false
```

The first V5.2 run refreshes the new `yahoo:v5_2:*` and `sec:v5_2:*` objects automatically.

## What a successful run must show

The Action will fail instead of publishing misleading data when:

- fewer than 5 reports are produced;
- `SEC_USER_AGENT` is missing;
- SEC connectivity fails in doctor;
- fewer than 60% of reports have enough SEC filing evidence.

After success, confirm these files were committed:

```text
published/latest_research.json
published/latest_research.csv
published/track_record.json
published/metadata.json
```

## Streamlit

Keep the same Streamlit deployment if it already points at your repository.

Main file path:

```text
dashboard/app.py
```

After the Action commits new `published/*` files, Streamlit should update automatically. If needed use **Manage app → Reboot app**.
