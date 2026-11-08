---
name: e2e-test
description: Plan and run end-to-end verification for complete user journeys across the simulator, pipeline stages, database, and (once built) API/frontend.
---

## Objective

Verify a complete journey works across all layers currently implemented: simulator generation → live Neon database → (once built) pipeline stage → (once built) API → (once built) frontend. Right now that means: simulator → database, since nothing past Layer 2 exists yet.

## Environment setup

```bash
cd pipeline/simulator/layer1_ground_truth   # or the relevant module
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# DATABASE_URL must point at the shared Neon project (see .env.example)
```

## Journey matrix (current)

| Journey | Layers touched | How to verify |
|---|---|---|
| Generate an episode, query its KPIs | Layer 1 generator → Neon | `generate.py`, then the worked `SELECT` queries in `docs/02-stage-design-reports/stage0-simulator-database-schema.md` §3 |
| An injected event is visible in the raw data | Layer 1 → Neon | Query `injected_events` + the corresponding `daily_state`/`orders` window, confirm the onset shape matches the event's `onset_type` |
| A reconciliation scenario is genuinely reproducible | Layer 2 views → Neon | `pipeline/simulator/layer2_observed_sources/test_views.py` |

Fill in new rows as Stage 1+ get built — each stage should add a journey here once it can be queried end-to-end.

## Validation layers

Unit/self-check (`test_*.py`) → live-database verification (query Neon directly, don't trust the code's stated intent) → (once built) API integration → (once built) browser.

## Report format

Environment/branch, test data created (which episode IDs, whether `--reset` was used), journeys passed/failed, evidence for any failure, follow-up issues opened.

## When to use

Before merging any PR that touches the simulator schema or a Layer 2 view, before any stage's first implementation is considered "done," when debugging a discrepancy between expected and actual data.
