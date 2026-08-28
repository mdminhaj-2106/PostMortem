# Simulator

The synthetic data foundation the whole system trains and evaluates against — there is no public dataset labeled "this revenue drop was caused by X," so this isn't a fallback, it's what makes every ML claim in the pitch checkable rather than asserted.

**Status:** Layer 1 design complete — see [`docs/02-stage-design-reports/simulator-layer1-ground-truth-design.md`](../../docs/02-stage-design-reports/simulator-layer1-ground-truth-design.md). Not yet built.

## Two layers

- **`layer1_ground_truth/`** — a generative engine, run once, simulating a fake business over time via structural equations (`traffic = f(marketing_spend, seasonality, noise)`, `revenue = orders × avg_order_value`, `churn = f(support_complaints, satisfaction, competitor_activity, noise)`, etc.), driving multiple related KPIs simultaneously with known causal events injected at known timestamps. Perfect, atomic-grain, complete. **Held out from the pipeline entirely** — used only for training labels and scoring (never fed to Stage 1+ as if it were real input). See [`docs/01-architecture/architecture-report.md`](../../docs/01-architecture/architecture-report.md) §2 and [`docs/02-stage-design-reports/stage1-reconciliation-design.md`](../../docs/02-stage-design-reports/stage1-reconciliation-design.md) §2.

- **`layer2_observed_sources/`** — a deliberate degradation layer built as literal SQL views over Layer 1, simulating what real fragmented source systems expose: different grains/cadences, different definitions of superficially-same concepts, injected staleness/bias/missing windows/conflicting values/calendar differences/duplicate keys. Because these are real SQL views (not static tables), Stage 1 can parse their defining queries for lineage — this is the mechanism behind most of Stage 1's seven reconciliation scenarios. **This is what the pipeline actually ingests.**

**Injected causal events to implement** (from the architecture report §2): product outage → churn ramp; marketing cut → immediate broad-based revenue fall; competitor launch → segment-concentrated churn; inventory shortage → SKU-concentrated order drop; pure-noise episodes with no injected cause (train/test the "ability to decline" behavior).

**Optional hybrid enrichment:** overlay injected shocks onto Olist (real Brazilian e-commerce order + review data) for less-synthetic-reading demo text, while still controlling ground truth via the injected shock.

No code yet.
