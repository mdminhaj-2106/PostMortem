# Simulator — Layer 2: Observed Sources

Deliberate degradation layer, built as SQL views over Layer 1, simulating fragmented real-world source systems. This is what the pipeline (Stage 1 onward) actually ingests — never Layer 1's raw tables, never `injected_events` (held out).

See [`../README.md`](../README.md) for the full simulator spec, and the design report:
- [`layer2-observed-sources-design.md`](../../../docs/02-stage-design-reports/layer2-observed-sources-design.md) — three-source model, scenario-by-scenario mechanism map

## Status

**Implemented** — 6 views across 3 sources (`billing_system`, `crm_system`, `marketing_system`), covering 6 of Stage 1's 7 reconciliation scenarios. Scenario 3 (late-arriving/mutable history) is deferred — see the design doc §2, it needs a small Layer 1 extension (`returned_day_offset` on `orders`) to be represented honestly rather than faked.

## Setup

```
cd pipeline/simulator/layer2_observed_sources
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
psql "$DATABASE_URL" -f schema_layer2.sql   # source_outages table
psql "$DATABASE_URL" -f views.sql           # the 6 source views
.venv/bin/python inject_outages.py --seed 42
```

Requires Layer 1's schema + generated episodes to already exist.

## Verify

```
.venv/bin/python test_views.py
```

Checks: a total-gap outage window has zero rows (not zeroed values), the marketing bias ratio matches the declared drift boundary (0.87 → 0.80), entity-mismatch rows exist in `v_crm_customer_mapping`, and grains genuinely differ in row count across sources.

## The 6 views

| View | Source | Demonstrates |
|---|---|---|
| `v_billing_daily_revenue` | billing_system | exact revenue/orders/AOV, daily/UTC |
| `v_billing_active_customers` | billing_system | purchase-based active (trailing 30d) |
| `v_crm_weekly_active_customers` | crm_system | broader "active" (order OR ticket), ISO week grain — scenarios 2 & 5 |
| `v_crm_customer_mapping` | crm_system | synthetic account IDs with duplicates/mismatches — scenario 6 |
| `v_marketing_daily_attributed_revenue` | marketing_system | biased revenue that silently re-biases mid-episode — scenarios 1 & 7 |
| `v_marketing_monthly_active_customers` | marketing_system | billing-cycle-month grain (day 15 start, not calendar month) — scenario 5 |

`source_outages` (populated by `inject_outages.py`) drives scenario 4 across all three sources — total gaps (missing rows, not zeros) for billing/crm, partial gaps (one metric dark) for marketing.
