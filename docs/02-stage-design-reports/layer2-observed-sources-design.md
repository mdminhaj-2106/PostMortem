# Simulator — Layer 2: Observed Sources — Design Report

**Status:** Design complete, pre-implementation. Builds on the Layer 1 ground-truth generator (already implemented and populated) and directly instantiates the seven scenarios from [`stage1-reconciliation-design.md`](stage1-reconciliation-design.md) — this doc maps each scenario to a concrete SQL mechanism instead of restating the scenario itself.

---

## 1. Three sources over one truth

Each source is a Postgres view (or small set of views) over Layer 1's atomic tables, deliberately exposing a different, imperfect slice of the same underlying business:

| Source | Owns | Grain | Definition quirk |
|---|---|---|---|
| `billing_system` | revenue, orders, AOV, active customers | daily, UTC day | Purchase-based "active" — the closest thing to ground truth |
| `crm_system` | active customers, identity | weekly (ISO, Monday-start) | "Active" = order **or** support ticket in trailing 30 days — broader than billing's |
| `marketing_system` | attributed revenue, active customers | billing-cycle month (30-day blocks starting day 15, not calendar months) | Revenue is a biased fraction of true revenue, and the bias itself silently changes partway through the episode |

## 2. Scenario → mechanism map

**Scenario 1 — Conflicting Values.** `v_marketing_daily_attributed_revenue` reports true revenue × a declared bias factor (~0.87, i.e. attribution misses ~13% — realistic for last-click attribution missing direct/organic traffic) against `v_billing_daily_revenue`'s exact number. Two sources, same underlying fact, genuinely different numbers, declared bias direction (matches Stage 1's own point that bias should be *declared*, not inferred).

**Scenario 2 — Definitional Mismatch.** `v_crm_weekly_active_customers` counts anyone with an order **or** a support ticket in the trailing 30 days; `v_billing_active_customers` counts only actual purchasers (Layer 1's own churn semantics). Same label ("active customers"), genuinely different construct — the exact CRM-vs-billing example from the stage 1 doc.

**Scenario 3 — Late-Arriving / Mutable History. Deferred, not implemented in this pass.** This scenario is fundamentally temporal — a source's answer for a past day has to change between two query times. A view over a dataset generated once and never revised can't produce that honestly; faking it (e.g. random jitter on "recent" days) would be indistinguishable from ordinary noise and wouldn't test what Stage 1 actually needs to detect. The real fix is a small Layer 1 extension: add `returned_day_offset` (nullable) to `orders`, so `billing_system` can expose both an as-issued view and an as-it-stands-today view that genuinely diverge. Not built now — flagged as a follow-up requiring a Layer 1 schema change, same as the reliability/churn issues found earlier in this project.

**Scenario 4 — True Gaps vs. Estimable Gaps.** A new `source_outages(episode_id, source_name, metric_name, start_day_offset, end_day_offset)` table declares suppression windows. `metric_name IS NULL` = the whole source goes dark for that window (**total gap** — `billing_system` and `crm_system` use this; a missing row, not a zero, exactly matching the "this is zero data, not low-resolution data" distinction from the stage 1 doc). `metric_name = 'attributed_revenue'` on `marketing_system` = **partial gap** — attributed revenue goes dark while the source's other metric keeps reporting, the "one field missing, correlated fields present" sub-case.

**Scenario 5 — Calendar Misalignment.** Three different conventions live side by side: `billing_system` is plain daily/UTC, `crm_system` buckets into ISO weeks (Monday-start), `marketing_system` buckets into 30-day billing-cycle blocks starting on day 15 (not calendar months). No two sources agree on "what period is this." (Sub-day timezone-cutoff misalignment — the other example named in the stage 1 doc — isn't implemented: Layer 1's atomic grain is whole-day, not timestamped, so there's no sub-day boundary to shift. Honest scope limit, not faked.)

**Scenario 6 — Entity / Join-Key Mismatch.** `v_crm_customer_mapping` generates a synthetic `crm_account_id` per customer, deterministically seeded off `customer_id` (via `hashtext`, so it's reproducible, not re-randomized per query): ~2% of customers get an account id that's silently off-by-one (points to the *wrong* real customer — a data-entry mismatch), and ~3% get a second, additional synthetic id (an unmerged duplicate record for the same real person). Exactly the messy, multi-identifier-per-entity problem the Identity Resolution Graph exists to resolve.

**Scenario 7 — Silent Definitional Drift.** `v_marketing_daily_attributed_revenue`'s bias factor itself changes partway through the episode (0.87 for the first half, 0.80 for the second — nobody flags it) — same mechanism as scenario 1, doing double duty, which is realistic: a marketing team tightening or loosening its attribution model without announcing it is exactly this failure mode. **Honest limitation:** the stage 1 doc's Level-1 evidence ("diff the source's own SQL over time") genuinely can't be tested here — our views are static artifacts generated once, not a live system whose defining query changes on a real calendar. What *is* testable is Level 2/3 (statistical changepoint in the metric itself, unexplained by causally-connected neighbors) — which is the harder, more honest version of the scenario anyway.

## 3. New Layer 2 objects

```sql
source_outages
  outage_id, episode_id, source_name, metric_name (nullable), start_day_offset, end_day_offset
```

Populated by a small script (`inject_outages.py`), not hand-authored: for each (episode, source) pair, ~25% chance of one outage window, 70/30 split between partial (specific metric, 5–10 days) and total (whole source, 3–7 days) — knobs, same spirit as Layer 1's.

Six views, all `CREATE OR REPLACE VIEW` over the existing 7 Layer 1 tables plus `source_outages` — no other new tables. Full DDL lives in `views.sql`, not duplicated here (same reasoning as the Stage 0 schema doc: two copies of the same SQL is exactly the kind of drift this whole system exists to catch).

## 4. What Stage 1 actually gets to work with

Stage 1 queries these 6 views — never Layer 1's raw tables directly, and never `injected_events` (held out, scoring-only). This is the first point in the pipeline where "the same fact reported three different ways" is a real, queryable condition instead of a claim in a slide.
