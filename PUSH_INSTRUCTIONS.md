# Push V5.4 to GitHub

This ZIP intentionally does not contain a `.git` directory.

## Replace the current repository contents while preserving history

From your existing local clone of `george962/inflection-bottleneck-scanner-4`:

```bash
git checkout -b v5.4

# Back up anything local first, then replace the working tree with the
# contents of the downloaded V5.4 folder. Do NOT copy a .git directory.

python -m pip install -e ".[dashboard,dev,llm]"
python -m compileall -q src dashboard tests
pytest -q

git add -A
git commit -m "feat: upgrade equity research engine to V5.4"
git push -u origin v5.4
```

Review the branch, then merge it into `main` through GitHub or locally.

## Fresh repository push

```bash
cd inflection-bottleneck-scanner-4-v5.4
git init
git add -A
git commit -m "feat: V5.4 equity research engine"
git branch -M main
git remote add origin https://github.com/george962/inflection-bottleneck-scanner-4.git
git push -u origin main
```

If the remote already has history, prefer the first method instead of force-pushing.
