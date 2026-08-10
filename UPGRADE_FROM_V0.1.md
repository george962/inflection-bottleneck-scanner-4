# Upgrade from V0.1

You can keep the existing `data/scanner.db`.

V0.2 performs an additive SQLite migration automatically when the database is
opened. Your old snapshots remain available.

## Upgrade

If this folder replaces the old repository:

```bash
source .venv/bin/activate
pip install -e ".[dashboard,dev]"

inflection-scanner doctor --network
pytest -q
inflection-scanner scan --top 25
```

Because your old V0.1 run used the old scoring model, the first V0.2
`score_delta_last` is not apples-to-apples. Treat that first delta as a migration
artifact. Starting with the second V0.2 scan, deltas are comparable.

## New commands

```bash
inflection-scanner explain MU
inflection-scanner changes --limit 25
inflection-scanner raw-json MU
```

## Important semantic change

The main score is now **opportunity**, not generic quality.

A very strong company can receive:
- high strength
- high extension
- only moderate opportunity

That is intentional.
