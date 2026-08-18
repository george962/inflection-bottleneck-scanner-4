# V5.4 Cache and Persistence Design

`data/warehouse.db` is a mutable acceleration cache and local research database. It is suitable for GitHub Actions cache restoration but is **not** the only permanent evidence store.

Permanent compact evidence is written under `published/`:

- `decision_ledger.jsonl`
- `pit_estimates.jsonl`
- `latest_research.json`
- `latest_research.csv`
- `metadata.json`
- `track_record.json`

The GitHub workflow commits these files after each successful run. Therefore a lost or evicted Actions cache does not erase the original model decisions or PIT estimate snapshots.
