# Simulator — Layer 1: Ground Truth

Perfect, atomic-grain, complete generating engine. Run once. Held out from the pipeline entirely — used only for training labels and scoring against.

See [`../README.md`](../README.md) for the full simulator spec, and the design reports:
- [`simulator-layer1-ground-truth-design.md`](../../../docs/02-stage-design-reports/simulator-layer1-ground-truth-design.md) — episode/event design, Olist real-data grounding
- [`stage0-simulator-database-schema.md`](../../../docs/02-stage-design-reports/stage0-simulator-database-schema.md) — schema rationale + ER diagram

## Status

**Schema + generator implemented.** Postgres, hosted on Neon so the team shares one live database from day 1 instead of everyone generating their own local file.

## Setup

```
cd pipeline/simulator/layer1_ground_truth
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
psql "$DATABASE_URL" -f schema.sql   # apply the schema once
```

`DATABASE_URL` is the team's Neon connection string (see `.env.example` at the repo root). Verify the schema landed:

```
psql "$DATABASE_URL" -c '\dt'
```

should list all 7 tables: `episodes`, `customers`, `products`, `daily_state`, `orders`, `support_tickets`, `injected_events`.

## Generate episodes

```
.venv/bin/python generate.py --n-episodes 400 --n-days 120 --seed 42 --reset
```

`--reset` truncates all 7 tables first — omit it to append more episodes to what's already there. Each episode is bootstrap-grounded in real Olist e-commerce statistics (`olist_stats.json` — see `bootstrap.py`) and gets 0–3 injected causal events (product outage, marketing cut, competitor launch, inventory shortage — see `generate.py`'s event model, which implements the design doc's severity/onset/mitigation/chaining rules).

Offline sanity check (no DB needed, runs against the generation logic directly):

```
.venv/bin/python test_generate.py
```
