# V5.3 Persistence Design

## GitHub Actions cache

Stored outside normal Git history:

```text
data/warehouse.db
data/cache/
```

V5.3 writes cache keys with prefix:

```text
equity-data-v5-2-
```

The restore step can fall back to earlier V5/V4 cache prefixes so the large historical price warehouse can be reused.

## SQLite warehouse

`data/warehouse.db` stores:

- `price_daily`: deduplicated daily market history
- `json_cache`: TTL-based mutable data
- `filing_documents`: compressed SEC filing text keyed by accession
- `research_reports`: historical research reports used for realized-outcome tracking

## Deep mutable-data namespaces

Yahoo:

```text
yahoo:v5_3:profile:TICKER
yahoo:v5_3:qfin:TICKER
yahoo:v5_3:afin:TICKER
yahoo:v5_3:analyst:TICKER
yahoo:v5_3:news:TICKER
```

SEC:

```text
sec:v5_3:ticker_map
sec:v5_3:submissions:TICKER
```

This forces V5.3 to refresh data whose semantics changed without throwing away the large daily-price cache.

SEC filing documents themselves remain immutable by accession number and are reused once downloaded.

## Published data

Small read-only Streamlit payloads are committed:

```text
published/latest_research.json
published/latest_research.csv
published/track_record.json
published/metadata.json
```

The large SQLite warehouse is not committed to normal Git history.
