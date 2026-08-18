# Push V5.4.1 to the existing repository

The safest path is to apply the hotfix into the existing clone so Git history, the live warehouse, and published history are preserved.

```bash
# From the extracted V5.4.1 folder:
./APPLY_TO_EXISTING_REPO.sh /path/to/inflection-bottleneck-scanner-4

cd /path/to/inflection-bottleneck-scanner-4
python -m pip install -e ".[dashboard,dev,llm]"
python -m compileall -q src dashboard tests
pytest -q

git status
git add -A
git commit -m "fix: V5.4.1 warehouse migration and publish health"
git push origin main
```

`APPLY_TO_EXISTING_REPO.sh` uses `rsync -a`, so hidden `.github/` files are copied. It preserves `.git/`, `data/warehouse.db`, `data/cache/`, and `published/`.

After pushing, run **Actions → Equity Research Engine → Run workflow**. The first Action should show a `Verify and migrate warehouse schema` step and commits should say `publish V5.4.1 equity research`, not V5.3.
