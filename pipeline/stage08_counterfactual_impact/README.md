# Stage 8 — Counterfactual Impact Engine

**Status:** First implementation slice built and passing (`test_stage8.py`, offline + one live-DB end-to-end run). Importable Python functions + a CLI, no FastAPI wiring yet.

**Design report:** [`docs/02-stage-design-reports/stage8-counterfactual-impact-engine-architecture.md`](../../docs/02-stage-design-reports/stage8-counterfactual-impact-engine-architecture.md) — the eligibility gate, both intervention scenarios, time-resolved trajectory, and joint-non-split invariant are followed. The design doc's central *mechanism* (a per-cause simulation class) is not implementable in this codebase — see below, this is the single most important thing to read before touching this stage again.

**Implementation plan:** [`.claude/plans/stage8-counterfactual-impact-engine.md`](../../.claude/plans/stage8-counterfactual-impact-engine.md) — has the full reasoning.

**The finding that reshapes this stage:** the design doc's `InterventionMechanism` registry (`ProductOutageMechanism`, etc., §14-21) re-simulates each cause's structural effect — e.g. "remove the outage's effect on `reliability`, propagate through `conversion_rate` → `orders` → `revenue`." Tracing the real mechanics in `pipeline/simulator/layer1_ground_truth/generate.py` shows every one of those mechanisms reads `daily_state` (`reliability`, `marketing_spend`, `competitor_activity`) — a **Layer 1 raw table**. `.claude/reference/architecture.md`'s boundary rule says nothing downstream of Layer 2 ever queries Layer 1 raw tables directly. Building the mechanism registry as designed would mean secretly reading the held-out ground truth — not a scope cut, an architecture violation.

**What's used instead:** Stage 5b's fitted `share`/`contribution` is the *only* validated quantitative mechanism this codebase actually has. A hypothesis is estimated **iff Stage 5b ran for its cluster and produced a matching `CauseContribution`** (single, IDENTIFIED contribution for a `SINGLE` hypothesis; the `NON_IDENTIFIABLE_JOINT` contribution for a `COMPOUND` one). Everything else returns `estimation_status=MECHANISM_UNAVAILABLE`. Since `router.should_fork()` (Stage 5b) only forks on narrow-margin, multi-dimension-concentration clusters, this means **most hypotheses across the dataset will be `MECHANISM_UNAVAILABLE`** — an honest, stated consequence, not a bug (see Risks).

The reconstruction itself, for each day in the hypothesis's investigated window: `counterfactual = observed - share * residual`, where `residual = observed - expected` comes from Stage 1/2's real, already-built baseline machinery (`ingest.load_kpi_timeline` + `baseline.compute_residuals`, a 14-day trailing median) — reused, never redefined, per design doc §18.

**Other real-contract corrections:**
1. Stage 4's `SliceResult` is a window *aggregate* (one number per slice per window), not time-resolved — Stage 8's required daily trajectory (§16-17) comes from Stage 1/2's per-day machinery instead, fetched at the **whole-KPI level** (unsliced), not per-region/segment/product.
2. No declared interaction config exists anywhere in this repo (same finding Stage 7 made about compound-hypothesis combination policy) — interaction modeling (§26-28) is out of scope; `interaction` isn't a populated field.
3. `REMOVE_FROM_TIME` reuses the exact same per-day reconstruction as `EVENT_NEVER_OCCURRED` — days before the intervention day just keep `counterfactual = observed`. No separate engine.
4. Recovery modeling (§30) is implicit, not a declared per-mechanism property: since the reconstruction never claims to know pre/post-window counterfactual behavior, whatever real recovery already happened during Stage 4's own investigated window is baked into the *observed* trajectory the residual is computed against. Stated simplification, not a modeled `IMMEDIATE`/`LINEAR`/`OBSERVED_RECOVERY_PROFILE` choice.
5. `data_confidence` reuses Stage 2's real `eligibility.py` tiers (`ELIGIBLE`/`LIMITED_HISTORY`/`LOW_CONFIDENCE`/`INSUFFICIENT_DATA`) rather than inventing the design doc's own `HIGH`/`MEDIUM`/`HEAVILY_IMPUTED` vocabulary, which doesn't exist in this codebase.
6. `impact_direction` is always `HIGHER_IS_BETTER` — checked against `stage01_reconciliation_ingestion/semantic_contract.py` before hardcoding: it declares source `bias_direction` (a different concept, measurement bias between systems), not a per-KPI cost/revenue orientation, and no cost-style KPI exists among the 5 real ones.
7. Uncertainty intervals are explicitly `uncertainty_status="LIMITED"` always — built from real pre-window residual variability but not statistically calibrated against anything (design doc §38's own stated escape hatch).

**Covers in this slice:**
- `models.py` — `InterventionSpec`/`CounterfactualPoint`/`CounterfactualImpact`/`Stage8Result`, trimmed of `stage5b_basis`/`interaction` sub-objects until something real populates them
- `config.py` — `MINIMUM_CONFIDENCE`, `ALLOW_UNKNOWN=False` (matches the design doc's own example policy), `PRE_WINDOW_HISTORY_DAYS`
- `canonical_bridge.py` — re-exports Stage 2's real `load_kpi_timeline`/`compute_residuals`/`assess_eligibility`
- `stage7_bridge.py` — re-exports Stage 7's `run_stage7` plus its own already-built stage3/4/5a/5b/6 bridges transitively (no need to re-derive 5 layers of cross-import plumbing a second time)
- `hypothesis_eligibility.py` — the 5b-match gate (mirrors Stage 7's own `evidence_analytical._stage5b_contribution_for` matching rule)
- `reconstruction.py` — the core per-day trajectory, pure function, both intervention modes
- `uncertainty.py` — pre-window residual-stdev interval + `data_confidence`
- `impact.py` — aggregate impact, pct, KPI direction
- `output_schema.py` — no estimates after abstention, no `ESTIMATED` entry without a matched mechanism, trajectory reconciles with the aggregate, interval contains the point
- `stage8.py` — orchestrator (`run_stage8`) + CLI entrypoint

**Output contract (→ Stage 9):** `models.Stage8Result` — one `CounterfactualImpact` per Stage 7 hypothesis (either `ESTIMATED` with a real trajectory, or a stated-unavailable reason), `abstained_upstream` when Stage 7 abstained, `engine_version`.

**Consumes:** Stage 7's `Stage7Result` (+ its own transitive chain via `stage7_bridge.py`), Stage 5b's raw `ConfoundedAttributionResult` (only when the router forked), Stage 1/2's canonical timeline + baseline machinery directly.

**Deferred, not implemented:**
- Any per-cause mechanism class re-simulating `daily_state` internals — architecturally impossible here, not a time cut (see above).
- Multi-hop structural KPI-graph propagation (§31-33) — Stage 3's real DAG doesn't have the depth the design doc assumes (`architecture.md`'s Known Risks: only a single 2-KPI edge actually runs).
- Interaction-effect modeling (§26-28) — no declared config exists.
- A calibrated/validated uncertainty model — stated `LIMITED`.
- Estimating any hypothesis Stage 5b didn't fit.
- FastAPI wiring.

**Run:**
```bash
cd pipeline/stage08_counterfactual_impact
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_sm
.venv/bin/python test_stage8.py            # must print OK (offline + one live episode-15 run)
.venv/bin/python stage8.py --episode-id 15
```
