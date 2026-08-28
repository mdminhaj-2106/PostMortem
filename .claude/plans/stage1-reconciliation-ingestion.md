# Plan: Stage 1 — Data Reconciliation & Ingestion

**Design report:** `docs/02-stage-design-reports/stage1-reconciliation-design.md` (complete, seven scenarios, escalation-ladder detail per scenario — read that first, this plan translates it into buildable steps, doesn't restate it).
**Priority:** next up — nothing else is blocking it, and everything downstream (Stage 2+) depends on Stage 1's output contract existing.
**Branch:** `feature/stage1-reconciliation-ingestion` off `develop`.
**Track:** `stage1-reconciliation` (per the feature issue template).

## Outcome (testable)

Given a KPI (starting with `revenue`) and an episode, Stage 1 queries Layer 2's views, runs the applicable escalation ladder per scenario, and emits one `ReconciledValue` row per (episode, day) with a real confidence tier — not just "it runs," but: querying `v_billing_daily_revenue` vs `v_marketing_daily_attributed_revenue` for the same episode/day produces a materiality-gated, bias-corrected canonical value with the *right* confidence tier for the situation (exact when sources agree, triangulated/declared-unresolved when they genuinely conflict past what bias-correction explains).

## Scope

**In (first implementation slice):**
- Scenario 1 (Conflicting Values) — full escalation ladder: definitional compatibility → materiality gate → bias correction (via Semantic Contract) → cross-signal triangulation → spread-size fork → decline
- Scenario 2 (Definitional Mismatch) — mostly resolved by Semantic Contract authoring (rename to precise labels, keep as separate features)
- Scenario 4 (Gaps) — **partial gap only** for this slice (SCM-constrained triangulation); total-gap forecast reconciliation is Phase 2 (see Risks — it needs Stage 2's changepoint engine)
- Scenario 5 (Calendar Misalignment) — Calendar Dimension bucketing, using Layer 2's three already-different grains as the test case
- Scenario 6 (Entity/Join-Key Mismatch) — Identity Resolution Graph (Fellegi-Sunter–style scoring) against `v_crm_customer_mapping`'s injected duplicates/near-misses
- KPI Semantic Contract — declared, not inferred, per-source metadata (grain, cadence, definition, bias direction, calendar convention) for `billing_system`, `crm_system`, `marketing_system`

**Out (this slice — explicitly deferred, not silently dropped):**
- Scenario 3 (Late-Arriving/Mutable History) — Layer 2 doesn't produce this data yet either (see its design doc). Nothing to reconcile against until `returned_day_offset` lands in Layer 1.
- Scenario 4's **total-gap** forecast reconciliation and Scenario 7 (Silent Drift) Level 2/3 detection — both explicitly reuse "Stage 2's STL/changepoint decomposition engine" per the design doc. Stage 2 doesn't exist yet. See Risks for how to unblock this without waiting.
- SQL-lineage parsing (reading Layer 2's own view definitions to auto-detect definitions/calendar convention) — the design doc treats this as a fallback for when metadata isn't declared; since we're authoring the Semantic Contract by hand for 3 known sources, this isn't needed yet. Worth building once Stage 1 needs to handle a source nobody's hand-documented.
- FastAPI wiring — Stage 1 ships as importable Python functions + a CLI/test harness first, per the architecture report's own phased build plan (orchestration is Phase 3, after Components A/B exist). Don't wire `/detect` etc. yet.
- Restatement/versioning (Scenario 3's machinery) beyond having the `version`/`restated_from_version` fields exist in the output contract — the actual "walk the topology, selectively recompute" logic has nothing to recompute yet (no Stage 2+ exists to be downstream of).

## Files to read first

1. `docs/02-stage-design-reports/stage1-reconciliation-design.md` — full scenario detail, §7 output contract
2. `pipeline/simulator/layer2_observed_sources/views.sql` — the actual 6 views this stage queries
3. `pipeline/simulator/layer2_observed_sources/schema_layer2.sql` — `source_outages`, needed to distinguish "gap" from "zero"
4. `.claude/reference/database.md` — current schema summary
5. `pipeline/simulator/layer1_ground_truth/generate.py` — the established code style to match (flat functions, `argparse` CLI, `psycopg2` direct)

## Files to create

```
pipeline/stage01_reconciliation_ingestion/
  README.md                    — update from stub to real status
  requirements.txt             — psycopg2-binary, numpy, python-dotenv (+ pandas if triangulation needs it)
  models.py                    — ReconciledValue output contract (dataclass)
  semantic_contract.py         — declared per-source metadata for billing/crm/marketing
  calendar_dimension.py        — bucket an atomic day_offset into any declared convention
  materiality.py               — the materiality gate (shared across scenarios 1, 3, 7)
  identity_resolution.py       — Fellegi-Sunter–style scoring for v_crm_customer_mapping
  reconcile.py                 — the main escalation-ladder pipeline, one function per scenario
  test_reconcile.py            — offline + live-DB checks, matching the Layer 1/2 test pattern
```

## Implementation steps

1. **`models.py`** — `ReconciledValue` dataclass: `episode_id`, `day_offset`, `kpi_name`, `value`, `value_range` (nullable), `confidence_tier` (`exact` / `aggregated` / `estimated` / `triangulated` / `declared_unresolved`), `source_provenance` (list), `imputation_flag` (`untouched` / `partially_imputed` / `fully_imputed`), `imputation_method` (nullable), `uncertainty_width` (nullable), `provisional` (bool), `provisional_resolution_date` (nullable), `version`, `restated_from_version` (nullable). *Validation:* instantiate one by hand, confirm every field from the design doc's §7 contract is represented.

2. **`semantic_contract.py`** — a plain Python dict (not a DB table yet — the design doc explicitly says this is authored, not inferred; a config module is the honest MVP of that, upgrade to a real table if/when a source needs runtime-editable metadata) keyed by source name, each entry: `grain`, `cadence_days`, `definition` (plain string, e.g. `"purchased in trailing 30 days"`), `bias_direction` (e.g. `"undercounts by ~13%, tightens to ~20% mid-episode"` for marketing — matches what's actually in `views.sql`), `calendar_convention`. *Validation:* every source in Layer 2's `views.sql` has an entry; the declared bias direction matches the actual view SQL (0.87/0.80), not a guess.

3. **`calendar_dimension.py`** — `bucket_day(day_offset, convention, start_date) -> bucket_id`, covering `"daily"`, `"iso_week"`, `"billing_cycle_month"` (mirrors the three grains Layer 2 already uses — this function should produce the *same* bucket boundaries the SQL views already compute, so it can be used to align reconciled values across grains, not reinvent them). *Validation:* for a known episode, confirm `bucket_day` output matches what `v_crm_weekly_active_customers`'s `week_start_day_offset` and `v_marketing_monthly_active_customers`'s `billing_cycle_index` actually returned in live queries.

4. **`materiality.py`** — `is_material(value_a, value_b, kpi_name, threshold) -> bool`. Start with a simple relative-difference threshold per KPI (a knob, like everything else in this project) — the design doc's fuller "would this flip a downstream decision" version needs Stage 3+ to exist to know what decisions are downstream, so this is deliberately the simple version for now, with a comment marking the upgrade path.

5. **`reconcile.py` — Scenario 1 (conflicting values):** `reconcile_conflicting_values(episode_id, day_offset)` — pull billing + marketing revenue for the day, run: definitional check (already resolved at Semantic Contract level — same construct, different bias) → materiality gate → bias correction (apply marketing's declared bias factor back, compare corrected value to billing's) → if still materially different, note as `triangulated` with widened uncertainty; if not, `exact`/`aggregated`. *Validation:* run against a known episode/day where marketing's bias is 0.87 and confirm bias-corrected marketing revenue ≈ billing revenue (within noise); run against a day inside a `source_outages` gap and confirm graceful handling (missing source, not a false conflict).

6. **`reconcile.py` — Scenario 2 (definitional mismatch):** for `active_customers`, don't reconcile billing vs crm into one number — emit **two** `ReconciledValue` rows (`kpi_name="active_customers_purchased_30d"` and `"active_customers_interacted_30d"`), per the design doc's explicit "keep as separate features, don't collapse" ruling. *Validation:* confirm both rows exist and are traceable to their source via `source_provenance`.

7. **`reconcile.py` — Scenario 5 (calendar):** use `calendar_dimension.py` to align `v_billing_daily_revenue` (daily) against `v_marketing_monthly_active_customers` (billing-cycle) for comparison/triangulation purposes without materializing a third combined grain (per the design doc's explicit rejection of that approach). *Validation:* confirm a billing-cycle-bucketed daily aggregate matches the view's own `billing_cycle_index` grouping.

8. **`reconcile.py` — Scenario 4 (partial gaps only):** when `source_outages` marks `marketing_system`'s `attributed_revenue` dark for a window but billing's revenue is present, triangulate using billing's number directly (they're the same underlying fact, just biased) rather than leaving it null. *Validation:* run against episode/day inside a known partial-gap window (query `source_outages` for one), confirm `imputation_flag="partially_imputed"` and the value is billing-derived.

9. **`identity_resolution.py`** — score two `crm_account_id` candidates against a `customer_id` using field agreement (for now: just the account-id match itself, since Layer 2's synthetic mapping is the only identifying field we have — richer field-weighting is Scenario 6's real machinery once more identifying fields exist in Layer 2). Two thresholds/three zones: auto-merge, auto-reject, ambiguous → `declared_unresolved`. *Validation:* run against `v_crm_customer_mapping`, confirm the ~3% synthetic duplicates get flagged as ambiguous/needing-review (not silently auto-merged — under-merging is the documented safer default) and the ~2% near-misses get caught, not trusted.

10. **`test_reconcile.py`** — offline checks (materiality gate logic, calendar bucketing math) + live-DB checks against the real 150-episode Neon dataset (mirrors `test_generate.py`/`test_views.py`'s split). Must print `OK`.

11. **Update `pipeline/stage01_reconciliation_ingestion/README.md`** from the stub to reflect real status, linking this plan and the design report.

## Tests and validation gate

```bash
cd pipeline/stage01_reconciliation_ingestion
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_reconcile.py   # must print OK
```
Plus a live-data spot check per `.claude/reference/testing.md`'s established pattern — query the actual reconciled output for a few episode/day combinations and eyeball it against the raw Layer 2 views, the same way every real bug in Layer 1/2 was actually caught.

## Acceptance criteria

- [ ] `ReconciledValue` output contract implemented, matches design doc §7 field-for-field
- [ ] Semantic Contract declared for all 3 Layer 2 sources, bias directions match actual view SQL
- [ ] Scenario 1 (conflicting values) ladder runs end-to-end on live data, produces the right confidence tier for both an agreeing day and a materially-conflicting day
- [ ] Scenario 2 (definitional mismatch) emits separate features, doesn't collapse
- [ ] Scenario 4 (partial gap only) triangulates through a real `source_outages` window
- [ ] Scenario 5 (calendar) bucketing verified against the views' own grain boundaries
- [ ] Scenario 6 (entity mismatch) correctly flags — not silently resolves — the synthetic duplicates/near-misses in `v_crm_customer_mapping`
- [ ] `test_reconcile.py` passes, both offline and against live Neon data
- [ ] README updated, PR opened against `develop`, merged

## Risks

1. **Scenario 4 (total gap) and Scenario 7 (drift) both explicitly reuse "Stage 2's STL/changepoint decomposition engine" per the design doc — and Stage 2 doesn't exist yet** (parallel teammate track, design complete, code not started). Options: (a) wait for Stage 2, blocking this slice's full scope; (b) build a minimal shared `changepoint.py` utility now (thin wrapper around the `ruptures` library, PELT method) that both Stage 1 and Stage 2 import later — promotes a piece of Stage 2's machinery slightly earlier than planned, consistent with this project's own "reuse over rebuild" principle. **Recommendation: (b)**, scoped as its own small follow-up once this slice's Scenario 1/2/4-partial/5/6 core is working — don't block the whole stage on it.
2. **Identity Resolution field-weighting is thin in this slice** — Layer 2 only gives us one identifying field (`crm_account_id`) to score against `customer_id`, not the richer multi-field set (email, phone, billing ID, etc.) the design doc describes. The design doc itself already flags this as a known hackathon-scale limitation (weights estimated from the simulator's own population, not a real enterprise's identity distribution) — this slice inherits that limitation honestly rather than fabricating fields Layer 2 doesn't have.
3. **No downstream stage exists yet to validate the output contract against.** `ReconciledValue` is built from the design doc's stated contract, not from an actual Stage 2 consumer's real needs — there's real risk the contract needs revision once Stage 2 is built and tries to consume it. Flag this explicitly when Stage 2 starts, don't assume Stage 1's contract is final.
