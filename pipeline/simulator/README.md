# Simulator

The synthetic data foundation the whole system trains and evaluates against — there is no public dataset labeled "this revenue drop was caused by X," so this isn't a fallback, it's what makes every ML claim in the pitch checkable rather than asserted.

**Status:** built and populated. Design docs: [`simulator-layer1-ground-truth-design.md`](../../docs/02-stage-design-reports/simulator-layer1-ground-truth-design.md), [`stage0-simulator-database-schema.md`](../../docs/02-stage-design-reports/stage0-simulator-database-schema.md).

Live in Neon (`generate.py` run once, fixed seed — the data is frozen, not regenerated per query):

| Table | Rows |
|---|---|
| `episodes` | 150 (120 days each) |
| `orders` | 1,355,626 |
| `customers` | 1,237,910 |
| `support_tickets` | 764,537 |
| `daily_state` | 18,000 |
| `injected_events` | 152 — **the held-out answer key** |
| `source_outages` | 112 |

Layer 2 adds no stored rows: it is 11 SQL views (plus the one `source_outages` table, which has to be stored because outage windows are drawn randomly at injection time and cannot be recomputed from `orders`). Views are deterministic — the same query on the same episode returns identical rows forever, since the only "randomness" (`hashtext`-based ID corruption, the 0.87/0.80 attribution bias) is a pure function of already-fixed data.

## Two layers

- **`layer1_ground_truth/`** — a generative engine, run once, simulating a fake business over time via structural equations (`traffic = f(marketing_spend, seasonality, noise)`, `revenue = orders × avg_order_value`, `churn = f(support_complaints, satisfaction, competitor_activity, noise)`, etc.), driving multiple related KPIs simultaneously with known causal events injected at known timestamps. Perfect, atomic-grain, complete. **Held out from the pipeline entirely** — used only for training labels and scoring (never fed to Stage 1+ as if it were real input). See [`docs/01-architecture/architecture-report.md`](../../docs/01-architecture/architecture-report.md) §2 and [`docs/02-stage-design-reports/stage1-reconciliation-design.md`](../../docs/02-stage-design-reports/stage1-reconciliation-design.md) §2.

- **`layer2_observed_sources/`** — a deliberate degradation layer built as literal SQL views over Layer 1, simulating what real fragmented source systems expose: different grains/cadences, different definitions of superficially-same concepts, injected staleness/bias/missing windows/conflicting values/calendar differences/duplicate keys. Because these are real SQL views (not static tables), Stage 1 can parse their defining queries for lineage — this is the mechanism behind most of Stage 1's seven reconciliation scenarios. **This is what the pipeline actually ingests.**

**Injected causal events** (from the architecture report §2): product outage → churn ramp; marketing cut → immediate broad-based revenue fall; competitor launch → segment-concentrated churn; inventory shortage → SKU-concentrated order drop; pure-noise episodes with no injected cause (train/test the "ability to decline" behavior).

**Hybrid enrichment (done):** the generator is Olist-bootstrapped — real Brazilian e-commerce product categories, price distributions, and 27 real state codes (`olist_stats.json`, `bootstrap.py`), with ground truth still controlled by the injected shock.

## Rebuild

```bash
psql "$DATABASE_URL" -f layer1_ground_truth/schema.sql
psql "$DATABASE_URL" -f layer2_observed_sources/schema_layer2.sql
.venv/bin/python layer1_ground_truth/generate.py      # regenerates Layer 1 (slow)
.venv/bin/python layer2_observed_sources/inject_outages.py
psql "$DATABASE_URL" -f layer2_observed_sources/views.sql   # views only — safe, no data touched
```

Re-applying `views.sql` alone changes what every consumer sees immediately without regenerating anything, so it is the cheap path for a Layer 2 fix — and it hits the shared Neon DB, so tell the team when you run it.
