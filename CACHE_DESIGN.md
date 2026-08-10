# Cache Design

## Stored once / incrementally

- historical daily price bars: upsert by `(ticker,date)`
- SEC filing documents: keyed by `(ticker, accession)` and never redownloaded
  once present

## TTL cache

- profiles: 48h
- annual/quarterly statements: 120h
- analyst tables: 16h
- news: 8h
- SEC submissions metadata: 12h

If a live request fails but stale cached data exists, the provider uses stale
data rather than throwing away the entire research run.

## GitHub

`data/warehouse.db` is restored/saved through GitHub Actions cache. It is also
included in each workflow artifact as a recoverable backup.

Only small `published/` files are committed, preventing binary SQLite history
from bloating the Git repository.
