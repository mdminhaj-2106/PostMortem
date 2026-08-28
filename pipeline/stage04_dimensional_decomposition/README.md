# Stage 4 — Dimensional Decomposition

**Job:** given a flagged movement (or cluster) from Stage 3, break it down by region/segment/product using each slice's own real data. Purely descriptive, no cause-guessing yet.

**Status:** First implementation slice built and passing (`test_stage4.py`, offline + live-DB). Importable Python functions + a CLI, no FastAPI wiring yet.

**Design report:** [`docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md`](../../docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md) -- superseded on several load-bearing facts (KPI names, taxonomy values, Stage 3 input contract shape); see the design-doc-supersession note below.
**Implementation plan:** [`.claude/plans/stage4-dimensional-decomposition.md`](../../.claude/plans/stage4-dimensional-decomposition.md)

**Covers in this slice:**
- **5 new sliced `billing_system` Layer 2 views** (`pipeline/simulator/layer2_observed_sources/views.sql`): `v_billing_daily_revenue_by_region/_segment/_product`, `v_billing_active_customers_by_region/_segment` -- each scaffolds every `(day_offset, slice_value)` pair explicitly and `COALESCE`s a no-orders slice-day to `0`, so a real zero-order day is never confused with a data gap. Same whole-day `source_outages` suppression as the un-sliced billing views. Verified live: row counts match `n_days x distinct slice values` exactly, sliced revenue sums back to the un-sliced view's daily total, and a real billing outage (episode 8, days 74-80) is suppressed identically in both.
- `dimension_config.py` -- declared `{kpi: [applicable_dimensions]}`; `active_customers_purchased_30d` never gets a `product` slice (a customer isn't tied to one product)
- `slice_fetcher.py` -- `distinct_slice_values` (queries `customers`/`products` directly, a metadata lookup, same pattern as Stage 1's `_fetch_episode_start_date`) and `load_slice_timeline` (queries the new sliced views, returns the same `(day_offset, Observation_or_None)` shape Stage 2's own `ingest.py` returns, so no further adapter is needed)
- `stage2_bridge.py` -- re-exports Stage 2's real `eligibility.assess_eligibility` / `baseline.compute_residuals` / `unusualness.score_unusualness` directly, one level deeper than Stage 3's own `stage2_bridge.py` (same `sys.path` + `sys.modules`-eviction pattern)
- `stage3_bridge.py` -- re-exports Stage 3's real `run_stage3`, so `stage4.py`'s CLI can re-derive a real cluster to decompose instead of a hand-built fixture (same pattern, one dir over; imported lazily by `stage4.main()` since only the CLI path needs it)
- `decomposer.py` -- the main loop: cluster -> per-KPI -> per-dimension -> per-slice-value -> `SliceResult`, aggregating the flagged window's `sum(expected)`/`sum(observed)` from Stage 2's real residuals, with `unusualness_percentile` structurally forced to `None` whenever `eligibility` is `LIMITED_HISTORY`/`INSUFFICIENT_DATA` (never incidental)
- `output_schema.py` -- rejects any free-text field outside the declared enums, a plain assertion
- `stage4.py` -- orchestrator (`run_stage4`) + CLI entrypoint

**A real finding from live verification, not the plan's a-priori assumption (CONSTITUTION.md's non-negotiable: verify new real-world-data claims against actual data before asserting them):** the plan's Outcome section predicted region *size* would drive eligibility -- small regions landing `LIMITED_HISTORY`/`INSUFFICIENT_DATA` because of real customer-count skew. Live testing shows this isn't what happens, and the actual mechanism is more interesting: because the new views scaffold every `(day, slice_value)` pair and `COALESCE` a no-orders day to `0` (deliberately, so a real zero-order day doesn't look like a data gap), `eligibility.assess_eligibility` counts a `0`-valued observation as *usable*, identical to a large one. So for a given window, eligibility ends up driven purely by **window recency** (how many trailing days of history exist before the flagged window), uniformly across every slice of that KPI -- not by slice size. A Stage 3 window close to episode day 0 makes every region/segment slice `LIMITED_HISTORY` together (confirmed: episode 1, `active_customers_purchased_30d`, window 9-14 -- SP and a nearly-empty region `AP` both land `LIMITED_HISTORY` with `unusualness_percentile: None`); a window with >=30 real trailing days makes every slice `ELIGIBLE` together, including economically-flat small regions -- their *expected*/*observed* legitimately settle near `0` (or their `deviation_pct` comes back `None` because `expected == 0`), not their eligibility (confirmed: episode 1, `revenue`, window 107-109 -- SP is `ELIGIBLE` with a real `unusualness_percentile≈0.96`, and region `AP`, with zero revenue for the entire window, is *also* `ELIGIBLE`, just flat). Both are correct, honest signals given how the views were deliberately built -- not a bug, and not what the plan guessed. `test_stage4.py`'s two live tests assert this verified behavior directly.

**Output contract (→ Stage 5a):** `models.DecompositionResult` (`episode_id`, `cluster_id`, `slices: List[SliceResult]`) -- matches design doc §5's field set, adapted to real `day_offset` windows instead of ISO dates. `unusualness_percentile: None` is the signal that should route a slice to Stage 5c instead of Stage 5a, once that stage exists.

**Consumes:** Stage 3's `models.StageThreeResult` (via `stage3_bridge.py` for the CLI) and Stage 2's `eligibility`/`baseline`/`unusualness` (via `stage2_bridge.py`), plus the 5 new sliced Layer 2 views directly.

**Known gaps in this slice:**
- Any dimension beyond `region`/`segment`/`product` -- no `channel` dimension exists in this simulator's schema.
- Per-slice trajectory/time-series output -- single-window snapshots only.
- A second reconciliation escalation ladder at the slice level -- there's no second source with a region/segment/product breakdown to reconcile `billing_system`'s sliced numbers against.
- Weekly (or other non-daily) aggregation granularity -- Stage 2's reused functions are period-agnostic, so this is a cheap future option if daily granularity's zero-inflation for small slices (see the finding above) ever needs revisiting, not built speculatively now.
- FastAPI wiring -- same phased-build reasoning as Stages 1-3.
- **A fourth stacked cross-stage import** (Stage 4 -> Stage 2 -> Stage 1, plus Stage 4 -> Stage 3 -> Stage 2 -> Stage 1 for the CLI path) via the `sys.path`/`sys.modules`-eviction pattern. `architecture.md`'s Known Risks already flagged this as overdue at the third stage; a fourth makes a real package a stronger case, still not folded into this slice.

**Run:**
```bash
psql "$DATABASE_URL" -f pipeline/simulator/layer2_observed_sources/views.sql   # apply the 5 new sliced views

cd pipeline/stage04_dimensional_decomposition
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_stage4.py            # must print OK (offline + live DB, ~90s -- 2 live Stage 3 sweeps)
.venv/bin/python stage4.py --episode-id 1
```
