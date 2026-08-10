# Roadmap

## V1 — runnable scanner
Status: included in this repository.

- Yahoo price/fundamental/estimate ingestion
- transparent feature engineering
- 7-component score
- SQLite snapshots
- CLI
- dashboard
- SEC filing metadata
- market-only walk-forward baseline
- CI
- scheduled GitHub scan

## V0.2 — opportunity layer
Status: included.

- opportunity vs. strength split
- no neutral-50 treatment for missing data
- expectation-gap proxy
- extension/maturity penalty
- stage/action labels
- why-now / missing-confirmation / risk / trigger / invalidation
- score delta versus previous scan
- SQLite migration from V0.1

## V0.3 — richer change detector

Add:
- score delta 1d / 7d / 30d / 90d
- rank delta
- new-top-20 alerts
- component-level deltas
- "what changed?" report
- score persistence

This is likely the highest-value immediate extension after collecting several weeks of snapshots.

## V1.2 — filing and earnings-call language

Extract structured observations:

```json
{
  "pricing": {"direction":"up","confidence":0.91},
  "lead_times": {"direction":"longer","confidence":0.82},
  "capacity": {"state":"constrained","confidence":0.88},
  "backlog": {"direction":"up","confidence":0.84},
  "qualification": {"state":"new_customer_ramp","confidence":0.76}
}
```

Store evidence spans and source timestamps.

Do not let an LLM directly create a buy/sell score. It should create structured, auditable observations.

## V1.3 — supply-chain graph

Entities:
- company
- product
- end market
- component
- manufacturing process
- supplier
- customer
- capacity asset
- geography

Edges:
- supplies
- consumes
- substitutes_for
- constrained_by
- manufactured_at
- capacity_expands_at
- customer_of

The scanner should answer:

> If demand for X increases 50%, which second-order suppliers have the highest earnings torque and the slowest supply response?

## V1.4 — direct bottleneck feeds

Examples:
- DRAM/NAND/HBM contract/spot pricing
- HDD nearline shipment data
- optical 800G/1.6T demand
- foundry utilization
- advanced packaging capacity
- transformer/switchgear lead times
- data-center power availability
- generation capacity pricing
- server shipment/backlog data

## V2 — point-in-time research warehouse

Canonical tables:

```text
security_master
prices_daily
fundamentals_pit
estimate_consensus_pit
estimate_revisions_pit
filings
transcripts
industry_observations
supply_chain_edges
feature_snapshots
forward_returns
model_predictions
```

Prefer Parquet for research datasets and SQLite/Postgres for metadata/indexes.

## V2.1 — cross-sectional model

Candidate models:
- LightGBM / XGBoost
- regularized linear ranker
- monotonic gradient boosting
- ensemble

Targets:
- 3M/6M/12M sector-relative return
- top-decile probability
- >20% sector outperformance probability
- drawdown risk

Important features:
- acceleration, not just levels
- revision velocity
- revision breadth
- margin torque
- estimate surprise persistence
- price confirmation
- supply-response lead time
- graph-derived exposure

## V2.2 — industry-specific specialists

A universal model misses important economics.

Specialists:
- memory/storage cycle
- semicap
- servers/networking
- optics
- power/grid
- turnarounds
- commodities/cyclicals
- structural growth/new products

Final rank can be an ensemble of generic + specialist models.

## V3 — research agent

The agent should:
1. notice a new bottleneck
2. identify exposed public companies
3. calculate earnings sensitivity
4. compare expectations vs. plausible scenarios
5. collect contradictory evidence
6. update the knowledge graph
7. propose candidates for human review

It should never silently rewrite historical observations or training data.
