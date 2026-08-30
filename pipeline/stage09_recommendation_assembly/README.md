# Stage 9 — Recommendation Assembly & Action Selection

**Status:** First implementation slice built and passing (`test_stage9.py`, offline + one live-DB end-to-end run). Importable Python functions + a CLI, no FastAPI wiring yet.

**Design report:** [`docs/02-stage-design-reports/stage9-recommendation-assembly-architecture.md`](../../docs/02-stage-design-reports/stage9-recommendation-assembly-architecture.md) — the decision layer's shape (cause → mechanism → lever → atomic action → context binding, confidence-aware multi-objective selection, no arbitrary weighted score) is followed. Several of its input assumptions were written before Stage 7/8 shipped their real contracts and turned out wrong — corrected here, stated plainly rather than silently narrowed.

**Implementation plan:** [`.claude/plans/stage9-recommendation-assembly.md`](../../.claude/plans/stage9-recommendation-assembly.md) — has the full reasoning behind every correction below.

**Real-contract corrections from the design doc (read before touching this stage again):**
1. **Stage 8 already did the Stage 7↔Stage 8 join.** `Stage8Result.estimates` is one `CounterfactualImpact` per Stage 7 `RankedHypothesis`, for every status (`ESTIMATED` and `MECHANISM_UNAVAILABLE`/`UNAVAILABLE` alike) — Stage 8 never drops a hypothesis. Stage 9 iterates `stage8_result.estimates` directly rather than building a separate per-hypothesis Stage 8 lookup.
2. **"Mechanism" means two different things across Stage 8 and Stage 9.** Stage 8's `estimation_reason_codes` describe the *quantitative method* used to compute the dollar figure (`STAGE5B_QUANTITATIVE_CONSTRAINT`, `BASELINE_RECONSTRUCTION`). Stage 9's own `mechanism` (e.g. `reliability_degradation`) describes *how the cause hurts the business*, used only to pick a lever. Do not conflate them.
3. **No target-scope (product/region/segment) survives in Stage 7 or Stage 8's output.** That signal only exists in Stage 4's `DecompositionResult` via Stage 6's own `entity_scope_filter.flagged_facets(decomposition_result)` — reused directly (`action_builder.resolve_target_scope`) rather than reinventing scope detection. Zero flagged facets is a legitimate outcome: `target_scope={}` (cluster-level), never a fabricated `"Global"`.
4. **No Learning & Memory, Decision Rights, or company-capability service exists anywhere in this repo.** `historical_effectiveness` is always `"UNKNOWN"`; `owner` comes from a small **declared** lever→team table (`config.LEVER_ACTIONS`, real domain knowledge, not invented per-episode); capability feasibility is a stated stub, always `AVAILABLE` for every declared team.
5. **No rich KPI structural graph exists** to filter multiple levers per mechanism or to expand a multi-KPI monitored set — Stage 3's real DAG is a single 2-KPI edge. Reduced to one declared lever per mechanism (`config.MECHANISM_LEVERS`) and `monitoring_plan.affected_kpis = [the one investigated kpi_name]`.
6. **`expected_impact` passes Stage 8's number through unchanged, honestly labeled.** No new forward-looking projection is built; `impact_lower`/`impact_upper` are never narrowed.
7. **`UNKNOWN`-confidence hypotheses do reach Stage 9.** Stage 8's own eligibility gate excludes them from `ESTIMATED` but still emits a `CounterfactualImpact` for them (`estimation_status="UNAVAILABLE"`, `stage7_confidence="UNKNOWN"`). `intent_resolver.resolve_intent` explicitly handles `UNKNOWN` → `INVESTIGATE`, always, never `ACT`.
8. **Multiple levers per mechanism and a populated action-compatibility conflict table are out of scope for this slice.** With only 4 real causes, one declared canonical lever per mechanism is enough; the 4 causes' default actions (repair reliability / restore marketing spend / investigate competitor / replenish inventory) are naturally compatible, so `config.ACTION_COMPATIBILITY_CONFLICTS` starts empty. The conflict-resolution check itself (`selection.resolve_conflicts`) is real and unit-tested against a synthetic conflict table — it just never fires against real data.
9. **`"seasonal"` can appear as a joint-hypothesis member cause** (Stage 5b's basis includes it alongside the 4 real causes — Stage 7's own README confirms a live `FULLY_MERGED` bucket containing all 5). It is not a business lever: nothing a company can "fix" the way it can repair an outage. `mechanism_resolver.resolve_mechanism("seasonal")` returns `None` rather than raising; the cause still appears in `driver` for provenance but contributes no mechanism/lever/action/owner (`config.NON_ACTIONABLE_CAUSES`). Not called out in the plan's own numbered findings — found live while implementing `action_builder.py`.

