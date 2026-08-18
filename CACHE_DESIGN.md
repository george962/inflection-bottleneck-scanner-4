# V5.4.1 Cache and Persistence Design

## Canonical schema

`data/warehouse.db` now records `warehouse_meta.schema_version = 5.4.1`. The active tables are:

- `prices` — canonical daily OHLCV history;
- `json_cache` — mutable JSON acceleration cache;
- `research_reports` — model-versioned research cohorts;
- `warehouse_meta` — schema metadata.

## Migration from V5.3

On first open of an older warehouse, V5.4.1:

1. creates the V5.4.1 canonical tables;
2. imports `price_daily` rows into `prices` with `INSERT OR IGNORE`;
3. renames incompatible V5.3 `json_cache` to `legacy_json_cache_v53` (or a suffix if needed);
4. renames incompatible V5.3 `research_reports` to `legacy_research_reports_v53`;
5. best-effort decompresses legacy report payloads and imports them into the new versioned `research_reports`; and
6. records schema version `5.4.1`.

Legacy tables are intentionally preserved so migration is non-destructive. Subsequent opens see the current schema version and do not re-import the old price table.

## Durable published evidence

The mutable SQLite warehouse is still only an acceleration/research database. Permanent compact evidence is committed under `published/`:

- `decision_ledger.jsonl`;
- `pit_estimates.jsonl`;
- `quarantined_operational_failures.jsonl` when needed;
- `latest_research.json`;
- `latest_research.csv`;
- `metadata.json`;
- `track_record.json`.

Operational pipeline failures are never appended to decision/PIT ledgers. The known broken V5.4 placeholders are moved into the quarantine file on the next V5.4.1 run.
