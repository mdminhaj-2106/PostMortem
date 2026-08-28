# Plan: Stage 4 — Dimensional Decomposition

**Design report:** `docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md` — **superseded on several load-bearing facts, not just style; read this plan's Risk #1 before that doc.** That doc predates Stage 1/2/3's real, narrowed build and gets three things wrong about what actually exists: (a) its golden example uses a `conversion_rate` KPI that Stage 1 has never reconciled and Stage 2/3 have never classified — the real KPI universe is `revenue` and `active_customers_purchased_30d` only; (b) its taxonomy (`Enterprise/SMB/Consumer` segments, `North/South/East/West` regions, `Product A/B/C`) doesn't match the real schema (`customers.segment` is `New/Returning/VIP`, `customers.region` is a real Olist state code — 27 distinct values in episode 1 alone, `products.category` is a real Olist category, only 4 distinct per episode); (c) its Stage 3 input contract is ISO-date JSON with a nested `priority_score` object — the real `StageThreeResult` dataclass (`stage03_cross_kpi_correlation/models.py`) uses integer `day_offset`s and flat fields. What's still correct and worth keeping: reuse Stage 2's layers rather than forking them, never fabricate a percentile for a `LIMITED_HISTORY` slice, reject free-text fields structurally, and the non-goals list (§9).
**Priority:** next up after Stage 3 (first slice merged in PR #13). Stage 5a depends on Stage 4's decomposition matrix existing.
**Branch:** `feature/stage4-plan` (this plan doc) → `feature/stage4-dimensional-decomposition` (implementation) off `develop`.
**Track:** `stage4-dimensional-decomposition`.

## A blocking prerequisite this plan surfaces (verified against live data, not assumed)

Layer 2's 6 existing views (`views.sql`) are **all whole-company aggregates** — none expose a region/segment/product breakdown. Stage 4's entire job is to break a flagged KPI down by dimension, so it cannot run at all without a sliced data source. `architecture.md`'s boundary rule ("nothing downstream of Layer 2 ever queries Layer 1's raw tables directly") means Stage 4 can't just query `orders`/`customers` itself either. **This plan's first implementation step is therefore a small, minimal extension to Layer 2** — sliced variants of the one source (`billing_system`) that's already exact/ground-truth-equivalent for `revenue` and `active_customers`, not a new fragmentation scenario. This is the same kind of "downstream stage needs an upstream extension" situation Stage 1's plan already flagged for Scenario 3 (mutable history) — surfaced here, not silently worked around.

## Outcome (testable)

Given a real `StageThreeResult` cluster from Stage 3 (e.g. episode 1's standalone `revenue` window, `day_offset` 107–109, `priority_score≈64604`, from Stage 3's own live spot-check), Stage 4 decomposes `revenue` over that window by every dimension it's declared applicable to (`region`, `segment`, `product`) using each slice's own real data, and emits one `SliceResult` per (KPI, dimension, slice_value) carrying expected/observed/deviation_pct/unusualness_percentile/eligibility — reusing Stage 2's real `eligibility.assess_eligibility`, `baseline.compute_residuals`, and `unusualness.score_unusualness` per slice, never re-deriving that logic. Given this project's real, skewed data (one region — `SP` — holds ~46% of customers in episode 1; the long tail has a handful of customers each), most small-region slices are expected to land `LIMITED_HISTORY`/`INSUFFICIENT_DATA` with `unusualness_percentile: None` — a correct signal, not a bug, and the test asserts this honestly rather than asserting a clean result the real data can't support.

## Scope

**In (first implementation slice):**
- **New Layer 2 views** (`pipeline/simulator/layer2_observed_sources/views.sql`): `v_billing_daily_revenue_by_region`, `v_billing_daily_revenue_by_segment`, `v_billing_daily_revenue_by_product` (keyed on `products.category`, the real 4-value Olist taxonomy — not a fabricated "Product A/B/C" list), `v_billing_active_customers_by_region`, `v_billing_active_customers_by_segment` (no `_by_product` variant — a customer isn't tied to one product, so `active_customers_purchased_30d` only ever gets `region`/`segment` breakdowns). Each view scaffolds every `(day_offset, slice_value)` combination explicitly (a `CROSS JOIN` of days × real distinct slice values, `LEFT JOIN`ed to orders) so a slice-day with zero orders reports `revenue=0`/`active_customers=0` — a real observation — rather than a missing row that would wrongly look like a data gap to the reused eligibility gate. Same `source_outages` suppression pattern as the existing views (a whole-day billing outage suppresses every slice equally; there's no slice-level outage concept in Layer 1's schema).
- **Declared dimension applicability** (`dimension_config.py`, a plain dict — no YAML config directory; this project's established pattern for small declared config is Stage 2's `relationship_graph.py`/`business_importance.py`, not a config-loading layer): `revenue: [region, segment, product]`, `active_customers_purchased_30d: [region, segment]`.
- **Slice values are read from the real data, not hand-enumerated** — `SELECT DISTINCT region FROM customers WHERE episode_id=...` etc. ("declare, don't infer" applies to which dimensions apply to which KPI, not to hardcoding all 27 Brazilian state codes by hand when the DB already has the canonical set for a given episode).
- **Per-slice decomposition**, reusing Stage 2's layers exactly as they exist (list-based, not `pandas.Series` — the interface mismatch Stage 2's own README already confirmed and left an adapter note for): for each slice, fetch a trailing daily timeline (window start − 30 days through window end) from the new sliced view, run `eligibility.assess_eligibility`, `baseline.compute_residuals`, `unusualness.score_unusualness`; aggregate the flagged window itself the same way Stage 3 aggregated its priority score (`sum(residual)` over the window days) into a single expected/observed/deviation_pct/percentile per slice, not a re-exposed daily series.
- **`unusualness_percentile: None` on `LIMITED_HISTORY`/`INSUFFICIENT_DATA` slices** — never a fabricated number (design doc §5's still-valid rule, carried forward).
- **Output contract** — a dataclass (`models.SliceResult` + `DecompositionResult`) matching the design doc §5 JSON shape field-for-field, adapted to real `day_offset` windows instead of ISO dates.
- **Schema validation** — reject any free-text field outside the fixed enums (`slice_value`, `eligibility`), a plain assertion in `output_schema.py`, not a new dependency (design doc §5's still-valid rule).
- **Single-KPI, single-member cluster handling** — Stage 3 already emits standalone single-KPI results for this project's real 2-KPI universe (most of Stage 3's own live output is standalone, not clustered); Stage 4 must decompose these identically to a 2-member cluster (design doc §8.3's edge case, still valid and now the *common* case here, not a rare one).

**Out (this slice — explicitly deferred):**
- Any dimension beyond `region`/`segment`/`product` — no `channel` dimension exists in this simulator's schema (design doc §9, still valid).
- Per-slice trajectory/time-series output — single-window snapshots only, matching design doc §9.
- A second reconciliation escalation ladder at the slice level — there's no second source with a region/segment/product breakdown to reconcile `billing_system`'s sliced numbers *against*, so there's nothing to escalate; the new views are read directly, tagged as exact (same `bias_direction: "none"` `billing_system` already carries in `semantic_contract.py` for the un-sliced case).
- Weekly (or other non-daily) aggregation granularity for the per-slice historical baseline — Stage 2's reused functions are period-agnostic (they operate on generic `(offset, value)` pairs, not literally "days"), so this is a real, cheap future option if daily granularity's sparse-data problem (see Risks #2) turns out to hide real signal — not built speculatively now.
- FastAPI wiring — same phased-build reasoning as Stages 1-3.
- Promoting `dimension_config.py`'s declared applicability into a shared `pipeline/cross_cutting/` Semantic Contract service — stays a Stage 4-local module for this slice, same reasoning Stage 1's semantic contract used before any second consumer needed it.

## Files to read first

1. `docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md` — still useful for mechanism/rationale (§3 pipeline shape, §5 output schema's free-text-rejection rule, §9 non-goals); **do not trust its KPI names, taxonomy values, or Stage 3 input contract shape** (this plan's header explains exactly which parts are wrong and why)
2. `pipeline/stage03_cross_kpi_correlation/models.py` — the real `StageThreeResult` Stage 4 actually consumes
3. `pipeline/stage02_significance_detection/eligibility.py`, `baseline.py`, `unusualness.py` — the real (list-based) functions Stage 4 reuses per slice, plus the real thresholds (`MIN_OBSERVATIONS_FOR_ELIGIBLE=30`, `MIN_OBSERVATIONS_FOR_LIMITED=10`) that make small-slice sparsity a real concern, not a hypothetical one
4. `pipeline/simulator/layer2_observed_sources/views.sql` — the exact view pattern (outage suppression, `GROUP BY`) the new sliced views must match
5. `pipeline/simulator/layer1_ground_truth/schema.sql` — `customers.region`/`.segment`, `products.category` — the real taxonomy source of truth
6. `pipeline/stage03_cross_kpi_correlation/stage2_bridge.py` — the `sys.path` + `sys.modules`-eviction cross-stage-import pattern Stage 4 needs one level deeper still (Stage 4 → Stage 2 → Stage 1); `architecture.md`'s Known Risks already calls a real package overdue now that a third stage needs this
7. `.claude/reference/architecture.md`, `.claude/reference/database.md` — current build status + schema + live data stats

## Files to create / change

```
pipeline/simulator/layer2_observed_sources/
  views.sql                     — append 5 new sliced billing views (CREATE OR REPLACE, idempotent, same file — not a new fragmentation scenario, an extension of billing_system's existing exact-source views)

pipeline/stage04_dimensional_decomposition/
  README.md                     — update from "no code yet" to real status
  requirements.txt               — psycopg2-binary, numpy, python-dotenv (same as Stages 2-3, no new deps)
  models.py                      — SliceResult + DecompositionResult dataclasses, matches design doc §5 field-for-field (day_offset windows, not ISO dates)
  dimension_config.py            — declared {kpi: [applicable_dimensions]} dict
  slice_fetcher.py                — pulls one slice's daily timeline from the new sliced Layer 2 views, given (kpi, dimension, slice_value, day_range)
  stage2_bridge.py                 — reuses Stage 2's eligibility/baseline/unusualness directly (same sys.path/sys.modules-eviction pattern as Stage 3's own stage2_bridge.py, one level deeper)
  decomposer.py                    — main loop: cluster -> per-KPI -> per-dimension -> per-slice-value -> SliceResult
  output_schema.py                 — free-text-field-rejection assertion (design doc §5)
  stage4.py                        — orchestrator: StageThreeResult -> DecompositionResult, CLI entrypoint
  test_stage4.py                    — offline + live-DB checks
```

## Implementation steps

1. **`views.sql` additions** — 5 new views, each: `CROSS JOIN` of `generate_series(0, n_days-1)` (per episode) × `SELECT DISTINCT <dimension column> FROM customers/products WHERE episode_id=...`, `LEFT JOIN orders` (aggregated `SUM`/`COUNT`), same `source_outages` suppression `WHERE NOT EXISTS` as the existing billing views, defaulting to `0` (via `COALESCE`) rather than omitting the row on a zero-order slice-day. *Validation:* `psql -f views.sql`, then query one view for episode 1 and confirm every `(day_offset, slice_value)` pair the CROSS JOIN should produce actually has a row (no silently-missing zero days), and that a day inside a known billing outage window is correctly absent for every slice.

2. **`models.py`** — `SliceResult`: `kpi_name`, `dimension`, `slice_value`, `window_start_day_offset`, `window_end_day_offset`, `expected` (float), `observed` (float), `deviation_pct` (nullable — `None` if `expected` is 0), `unusualness_percentile` (nullable float), `eligibility` (`ELIGIBLE`/`LIMITED_HISTORY`/`LOW_CONFIDENCE`/`INSUFFICIENT_DATA`). `DecompositionResult`: `episode_id`, `cluster_id` (nullable, carried from Stage 3), `slices: List[SliceResult]`. *Validation:* instantiate by hand, confirm every design doc §5 field is represented (flattened).

3. **`dimension_config.py`** — `DIMENSION_APPLICABILITY = {"revenue": ["region", "segment", "product"], "active_customers_purchased_30d": ["region", "segment"]}`, `applicable_dimensions(kpi_name) -> list[str]`. *Validation:* trivial lookup check, confirm `active_customers_purchased_30d` never returns `"product"`.

4. **`slice_fetcher.py`** — `distinct_slice_values(cur, episode_id, dimension) -> list[str]` (queries `customers`/`products` directly — this is Layer 1, but only to enumerate *which slice values exist*, the same kind of metadata lookup Stage 1's own `_fetch_episode_start_date` already does against `episodes`; the actual KPI *values* per slice always come from the new Layer 2 views, never from raw `orders`). `load_slice_timeline(cur, episode_id, kpi_name, dimension, slice_value, day_range) -> list[(day_offset, value_or_None)]` — queries the matching new sliced view. *Validation:* run against episode 1, `region`, confirm `SP`'s slice timeline has non-zero values on most days and a smaller region's timeline has real zero days (not missing days).

5. **`stage2_bridge.py`** — mirrors Stage 3's own bridge module exactly (same `sys.path` insert + `sys.modules`-eviction, same self-name-collision rationale for not calling it `ingest.py`), but exposes the *lower-level* layer functions Stage 4 actually needs: `assess_eligibility(timeline)`, `compute_residuals(timeline)`, `score_unusualness(residuals)` — re-exported directly, not wrapped, since their real signatures already match what Stage 4 needs (no adapter shim required beyond the import bridge itself — the design doc's anticipated "adapter layer" turns out to be exactly this bridge module, already built once for Stage 3). *Validation:* import in isolation, confirm no `sys.modules` collision with Stage 4's own `models.py`/other same-named files (repeat Stage 3's own eviction-order test if one exists, else a simple round-trip import check).

6. **`decomposer.py`** — `decompose_cluster(cur, episode_id, stage3_result) -> DecompositionResult`: for each `kpi_name` in `stage3_result.kpi_names`, for each `dimension` in `dimension_config.applicable_dimensions(kpi_name)`, for each `slice_value` in `slice_fetcher.distinct_slice_values(...)`: fetch a timeline from `window_start_day_offset - 30` through `window_end_day_offset`, run eligibility/baseline/unusualness via `stage2_bridge`, and — only for days inside the flagged window itself — sum `observed` and sum `expected` (from the residuals' `expected` component) to get the window-aggregate pair; `unusualness_percentile` = the window's last day's score (same "as-of-the-window's-end" convention Stage 3 already used for its own confidence lookup); `deviation_pct = (observed - expected) / expected` if `expected != 0` else `None`. *Validation:* offline — a synthetic two-slice fixture (one dense/eligible, one sparse/insufficient) confirms both paths produce the expected `eligibility`/`unusualness_percentile: None` combination.

7. **`output_schema.py`** — `validate(decomposition_result)`: walks every `SliceResult`, asserts every field is either a declared enum member or a number — raises on any unexpected string. *Validation:* one case with a deliberately-injected free-text field, confirm it's rejected; one clean case passes.

8. **`stage4.py`** — `run_stage4(cur, episode_id, stage3_result) -> DecompositionResult`, wiring steps 4/6/7; CLI (`argparse`, matching Stages 1-3's style) taking `--episode-id` and re-running Stage 3 itself for that episode to get a real cluster to decompose (mirrors how `stage3.py`'s own CLI re-derives its input from Stage 2 rather than requiring a hand-built fixture). *Validation:* run end-to-end against episode 1's real standalone `revenue` window, confirm no crash and every emitted slice has a valid `eligibility`.

9. **`test_stage4.py`** — offline checks (steps 2/3/6/7's validations, collected) + live-DB checks:
   - Run `run_stage4` against a real Stage 3 result for episode 1 (or another already-validated episode from Stage 2/3's own live checks) and confirm the decomposition matrix covers every applicable (KPI, dimension) pair with at least one slice.
   - **Confirm the honest expectation, not a fabricated one:** assert that at least one small-region slice lands `LIMITED_HISTORY` or `INSUFFICIENT_DATA` with `unusualness_percentile is None` (this project's real customer-count skew all but guarantees this — see Outcome), and that `SP` (or whatever the top region is for the tested episode) is `ELIGIBLE`.
   - Must print `OK` alongside everything else.

10. **Update `pipeline/stage04_dimensional_decomposition/README.md`** from "no code yet" to real status, linking this plan, and explicitly noting where it now diverges from the old design-report doc (same honesty precedent Stage 2/3's READMEs already set for their own confirmed interface mismatches).

## Tests and validation gate

```bash
psql "$DATABASE_URL" -f pipeline/simulator/layer2_observed_sources/views.sql   # apply the new sliced views

cd pipeline/stage04_dimensional_decomposition
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_stage4.py   # must print OK
```
Plus a manual live spot-check: run `stage4.py --episode-id 1` and eyeball the per-slice numbers against a direct `psql` query of the new sliced views for the same window — this project's real bugs (VIP-segment skew, reliability >1.0, an inconsistent active-customer definition) have only ever been caught by querying live output, not by reading the code.

## Acceptance criteria

- [ ] 5 new sliced Layer 2 views applied and verified against live data (every `(day_offset, slice_value)` pair present, zero-order days show `0` not a missing row, outage suppression matches the existing un-sliced views)
- [ ] `DIMENSION_APPLICABILITY` correctly excludes `product` for `active_customers_purchased_30d`
- [ ] Slice values are read from real per-episode data, never hand-enumerated
- [ ] Decomposition reuses Stage 2's real `eligibility`/`baseline`/`unusualness` functions directly — no forked logic
- [ ] `unusualness_percentile` is `None` for every `LIMITED_HISTORY`/`INSUFFICIENT_DATA` slice, never a fabricated number
- [ ] Output schema validation rejects an injected free-text field
- [ ] Live test passes against a real Stage 3 result, and honestly asserts the expected mix of `ELIGIBLE` and `LIMITED_HISTORY`/`INSUFFICIENT_DATA` slices given this project's real data skew — not a cleaned-up fabricated result
- [ ] `test_stage4.py` passes, both offline and against live Neon data
- [ ] README updated (including an explicit note on where this plan diverges from the old design-report doc), PR opened against `develop`, merged

## Risks

1. **This plan supersedes several concrete facts in the existing design-report doc** (`conversion_rate` KPI, `Enterprise/SMB/Consumer` segments, `North/South/East/West` regions, the ISO-date Stage 3 JSON contract) — see this plan's header for the full list. The old doc's *mechanism* (reuse Stage 2's layers, reject fabricated percentiles, structural free-text rejection) is still sound and carried forward; only the specific names/shapes are wrong, because that doc was written before Stage 1/2/3's real scope narrowed to 2 KPIs. Flagging this explicitly in the PR rather than silently diverging.
2. **Real data is far more skewed than the old doc's clean golden example assumed.** Episode 1 has 27 distinct regions with `SP` alone holding ~46% of customers; company-wide order volume averages roughly one order per day per small region. At daily granularity, most non-top-region slices will hit Stage 2's `MIN_OBSERVATIONS_FOR_LIMITED=10`/`MIN_OBSERVATIONS_FOR_ELIGIBLE=30` thresholds slowly or not at all within a short Stage-3-flagged window's trailing history. This is a correct signal (small slices genuinely can't be analyzed with daily confidence), not a bug — but it does mean the demo's "interesting" slice-level findings will concentrate on the top 1-2 regions and the 4 product categories, not a rich 27-region breakdown. Weekly (or other) aggregation is a cheap follow-up if this turns out to hide real signal (Stage 2's reused functions are period-agnostic) — not built now (Scope/Out).
3. **A fourth stage now needs the same `sys.path`/`sys.modules`-eviction cross-import pattern** (Stage 4 → Stage 2 → Stage 1, on top of Stage 3's own already-one-level-deeper case). `architecture.md`'s Known Risks called a real package overdue at the *third* stage; a fourth is a strong signal this shouldn't be deferred again, though a full package restructure stays a separately-scoped change, not folded silently into this plan.
4. **The new sliced views' zero-vs-missing scaffolding (`CROSS JOIN` + `COALESCE`) is new SQL, not a copy of an existing pattern** — the existing 6 views never needed this because "no orders company-wide on a given day" essentially never happens at this dataset's scale, while "no orders for a specific small region on a given day" is common. Get this wrong and Stage 4 silently treats real zero-order days as missing data, degrading eligibility incorrectly — the step 1 validation specifically checks for this.
