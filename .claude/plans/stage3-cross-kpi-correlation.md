# Plan: Stage 3 — Cross-KPI Correlation & Prioritization

**Design report:** `docs/02-stage-design-reports/stage3-cross-kpi-correlation-prioritization.md` (complete — DAG-based grouping vs. live causal discovery, revenue-equivalent dollar prioritization, joint/disjoint multi-path combination, why a composite KPI never reaches Stage 4; read that first, this plan translates it into buildable steps against what Stage 1/2 actually built, doesn't restate it).
**Priority:** next up after Stage 2 (first slice merged in PR #11). Stage 4 depends on Stage 3's cluster+priority output existing.
**Branch (this plan doc):** `feature/stage3-plan` off `develop`. **Branch (implementation slice):** `feature/stage3-cross-kpi-correlation` off `develop`.
**Track:** `stage3-cross-kpi-correlation`.

## Outcome (testable)

Given an episode where Stage 2 flags both `revenue` and `active_customers_purchased_30d` `SIGNIFICANT`/`STRUCTURAL` within a few days of each other (the real injected-event episodes already used for Stage 2's live check), Stage 3 looks up the one declared DAG edge between them, confirms same-direction co-movement within the expected lag window, forms a two-KPI cluster, computes a revenue-equivalent priority score from `revenue`'s own observed dollar delta, and emits one `StageThreeResult` carrying the full untouched cluster + priority score + carried-through Stage 2 confidence tag. An episode where only one KPI flags (or the two flag with contradicting direction / outside the lag window) emits each as a standalone, unclustered result instead — never a forced pairing.

## Scope

**In (first implementation slice):**
- Grouping Job — DAG lookup (design doc §2/§3) reusing the one edge this project's real KPI universe supports (`active_customers_purchased_30d → revenue`, `UPSTREAM_DRIVER`), extended with an expected-lag annotation and expected-direction (both same-sign, near-zero lag — active-customer purchases compose directly into the same window's revenue) — declared once in this stage's own DAG module, not inferred.
- Correlation check (design doc §2) — confirm actual co-movement: same-sign residual over the flagged window, and windows overlapping within the declared lag tolerance. Reuses Stage 2's own baseline residuals (see Files to read first) rather than recomputing expected-behavior logic.
- Failure mode — DAG-adjacent but direction/lag check fails, or no second flagged KPI exists at all: emit standalone, never force a cluster (design doc §2's "don't force it," direct reuse of Stage 1 Scenario 6's under-merge-is-safer principle).
- Prioritization Job — Axis 1 gate: Stage 2's confidence field (`HIGH`/`MEDIUM`/`LOW`) gates ranking eligibility, doesn't scale it (design doc §4). Axis 2 scale: revenue-equivalent dollar score.
- Case 1 (revenue in cluster — the only case this project's real KPI universe can produce, see Risks #1): priority = revenue's own observed dollar delta, `sum(residual)` over the flagged window from Stage 2's baseline (design doc §5's "use revenue's own observed dollar change directly").
- Case 2 (revenue not in cluster) — code path built and gated, not fabricated: since no declared multiplicative equation exists connecting `active_customers_purchased_30d` to revenue (unlike the design doc's illustrative `orders = conversion × traffic` chain — this project's generator has no such coefficient for this KPI pair), a lone `active_customers_purchased_30d` cluster gets `priority_score=None`, `priority_basis="PROJECTED_UNAVAILABLE"` rather than an invented number. Revisit once Stage 1 tracks `orders_count`/`avg_order_value` as their own KPIs (same gap Stage 2's plan already flagged for its own Layer 4).
- Output contract — a dataclass matching design doc §8 field-for-field: full contributing-KPI list untouched, priority score + basis, Stage 2 confidence tag carried through.
- Single-KPI passthrough (design doc §11 node Z) — an episode/window where only one KPI ever flags emits that KPI alone with its own Stage 2 confidence as the priority gate, no grouping logic invoked.

**Out (this slice — explicitly deferred):**
- Multi-path combination / joint-vs-disjoint node handling (design doc §6) — needs a 3+-member cluster, which this project's 2-KPI universe cannot produce (max cluster size = 2). Build the shared-node annotation mechanism once Stage 1 reconciles a third KPI; don't build a generic graph-traversal solver speculatively (design doc §10 explicitly rejects this even at full 3-5 KPI scale).
- Composite-KPI synthesis before handoff — explicitly rejected by the design doc itself (§7), not merely deferred. The full cluster passes through untouched; nothing to build here beyond not compressing it.
- Live causal discovery (Granger, PC algorithm) — design doc §10 rejects this outright; the DAG stays hand-declared.
- Empirically-fit correlation coefficients / regression-based relationship strength — Stage 2's plan already rejected inferring relationship evidence from an n=2 KPI universe (its own Risk #2); Stage 3 inherits that same reasoning for Case 2's equation coefficient rather than re-deriving one from a two-point correlation.
- FastAPI wiring — same phased-build reasoning as Stage 1/2; Stage 3 ships as importable Python functions + a CLI/test harness.
- Cross-episode / bulk performance optimization — single-episode runs only for this slice, matching Stage 2's own deferred Risk #3.

## Files to read first

1. `docs/02-stage-design-reports/stage3-cross-kpi-correlation-prioritization.md` — full grouping/prioritization rationale, §8 output contract, §10 scope guard, §11 pipeline flowchart
2. `pipeline/stage02_significance_detection/models.py` + `stage2.py` — the real (list-based, not `pandas.Series`) output Stage 3 consumes: `StageTwoResult.classification_state`, `.confidence`, `.day_offset`, `.kpi_name`
3. `pipeline/stage02_significance_detection/baseline.py` + `ingest.py` — reuse these directly for revenue's observed-vs-expected dollar residual (Case 1's priority score) and the same cross-stage-import pattern (`sys.path` insert + `sys.modules` eviction) Stage 2 already established for importing Stage 1
4. `pipeline/stage02_significance_detection/relationship_graph.py` — the one existing declared edge; Stage 3's own DAG module extends this with lag/direction, doesn't duplicate the base fact
5. `.claude/reference/architecture.md`, `.claude/reference/database.md` — current build status + schema
6. `pipeline/stage02_significance_detection/test_stage2.py` — the offline+live-DB test pattern to match

## Files to create

```
pipeline/stage03_cross_kpi_correlation/
  README.md                    — update from stub to real status
  requirements.txt             — psycopg2-binary, numpy, python-dotenv (same as Stage 2, no new deps)
  models.py                    — StageThreeResult dataclass, matches design doc §8 field-for-field
  ingest.py                    — pulls Stage 2 results + Stage 2's baseline residuals per KPI, via sys.path insert (Stage 2's own import pattern, one stage further)
  dag.py                       — the declared DAG: one edge, expected lag, expected direction
  correlation.py                — co-movement check: same-sign residual + lag-window overlap
  grouping.py                   — the actual clustering test (DAG adjacency + correlation confirm -> cluster, else separate)
  priority.py                   — revenue-equivalent dollar scoring (Case 1 observed; Case 2 gated/unavailable) + Axis-1 confidence gate
  stage3.py                     — orchestrator: episode -> list[StageThreeResult], CLI entrypoint
  test_stage3.py                 — offline + live-DB checks
```

## Implementation steps

1. **`models.py`** — `StageThreeResult` dataclass: `episode_id`, `cluster_id` (nullable — `None` for a standalone single-KPI result), `kpi_names` (list, the full untouched cluster membership), `window_start_day_offset`, `window_end_day_offset`, `priority_score` (nullable float, dollars), `priority_basis` (`OBSERVED`/`PROJECTED_UNAVAILABLE`), `confidence` (carried through from Stage 2, gates ranking), `grouping_basis` (`DAG_AND_CORRELATION`/`SINGLE_KPI`/`SEPARATE_NO_CORRELATION`/`SEPARATE_NO_ADJACENT_KPI`). *Validation:* instantiate by hand, confirm every §8 field is represented.

2. **`dag.py`** — declared dict extending `relationship_graph.py`'s one edge with `expected_lag_days: (0, 3)` and `expected_direction: "SAME_SIGN"` for `active_customers_purchased_30d -> revenue`. `related_kpis_with_lag(kpi_name) -> list[(kpi, relationship, lag_range, direction)]`. *Validation:* trivial lookup check, confirm it's a strict superset of Stage 2's own graph (same edge, same target).

3. **`ingest.py`** — `load_stage2_results(cur, episode_id, kpi_name, day_range) -> list[StageTwoResult]` (imports `stage2.run_stage2` via the established `sys.path` + `sys.modules`-eviction pattern) and `load_dollar_residuals(cur, episode_id, kpi_name, day_range) -> list[(day_offset, residual)]` (imports Stage 2's `ingest.load_kpi_timeline` + `baseline.compute_residuals` directly — reused, not reimplemented). *Validation:* run against episode 1, confirm both return non-empty lists of the expected length for both KPIs.

4. **`grouping.py`** — `find_flagged_windows(stage2_results) -> list[(start_day, end_day)]`: contiguous day-runs where `classification_state in (SIGNIFICANT, STRUCTURAL)`. `attempt_cluster(kpi_a_windows, kpi_a_residuals, kpi_b_windows, kpi_b_residuals, dag_entry) -> Cluster | None`: for each of KPI A's windows, checks whether KPI B has a window starting within `dag_entry.expected_lag_days` of KPI A's window start, and whether the mean residual sign over each window matches `dag_entry.expected_direction`; returns a cluster only if both hold. *Validation:* offline — synthetic window pairs covering all four `grouping_basis` outcomes (adjacent+correlated, adjacent+wrong-direction, adjacent+out-of-lag, no second KPI flagged at all).

5. **`priority.py`** — `gate_by_confidence(confidence) -> bool` (excludes `LOW`, per design doc §4's "gate, not scale"). `score_priority(cluster, residuals_by_kpi) -> (priority_score, priority_basis)`: if `revenue` is a cluster member, `priority_score = sum(residual for residual in residuals_by_kpi["revenue"] over the window)`, `priority_basis = "OBSERVED"`; otherwise `priority_score = None`, `priority_basis = "PROJECTED_UNAVAILABLE"` (see Scope — no fabricated coefficient). *Validation:* offline — one case per basis, one case for the confidence gate excluding a `LOW`-confidence cluster from ranking.

6. **`stage3.py`** — `run_stage3(cur, episode_id, day_range=None) -> list[StageThreeResult]`: runs Stage 2 for both KPIs (`ingest.py`), finds each KPI's flagged windows (`grouping.py`), attempts clustering pairwise, falls back to single-KPI passthrough for anything left unclustered, scores priority (`priority.py`) for every resulting cluster/standalone, applies the confidence gate. CLI (`argparse`, matching Stage 1/2's style) taking `--episode-id`. *Validation:* run end-to-end against episode 1, confirm no crash and every emitted result has a valid `grouping_basis`.

7. **`test_stage3.py`** — offline checks (steps 2, 4, 5's individual validations, collected) + live-DB checks:
   - Run `run_stage3` against the same real injected-event episode Stage 2's own live check already validated (a `marketing_cut`/`product_outage` case) and confirm the two KPIs cluster (`grouping_basis == "DAG_AND_CORRELATION"`) with `priority_basis == "OBSERVED"` and a nonzero `priority_score`.
   - Confirm a quiet episode/window (both KPIs `NORMAL` throughout) never gets forced into a cluster it doesn't earn (no `StageThreeResult` with `grouping_basis == "DAG_AND_CORRELATION"` where the underlying Stage 2 windows don't actually overlap-with-direction).
   - Must print `OK` alongside everything else.

8. **Update `pipeline/stage03_cross_kpi_correlation/README.md`** from stub to real status, linking this plan and the design report, and stating the Case 2 / multi-path deferrals plainly (matching Stage 2's README precedent for honestly-scoped gaps).

## Tests and validation gate

```bash
cd pipeline/stage03_cross_kpi_correlation
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_stage3.py   # must print OK
```
Plus a manual live spot-check: run `stage3.py --episode-id <n>` against a real injected-event episode and eyeball the emitted cluster/priority against that episode's actual revenue numbers before trusting the automated check alone — this project's real bugs have only ever been caught that way (`.claude/reference/testing.md`).

## Acceptance criteria

- [ ] `StageThreeResult` output contract implemented, matches design doc §8 field-for-field, full cluster membership never compressed/composited
- [ ] DAG lookup + lag/direction-aware correlation check both implemented and offline-tested against all four grouping outcomes
- [ ] Failed grouping (no adjacency, wrong direction, out-of-lag, or only one KPI flagged) always falls back to standalone results, never a forced cluster
- [ ] Priority scoring implements Case 1 (observed, revenue-in-cluster) for real against Stage 2's actual baseline residuals; Case 2 (projected) is explicitly gated as unavailable rather than fabricated, with the reason documented in README/plan
- [ ] Confidence gate (Axis 1) excludes `LOW`-confidence flags from ranking without discarding them from output
- [ ] Live check passes: a real injected-event episode's two KPIs cluster with a nonzero observed priority score, using the exact same episode already validated by Stage 2's own live check
- [ ] `test_stage3.py` passes, both offline and against live Neon data
- [ ] README updated, PR opened against `develop`, merged

## Risks

1. **This project's real KPI universe (2 KPIs, 1 edge) makes Case 2 (projected priority) and multi-path combination (3+ members) structurally untestable, not just unimplemented.** A lone `active_customers_purchased_30d` cluster without revenue is possible in principle (if the two windows don't align) but has no declared coefficient to project through — building one now would mean inventing an unjustified formula (exactly what Stage 2's own plan already refused to do for its Layer 4 §9.1/§9.4 gaps). **Recommendation:** ship Case 2 as an explicit gated "unavailable" result rather than a fabricated number; revisit once Stage 1 exposes `orders_count`/`avg_order_value` as trackable KPIs, which would also unlock a genuine 3-member cluster and make multi-path combination testable for real.
2. **Reusing Stage 2's baseline residuals for revenue's dollar delta means Stage 3 inherits Stage 2's calibration assumptions** (rolling-median window, `target_candidate_rate=0.30`) rather than an independent revenue-equivalent computation. This is deliberate (reuse machinery, don't fork logic — same principle Stage 4's plan already committed to for Stage 2's interface), but means any future retuning of Stage 2's baseline changes Stage 3's dollar figures too; worth a comment at the reuse site.
3. **A third cross-stage import** (Stage 3 -> Stage 2 -> Stage 1) stacks the same `sys.path`/`sys.modules`-eviction pattern one level deeper. Architecture.md already flags consolidating into a real package as overdue "once a third stage needs the same cross-import" — that threshold is now met. Recommend flagging this explicitly in the PR rather than silently deepening the workaround a third time, but not blocking this slice on a package restructure that's a separately-scoped change.
4. **Lag-window and direction annotations in `dag.py` are prototype knobs the team is declaring by hand** (`expected_lag_days=(0,3)`, same-sign), not fit from data — consistent with the design doc's own §12 admission that lag windows are "estimated by the team, not learned," but worth stating plainly in the report rather than presenting as validated.