**Covers in this slice:**
- `models.py` — `ActionCandidate`/`MonitoringPlan`/`SuccessCriteria`/`Recommendation`/`Stage9Result`, trimmed of effort/time-to-impact beyond `"UNKNOWN"` placeholders, no monetary-cost field anywhere
- `config.py` — `CAUSE_MECHANISMS`/`MECHANISM_LEVERS`/`LEVER_ACTIONS` (4 rows, one lever/action each), `NON_ACTIONABLE_CAUSES`, `ACTION_COMPATIBILITY_CONFLICTS` (starts empty, stated why), `CAPABILITY_AVAILABLE` (stubbed), `CONFIDENCE_POLICY` — plain Python dicts, matching every other stage's `config.py`/`cause_config.py` style, not the design doc's YAML files
- `mechanism_resolver.py` / `lever_resolver.py` — declared-only lookups, no structural-applicability filtering (finding #5)
- `action_builder.py` — lever → atomic action, deduplicated across a joint hypothesis's actionable members; `resolve_target_scope` binds Stage 6's real `flagged_facets` once per Stage 9 run
- `owner_resolver.py` — primary/secondary owner resolution for joint hypotheses, never implying a numeric ownership split
- `feasibility.py` — capability (stubbed `AVAILABLE`) + context (real check that a bound scope isn't internally contradictory)
- `intent_resolver.py` — `stage7_confidence` + action `risk_tier` → `ACT`/`INVESTIGATE`/`MONITOR`, per `CONFIDENCE_POLICY`; `UNKNOWN` and "no valid action mechanism" both force `INVESTIGATE`
- `monitoring.py` / `success_criteria.py` — the one investigated KPI, `expected_direction="UP"` (all 5 real KPIs are higher-is-better, reused from Stage 8's own `impact.py` finding); `DERIVABLE` iff `estimation_status=="ESTIMATED"`
- `selection.py` — dominance over the real, reduced axis set (`stage7_confidence`, `estimated_impact` magnitude, `context_feasibility`), conflict resolution (real, unreachable table), deterministic primary + non-dominated alternatives, stable tie-break on Stage 7's own `rank`
- `output_schema.py` — no unknown `hypothesis_id`, no monetary-cost-shaped field, no LLM import anywhere in this package (greppable regression test)
- `stage8_bridge.py` — re-exports Stage 8's `run_stage8` plus its own transitive stage3/4/5a/5b/6/7 bridges, plus a sideways bridge straight into Stage 6's `entity_scope_filter.flagged_facets`
- `stage9.py` — orchestrator (`run_stage9`) + CLI entrypoint

**Output contract (→ Stage 10):** `models.Stage9Result` — `decision_status` (`RECOMMENDATION_AVAILABLE`/`INVESTIGATION_RECOMMENDED`/`MONITORING_RECOMMENDED`/`NO_DEFENSIBLE_ACTION`), one `primary_recommendation` (`driver → mechanism → lever → action → owner → decision_intent → expected_impact → monitoring_plan → success_criteria`), a capped list of non-dominated `alternatives` (each flagged `parallel_action` when its own intent is `ACT`, vs. a fallback otherwise).

**Consumes:** Stage 7's `Stage7Result`, Stage 8's `Stage8Result` (already Stage-7-joined), Stage 4's `DecompositionResult` (for real target-scope binding via Stage 6's `flagged_facets`).

**Deferred, not implemented:**
- Multiple levers per mechanism/cause (finding #8) — one canonical lever is enough for this project's real 4-cause vocabulary.
- Real historical action-effectiveness — no Learning & Memory service exists anywhere in this repo (finding #4).
- Real company capability gating — no such service exists (finding #4).
- Structural KPI-graph-filtered lever applicability or multi-KPI monitoring propagation (finding #5) — Stage 3's real DAG is one edge.
- A populated action-compatibility conflict table (finding #8) — none of the 4 real causes' actions actually conflict.
- Effort/time-to-impact metadata — stays `"UNKNOWN"`, never guessed.
- FastAPI wiring.

**Run:**
```bash
cd pipeline/stage09_recommendation_assembly
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_sm   # transitively needed via stage8_bridge -> ... -> stage6
.venv/bin/python test_stage9.py            # must print OK (offline + one live episode-15 run)
.venv/bin/python stage9.py --episode-id 15
```
