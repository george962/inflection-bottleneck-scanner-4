# V5 Persistence Design

## GitHub Actions cache

Stored outside Git history:

```text
data/warehouse.db
data/cache/
```

Actions cache key prefix:

```text
equity-data-v5-
```

## SQLite warehouse

`data/warehouse.db` stores:

- `price_daily`: deduplicated daily market history
- `json_cache`: TTL-based Yahoo data
- `filing_documents`: compressed SEC filing text keyed by accession
- `research_reports`: historical v5 reports used for realized-outcome tracking

## Cache schema version

Yahoo deep-data keys use:

```text
yahoo:v5_1:...
```

This intentionally separates v5 data from incompatible earlier cached objects.

## Published data

Small read-only Streamlit payloads are committed:

```text
published/latest_research.json
published/latest_research.csv
published/track_record.json
published/metadata.json
```

The large SQLite warehouse is never committed to normal Git history.
