# Simulator — Layer 1: Ground Truth

Perfect, atomic-grain, complete generating engine. Run once. Held out from the pipeline entirely — used only for training labels and scoring against.

See [`../README.md`](../README.md) for the full simulator spec, and the design reports:
- [`simulator-layer1-ground-truth-design.md`](../../../docs/02-stage-design-reports/simulator-layer1-ground-truth-design.md) — episode/event design, Olist real-data grounding
- [`stage0-simulator-database-schema.md`](../../../docs/02-stage-design-reports/stage0-simulator-database-schema.md) — schema rationale + ER diagram

## Status

**Schema implemented** (`schema.sql`) — Postgres, hosted on Neon so the team shares one live database from day 1 instead of everyone generating their own local file.

Generator script (fills these tables via the structural equations + Olist bootstrap) — not yet built.

## Apply the schema

```
psql "$DATABASE_URL" -f schema.sql
```

`DATABASE_URL` is the team's Neon connection string (see `.env.example` at the repo root). Verify it landed:

```
psql "$DATABASE_URL" -c '\dt'
```

should list all 7 tables: `episodes`, `customers`, `products`, `daily_state`, `orders`, `support_tickets`, `injected_events`.
