# Plan: Stage 2 — Relevant KPI Extraction & Temporal Change Classification

**Design report:** `docs/02-stage-design-reports/stage2-relevance-extraction-architecture.md` (complete — 7 layers, full rationale for why fixed per-KPI thresholds are rejected in favor of self-normalized unusualness; read that first, this plan translates it into buildable steps, doesn't restate it).
**Priority:** next up after Stage 1 (first slice merged in PR #9). Everything downstream (Stage 3+) depends on Stage 2's relevant/classified KPI set existing.
**Branch:** `feature/stage2-relevance-extraction` off `develop`.
**Track:** `stage2-relevance-extraction`.

## Outcome (testable)

Given an episode with a real injected event (e.g. a `marketing_cut` or `product_outage`), Stage 2 ingests Stage 1's `revenue` and `active_customers_purchased_30d` timelines for that episode, computes each day's unusualness relative to that KPI's own history, resolves relevance from declared business importance + relationship context, and classifies each relevant day as `EMERGING` / `SIGNIFICANT` / `STRUCTURAL` — producing a day-by-day trajectory that visibly reacts within a few days of the event's `start_day_offset` and stays `NORMAL` / filtered during quiet stretches before it. Stage 2's own code never queries `injected_events`; only the offline test does, for scoring (architecture.md's "Critical flows" #3).

## Scope

**In (first implementation slice):**
- Layer 1 — Data Eligibility Gate (`ELIGIBLE` / `LIMITED_HISTORY` / `LOW_CONFIDENCE` / `INSUFFICIENT_DATA`)
- Layer 2 — Expected Behavior: **one** baseline method, a rolling-median robust baseline with a configurable window (design doc §6.2). No STL/seasonal decomposition — the design doc itself says a simple robust baseline "should be the initial default," and this project has no cyclical/seasonal KPI yet to justify more.
- Layer 3 — Self-Normalized Unusualness: residual → empirical percentile against that KPI's own historical residual distribution (design doc §7)
- Broad Candidate Selection — percentile-threshold, configurable `target_candidate_rate` (design doc §8)
- Layer 4 — Business Importance: **declared** criticality metadata + **declared** KPI relationship-graph position only (design doc §9.2, §9.3). No direct-outcome-formula conversion (§9.1) and no historical/correlation-based relationship evidence (§9.4) in this slice — see Out, below.
- Layer 5 — KPI Relationship Graph: one hand-declared edge, `active_customers_purchased_30d → revenue` (`UPSTREAM_DRIVER`) — the only relationship this project's actual reconciled KPI universe supports honestly (see Risks #2).
- Layer 6 — Relevance Resolution: the design doc's §14 interpretable rule matrix, implemented as explicit rules (not a weighted formula)
- Layer 7 — Temporal Change Classification: `EMERGING` → `SIGNIFICANT` → `STRUCTURAL` state machine (design doc §16), run as a full-episode offline backtest (this project's simulator produces complete historical episodes, so there's no need to model live/streaming incremental state for the prototype)
- Output contract — a dataclass matching design doc §18's JSON contract field-for-field

**Out (this slice — explicitly deferred, matches design doc §19 almost exactly):**
- STL/seasonal decomposition baseline for "mature history" KPIs — no KPI in this project has enough episode-length data to justify it yet; revisit if a KPI with genuine seasonality gets tracked.
- Direct-outcome-formula business importance (§9.1, e.g. `Δrevenue = Δorders × E[AOV]`) — would need `orders_count`/`avg_order_value` tracked as their own Stage-2 KPIs, which Stage 1 doesn't currently emit as standalone `ReconciledValue` rows (it only surfaces them as intermediate view columns). Add once Stage 1 (or Stage 2's own ingestion) exposes them.
- Historical/correlation-based relationship evidence (§9.4) — needs enough parallel KPI history to compute meaningful correlations; with only 2 KPIs in the current universe, a declared edge is more honest than an inferred one from n=2.
- PELT / CUSUM / Bayesian online change detection for `STRUCTURAL` (§16.3, §19) — design doc explicitly says these are "later, if the prototype demonstrates the need," not initial requirements. The prototype rule (persistence + no reversion, both as day-count knobs) is what ships.
- ML-ranked relevance, learned/calibrated importance weights, full causal discovery, LLM-based classification — all explicitly out per design doc §19 and CONSTITUTION.md's LLM-boundary rule (Stage 2 makes zero LLM calls).
- FastAPI wiring — same phased-build reasoning as Stage 1's plan; Stage 2 ships as importable Python functions + a CLI/test harness.
- Multi-episode / bulk performance optimization (batching Stage 1 calls across days into fewer round trips) — see Risks #3.

## Files to read first

1. `docs/02-stage-design-reports/stage2-relevance-extraction-architecture.md` — full layer detail, §18 output contract, §19 deferred list
2. `pipeline/stage01_reconciliation_ingestion/reconcile.py` + `models.py` — the actual functions/contract Stage 2 consumes (`reconcile_conflicting_values`, `reconcile_definitional_active_customers`, `ReconciledValue`); Stage 2 must not reinvent this, only call it (design doc §5: "Stage 1 already performs reconciliation and ingestion. Stage 2 should not repeat that work.")
3. `pipeline/stage01_reconciliation_ingestion/semantic_contract.py` — the "declared, not inferred" pattern to reuse for Stage 2's own business-criticality and relationship-graph metadata
4. `pipeline/simulator/layer1_ground_truth/schema.sql` — `injected_events` fields (`event_type`, `start_day_offset`, `end_day_offset`, `magnitude`, `onset_type`), needed for the live scoring test only
5. `.claude/reference/architecture.md`, `.claude/reference/database.md` — current build status + schema
6. `pipeline/stage01_reconciliation_ingestion/test_reconcile.py` — the offline+live-DB test pattern to match

## Files to create

```
pipeline/stage02_significance_detection/
  README.md                    — update from stub to real status
  requirements.txt             — psycopg2-binary, numpy, python-dotenv (same as Stage 1, no new deps)
  models.py                    — StageTwoResult dataclass, matches design doc §18 field-for-field
  ingest.py                    — calls into Stage 1's reconcile.py per day to build a KPI timeline
  eligibility.py                — Layer 1: data eligibility gate
  baseline.py                  — Layer 2: rolling-median expected-behavior baseline
  unusualness.py                — Layer 3: self-normalized unusualness (empirical percentile)
  candidate_selection.py       — Broad candidate selection (percentile threshold)
  business_importance.py       — Layer 4: declared criticality + relationship-graph evidence
  relationship_graph.py        — Layer 5: the one declared edge (active_customers -> revenue)
  relevance.py                  — Layer 6: relevance resolution rule matrix + priority tiers (§15)
  classification.py            — Layer 7: EMERGING/SIGNIFICANT/STRUCTURAL state machine
  stage2.py                     — orchestrator: episode -> list[StageTwoResult], CLI entrypoint
  test_stage2.py                — offline + live-DB (incl. injected_events scoring) checks
```

## Implementation steps

1. **`models.py`** — `StageTwoResult` dataclass: `episode_id`, `day_offset`, `kpi_name`, `analysis_status` (`ANALYZED`/`INSUFFICIENT_DATA`), `unusualness_score` (nullable float), `unusualness_basis`, `history_confidence` (`HIGH`/`MEDIUM`/`LOW`), `business_importance_level`, `business_importance_evidence` (list), `cluster_id` (nullable), `related_candidates` (list), `relevance_level`, `priority_tier` (nullable int), `classification_state` (`NORMAL`/`EMERGING`/`SIGNIFICANT`/`STRUCTURAL`), `classification_evidence` (list), `confidence`. *Validation:* instantiate by hand, confirm every §18 JSON field is represented (flattened, not nested — matches this project's flat-dataclass style over nested objects).

2. **`ingest.py`** — `load_kpi_timeline(cur, episode_id, kpi_name, day_range)`, where `kpi_name` is one of `revenue` / `active_customers_purchased_30d`. For `revenue`, calls Stage 1's `reconcile_conflicting_values` per day; for `active_customers_purchased_30d`, calls `reconcile_definitional_active_customers` per day and keeps only the billing-sourced row. Imports Stage 1's `reconcile.py` via a `sys.path` insert to its sibling module directory (see Risks #1 — no root package exists yet to import across `pipeline/stage0N_*/` cleanly). Returns a list of `(day_offset, ReconciledValue)`, `None` value preserved for `declared_unresolved` days (not silently dropped — eligibility needs to see the gap). *Validation:* run against episode 1, day range 0-20, confirm length matches, confirm at least one `declared_unresolved` day is preserved if a partial/total gap exists in that window.

3. **`eligibility.py`** — `assess_eligibility(timeline) -> str`, one of `ELIGIBLE`/`LIMITED_HISTORY`/`LOW_CONFIDENCE`/`INSUFFICIENT_DATA`, based on: count of non-null observations vs. configurable `min_observations_for_eligible`/`min_observations_for_limited`, and the fraction of `imputation_flag != "untouched"` or `declared_unresolved` observations vs. a configurable `max_degraded_fraction`. *Validation:* offline — construct synthetic timelines (all-clean/long, all-clean/short, half-imputed, empty) and confirm each maps to the expected status.

4. **`baseline.py`** — `compute_residuals(timeline, window) -> list[(day_offset, expected, residual)]`, rolling median over the trailing `window` non-null observations (design doc §6.2 formula exactly); skips (returns no residual for) days with fewer than a configurable `min_window_for_estimate` prior observations. *Validation:* offline — a synthetic flat series with one spike; confirm the spike day's residual is large and all other residuals are ~0.

5. **`unusualness.py`** — `score_unusualness(residuals) -> list[(day_offset, score)]`, empirical percentile rank of `abs(residual)` against all prior `abs(residual)` values for that same KPI up to (not including) that day — a real online/causal percentile, not one computed with future data leaking in (important: must not use the full-episode residual distribution to score an early day, since that wouldn't be knowable at the time). *Validation:* offline — confirm a day's unusualness score never depends on residuals from days after it (feed the same prefix twice, confirm identical scores); confirm the spike day from step 4's fixture scores near 1.0.

6. **`candidate_selection.py`** — `select_candidates(unusualness_scores, target_candidate_rate) -> set[day_offset]`, percentile-threshold selection (design doc §8's `candidate_selection.strategy: percentile` interface). *Validation:* offline — confirm the returned set size is proportional to `target_candidate_rate` on a synthetic uniform-random score series.

7. **`relationship_graph.py`** — a small declared dict, `{"active_customers_purchased_30d": [("revenue", "UPSTREAM_DRIVER")]}`, plus `related_kpis(kpi_name) -> list[(kpi, relationship)]`. *Validation:* trivial lookup check.

8. **`business_importance.py`** — declared criticality dict (`revenue: critical`, `active_customers_purchased_30d: high`) + `assess_importance(kpi_name, other_candidates_today) -> (level, evidence_list)`, checking declared criticality and whether a related KPI (per `relationship_graph.py`) is *also* a candidate the same day. *Validation:* offline — confirm `revenue` alone gets `level="HIGH"` from criticality; confirm `active_customers_purchased_30d` co-occurring with a `revenue` candidate adds a `KNOWN_RELATIONSHIP` evidence entry.

9. **`relevance.py`** — `resolve_relevance(unusualness_score, importance_level, has_relationship_context) -> (relevance_level, priority_tier)`, implementing design doc §14's matrix as explicit `if`/`elif` rules (discretizing unusualness into `very_high`/`high`/`medium`/`low` tiers via configurable cutoffs first). *Validation:* offline — one test case per matrix row in §14.

10. **`classification.py`** — `classify_trajectory(day_relevance_sequence) -> list[(day_offset, state, evidence)]` implementing the §16 state machine over a full episode's relevant/not-relevant sequence for one KPI: `EMERGING` on first relevant day(s); `SIGNIFICANT` once relevant for >= `min_days_for_significant` (knob, default 3) consecutive days with consistent direction; `STRUCTURAL` once `SIGNIFICANT` has persisted >= `min_days_for_structural` (knob, default 10) without reverting toward the pre-event baseline; `NORMAL`/exit when movement disappears. *Validation:* offline — feed a synthetic relevance sequence (`[F,F,T,T,T,T,T,T,T,T,T,T,F]`) and confirm the expected `EMERGING`→`SIGNIFICANT`→`STRUCTURAL`→exit trajectory.

11. **`stage2.py`** — `run_stage2(cur, episode_id, kpi_name, day_range) -> list[StageTwoResult]`, wiring steps 2-10 in the design doc's §17 flow order; CLI (`argparse`, matching Stage 1's `reconcile.py` style) taking `--episode-id`, `--kpi`. *Validation:* run end-to-end against episode 1 for both KPIs, confirm it doesn't crash and every output day has a valid `analysis_status`.

12. **`test_stage2.py`** — offline checks (steps 3-10's individual validations, collected) + live-DB checks:
    - Ingest a real Stage 1 timeline and confirm `stage2.py` runs end-to-end without error.
    - **Scoring check (the real validation):** query `injected_events` for an episode with a `marketing_cut` or `product_outage` of `severity IN ('moderate','severe')`, run `run_stage2` on `revenue` for that episode across the full episode range, and confirm at least one day within `[start_day_offset, start_day_offset + 15]` reaches `classification_state IN ("EMERGING","SIGNIFICANT","STRUCTURAL")` — i.e., Stage 2 actually reacts to a real injected cause. Also confirm a quiet stretch well before `start_day_offset` (e.g. days 0-10, if the event starts later) stays `NORMAL` on most days. This is the only place in Stage 2's codebase that touches `injected_events`, and only for offline scoring (per CONSTITUTION.md's non-negotiable #5) — must print `OK` alongside everything else, never be imported by `stage2.py` itself.

13. **Update `pipeline/stage02_significance_detection/README.md`** from stub to real status, linking this plan and the design report.

## Tests and validation gate

```bash
cd pipeline/stage02_significance_detection
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_stage2.py   # must print OK
```
Plus a manual live spot-check per `.claude/reference/testing.md`'s established pattern: run `stage2.py` over a real episode/KPI and eyeball the day-by-day trajectory against that episode's actual revenue numbers (and, informally, its injected event) before trusting the automated scoring check alone — this project's real bugs have only ever been caught that way.

## Acceptance criteria

- [ ] `StageTwoResult` output contract implemented, matches design doc §18 field-for-field
- [ ] Stage 2 ingests Stage 1's output via its real functions (`reconcile_conflicting_values`, `reconcile_definitional_active_customers`) — no reimplementation of reconciliation logic
- [ ] Eligibility gate, rolling-median baseline, and self-normalized unusualness all implemented and offline-tested
- [ ] Business importance uses only declared metadata + the one declared relationship edge — no fabricated formulas or unjustified weights
- [ ] Relevance resolution matches design doc §14's rule matrix exactly (one test case per row)
- [ ] Temporal classification state machine (`EMERGING`/`SIGNIFICANT`/`STRUCTURAL`) implemented and offline-tested against a synthetic trajectory
- [ ] Live scoring check passes: Stage 2 reacts (reaches `SIGNIFICANT`+ within 15 days) to a real injected event on at least one tested episode, without ever having read `injected_events` inside `stage2.py`/its dependencies
- [ ] `test_stage2.py` passes, both offline and against live Neon data
- [ ] README updated, PR opened against `develop`, merged

## Risks

1. **No root-level Python package exists yet, and this is the first stage that genuinely needs to import another stage's module** (`ingest.py` calling into Stage 1's `reconcile.py`). Options: (a) a `sys.path.insert` hack pointing at `../stage01_reconciliation_ingestion` — quick, ugly, works, consistent with "no new dependency without asking" since it adds no dependency at all; (b) consolidate into a real installable package now. **Recommendation: (a)** for this slice, clearly commented as a known interim wrinkle (architecture.md already flags this as a known risk to consolidate "once the FastAPI app needs to import across stage modules" — that need has now arrived one stage earlier than expected, but a full package restructure is a bigger, separately-planned change, not something to fold silently into Stage 2's plan).
2. **The KPI relationship graph is honest but thin** — only 2 KPIs (`revenue`, `active_customers_purchased_30d`) currently exist in Stage 1's output, so Layer 5's graph is a single edge and Layer 4's "position in known KPI relationships" evidence type has exactly one thing to point to. The design doc's richer illustrative examples (Traffic → Conversion → Orders → Revenue) aren't buildable until Stage 1 reconciles more KPIs. Flag this honestly in the report rather than fabricating relationships Stage 1 doesn't actually produce.
3. **Performance:** `ingest.py` calls Stage 1's per-day functions in a loop — for a 120-day episode and 2 KPIs, that's ~240-480 sequential round trips to the pooled Neon connection. Fine for a single-episode offline run/demo; would need batching (a bulk `reconcile_revenue_range` in Stage 1, or a single wider SQL query) before this scales to a multi-episode eval loop. Not blocking this slice — flag for whoever builds the offline eval harness (architecture report §9).
4. **Temporal classification thresholds (`min_days_for_significant=3`, `min_days_for_structural=10`) are prototype knobs, not empirically calibrated** — the design doc itself says "the exact policies can later be calibrated" (§14) and explicitly defers CUSUM/PELT/Bayesian changepoint detection until "the prototype demonstrates the need" (§16.3). State this plainly in the report rather than presenting these numbers as validated.
