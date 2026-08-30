# Stage 8 — Counterfactual Impact Engine (first slice, reduced scale)

**Design report:** `docs/02-stage-design-reports/stage8-counterfactual-impact-engine-architecture.md`
**Branch:** `feature/stage8-counterfactual-impact-engine` (off `develop`)
**Consumes:** Stage 7 (`Stage7Result`), Stage 5b (`ConfoundedAttributionResult`, only when the router forked), Stage 1/2's canonical timeline + baseline machinery

## The one finding that reshapes this whole stage

The design doc's central mechanism is a **per-cause `InterventionMechanism` registry** (`ProductOutageMechanism`, `MarketingCutMechanism`, ...) that re-simulates each cause's structural effect (§14-21, §31-33) — e.g. "remove the outage's effect on `reliability`, propagate through `conversion_rate` → `orders` → `revenue`."

**This is not implementable in this codebase, and not a scope choice — it's an architecture boundary.** I traced the real per-cause mechanics in `pipeline/simulator/layer1_ground_truth/generate.py` (`generate_episode`, `effect_fraction`):
- `product_outage` multiplicatively degrades `daily_state.reliability`, which then feeds `conversion_rate`.
- `marketing_cut` multiplicatively degrades `daily_state.marketing_spend`, which then feeds `traffic`.
- `competitor_launch` only feeds `daily_state.competitor_activity` → `churn_rate` — no same-day revenue/orders effect at all, its impact is a *cumulative reduction in future active customers*, not a mechanism a per-day formula can cleanly invert.
- `inventory_shortage` reweights which *product* an order lands on (`product_weights`) — it doesn't reduce order *count*, so "removing" it mostly redistributes revenue between products rather than raising the KPI total.

All four mechanisms read `daily_state` — a Layer 1 raw table. `.claude/reference/architecture.md`'s own boundary rule says **nothing downstream of Layer 2 ever queries Layer 1's raw tables directly**, and `daily_state` is exactly that (only `injected_events` is called out as held-out, but the rule is broader: Layer 2 views are "what the pipeline actually ingests," full stop). So Stage 8 structurally cannot see `reliability`, `marketing_spend`, or `competitor_activity` to re-run these formulas — doing so would mean silently reading the answer key, the same violation `injected_events` being held out exists to prevent.

**What Stage 8 can honestly do instead**, from the design doc's own decision hierarchy (§20, priority order 1-5): mechanism-class re-simulation (#1) and multi-hop structural-equation propagation (#3, `Traffic → Conversion → Orders → Revenue`) are both off the table for the reason above — Stage 3's real DAG is a single 2-KPI edge, not the doc's assumed multi-hop chain (`architecture.md`'s Known Risks), and even if it were richer, propagating through it would still need the same off-limits latent state. That leaves **#2 (Stage 5b's quantitative contribution) and #4 (baseline reconstruction)** as the only two levers actually available — and only #2 gives a *cause-specific* number; #4 alone can't honestly be attributed to one hypothesis among several. So:

> **In this slice, a hypothesis is counterfactually estimable if and only if Stage 5b ran for its cluster and produced a matching `CauseContribution` (single, for a `SINGLE` hypothesis; joint, for a `COMPOUND` one).** Every other hypothesis — which, since `router.should_fork()` only forks on narrow-margin/multi-dimension cases, is most of them — gets `estimation_status=MECHANISM_UNAVAILABLE`. This is not a cut corner; it's the direct, stated consequence of `NO_VALIDATED_INTERVENTION_MECHANISM` (design doc §14, §52) applied honestly against what this codebase's causal machinery actually validates: Stage 5b's fitted shape-basis decomposition, and nothing per-cause beyond it.

The reconstruction itself: `ingest.load_kpi_timeline` + `baseline.compute_residuals` (Stage 1/2's real, already-built machinery — see below) give a per-day `(observed, expected, residual)` for the investigated KPI. For each day in the hypothesis's window, `counterfactual = observed - share * residual` (adds back `share`'s fraction of the shortfall/excess; sign-correct for both up- and down-deviations without assuming "higher is better" — direction is read off the residual's own sign, then labeled via `impact_direction`). This is the "Stage 5b as quantitative constraint, baseline as the reconstruction surface" combination the design doc itself describes (§22) — just without a mechanism class sitting on top pretending to know *why* the number is that size.

## Real contracts vs. the design doc (the rest of the corrections)

1. **Stage 7's real `RankedHypothesis` is close to what §7 assumes** — `hypothesis_id`, `member_causes`, `hypothesis_type`, `identifiability`, `borrowed`, `confidence_bucket`, `confidence_reason_codes`, `analytical_evidence.stage5b_contribution`/`.stage5b_share`, `rank`/`rank_group` all exist as built (`stage07_hypothesis_debate_ranking/models.py`). The per-hypothesis Stage 5b contribution/share is already sitting on `analytical_evidence` — no need to re-bridge to raw Stage 5b output for that part. Stage 8 still needs the *raw* `ConfoundedAttributionResult` separately for `fit_quality`/`unexplained_share`/`identifiability_verdict`, which live at the result level, not per-hypothesis.
2. **No time-resolved daily data exists at the Stage 4 (sliced) layer** — `SliceResult.expected`/`.observed` are window *aggregates*, one number per (KPI, dimension, slice_value, window), not a per-day series (`stage04_dimensional_decomposition/models.py`). Stage 8's time-resolved trajectory (design doc §16-17, a hard requirement) must come from Stage 1/2's own per-day machinery instead — `stage02_significance_detection/ingest.py`'s `load_kpi_timeline(cur, episode_id, kpi_name, day_range)` → `[(day_offset, ReconciledValue_or_None), ...]`, then `baseline.py`'s `compute_residuals(timeline)` → `[(day_offset, expected, residual), ...]` (14-day trailing median baseline, the real "baseline machinery" design doc §18 says to reuse). This is fetched at the **whole-KPI level** (unsliced), matching the design doc's own aggregate-revenue examples, not per-region/segment/product.
3. **No declared interaction config exists anywhere in the repo** (same finding Stage 7 made about compound-hypothesis combination policy) — `interaction = NOT_MODELED` unconditionally in this slice; §26-28's multi-scenario interaction machinery is out of scope.
4. **`REMOVE_FROM_TIME` is cheap to support once the per-day loop exists** — days before the requested intervention day keep `counterfactual = observed` (zero impact), days after use the same share-based reconstruction as `EVENT_NEVER_OCCURRED`. Both modes share one code path; no separate engine needed.
5. **Recovery modeling (§30) is implicit, not a separate mechanism property** — because the reconstruction only ever touches days inside Stage 4's own investigated window (never claiming to know pre/post-window counterfactual behavior), whatever real recovery already happened during that window is baked into the *observed* trajectory the residual is computed against. This is a stated simplification, not a modeled `IMMEDIATE`/`LINEAR`/`OBSERVED_RECOVERY_PROFILE` choice — flagged as a risk below.
6. **Data confidence reuses Stage 2's real `eligibility.py`** (`ELIGIBLE`/`LIMITED_HISTORY`/`LOW_CONFIDENCE`/`INSUFFICIENT_DATA`, run on the whole-KPI timeline this stage already fetched) rather than inventing the design doc's own `HIGH`/`MEDIUM`/`HEAVILY_IMPUTED` vocabulary that doesn't exist in this codebase.
7. **Uncertainty intervals are explicitly `LIMITED`** in this slice — built from the pre-window trailing residual variability (a real, computable signal) but not statistically calibrated against anything (design doc §38's own escape hatch: "the output must not pretend the interval is statistically calibrated" when no reliable estimate exists). Exact formula is a live-calibration item, not hardcoded here.

## Scope

**In:** eligibility gating (Stage 7 abstention → don't run; `UNKNOWN` bucket excluded by default per the design doc's own example config; hypothesis without a matching Stage 5b contribution → `MECHANISM_UNAVAILABLE`); per-day counterfactual reconstruction from Stage 1/2's real baseline machinery, constrained by Stage 5b's `share`; both `EVENT_NEVER_OCCURRED` and `REMOVE_FROM_TIME` scenarios (same code path); joint (`NON_IDENTIFIABLE_JOINT`) hypotheses estimated as one mechanism, never split; aggregate impact + direction + recovered-potential; a stated-`LIMITED` uncertainty interval from pre-window residual variability; `output_schema.py` invariants (no joint split, no estimate without a matching 5b contribution, no estimate after Stage 7 abstention, no `UNKNOWN` estimate, trajectory reconciles with the aggregate); `resolver`/`engine_version`.

**Out (stated, not hidden):** any per-cause mechanism class re-simulating `daily_state` internals (architecturally impossible here, not a time cut); multi-hop structural KPI-graph propagation (Stage 3's real DAG doesn't have the depth the design doc assumes); interaction-effect modeling (no declared config exists); a calibrated/validated uncertainty model (stated `LIMITED`); estimating any hypothesis Stage 5b didn't fit; explicit recovery-mode selection (implicit in the window-scoped reconstruction, see finding #5); FastAPI wiring.

## Files to read first

- `docs/02-stage-design-reports/stage8-counterfactual-impact-engine-architecture.md` — §2 locked decisions, §5 forbidden behaviors, §41-54 examples/failure modes (these define correctness even where the mechanism underneath is simplified)
- `pipeline/simulator/layer1_ground_truth/generate.py` — `effect_fraction`, `generate_episode`'s day loop (already traced above; re-read if the mechanism-availability finding needs re-verifying against a generator change)
- `pipeline/stage02_significance_detection/ingest.py` (`load_kpi_timeline`, `KPI_NAMES`) and `baseline.py` (`compute_residuals`) — the real baseline/timeline machinery to reuse, not reinvent
- `pipeline/stage02_significance_detection/eligibility.py` — data-quality tiers to reuse for `data_confidence`
- `pipeline/stage05b_confounded_cause_decomposer/models.py` (`ConfoundedAttributionResult`, `CauseContribution`) — `fit_quality`, `unexplained_share`, `identifiability_verdict` at the result level
- `pipeline/stage07_hypothesis_debate_ranking/models.py`, `stage7.py`, and its own `stage3_bridge.py`/`stage4_bridge.py`/`stage5a_bridge.py`/`stage5b_bridge.py`/`stage6_bridge.py` — the real input contract and the full re-derivation chain Stage 8's CLI needs to replay
- `pipeline/stage04_dimensional_decomposition/models.py` — confirms `SliceResult` is window-aggregate only, not time-resolved (why Stage 8 bridges to Stage 1/2 directly instead)

## Files to change/create

```
pipeline/stage08_counterfactual_impact/
├── README.md
├── requirements.txt              (psycopg2-binary, python-dotenv, numpy -- transitively
│                                   needs stage07's full requirements too, since its
│                                   own bridge chain re-derives through stage06's
│                                   sentence-transformers/spacy/vaderSentiment)
├── models.py                     (InterventionSpec, CounterfactualPoint,
│                                   CounterfactualImpact, Stage8Result -- trimmed to
│                                   fields this slice actually populates)
├── config.py                     (minimum_confidence policy, allow_unknown=False,
│                                   pre-window history buffer days)
├── canonical_bridge.py           (re-exports Stage 1/2's real load_kpi_timeline /
│                                   compute_residuals / assess_eligibility, same
│                                   sys.path/sys.modules-eviction pattern as every
│                                   other cross-stage bridge)
├── stage7_bridge.py              (re-exports Stage 7's own run_stage7 AND its
│                                   already-built stage3/4/5a/5b/6 bridges transitively
│                                   -- Stage 8's CLI needs the whole chain, and
│                                   re-deriving each layer's bridge a second time
│                                   would just be more of the same sys.modules-eviction
│                                   boilerplate for no benefit)
├── hypothesis_eligibility.py     (Step: abstention check, confidence-bucket policy,
│                                   5b-contribution-required gate -> ESTIMATED-eligible
│                                   vs each UNAVAILABLE/MECHANISM_UNAVAILABLE reason)
├── reconstruction.py             (the core per-day trajectory: observed/expected/
│                                   residual -> counterfactual, both intervention modes)
├── uncertainty.py                (pre-window residual-variability interval,
│                                   uncertainty_status=LIMITED, data_confidence from
│                                   eligibility)
├── impact.py                     (aggregate impact, impact_pct, impact_direction,
│                                   recovered_potential)
├── output_schema.py              (invariants: no joint split, no estimate without a
│                                   matching 5b contribution, no estimate after Stage 7
│                                   abstention, no UNKNOWN estimate, trajectory
│                                   reconciles with aggregate within tolerance, interval
│                                   contains the point estimate)
├── stage8.py                     (orchestrator: run_stage8() + CLI entrypoint)
└── test_stage8.py
```

## Implementation steps

1. **`models.py` + `config.py`.** `InterventionSpec` (`hypothesis_id`, `member_causes`, `mode` ∈ {`EVENT_NEVER_OCCURRED`, `REMOVE_FROM_TIME`}, `intervention_day_offset`), `CounterfactualPoint` (`day_offset`, `observed_value`, `baseline_value`, `counterfactual_value`, `estimated_impact`, `point_lower`/`point_upper`, `data_confidence`), `CounterfactualImpact` (per design doc §46, trimmed: drop `stage5b_basis`/`interaction` sub-objects until something real populates them beyond `None`), `Stage8Result` (`cluster_id`, window bounds, `estimates`, `skipped_hypotheses`, `abstained_upstream`, `engine_version`). `config.py`: `MINIMUM_CONFIDENCE = ("KNOWN", "LIKELY", "POSSIBLE")`, `ALLOW_UNKNOWN = False`, `PRE_WINDOW_HISTORY_DAYS` (buffer before `window_start` so `compute_residuals`'s 14-day/5-observation minimums are satisfiable — start around 30, confirm live). No DB needed.

2. **`canonical_bridge.py`.** Re-export `ingest.load_kpi_timeline`, `ingest.KPI_NAMES`, `baseline.compute_residuals`, `eligibility.assess_eligibility` + its status constants, from `stage02_significance_detection`. Same eviction pattern as every bridge so far — remember the real bug Stage 7 hit: check for any bare-module-name collision between `stage02_significance_detection`'s own internal modules and anything already cached (`ingest.py` itself bridges to Stage 1's `reconcile`/`models`/etc. — evict those transitively too, mirroring `stage02_significance_detection/ingest.py`'s own `_STAGE1_MODULE_NAMES` list).

3. **`stage7_bridge.py`.** Re-export `stage07_hypothesis_debate_ranking`'s `run_stage7` plus its own already-built `stage3_bridge.run_stage3`/`stage4_bridge.run_stage4`/`stage5a_bridge.run_stage5a_and_5c`+`load_reference`/`stage5b_bridge.should_fork`+`run_stage5b`/`stage6_bridge.run_stage6`. Test: import succeeds and every re-exported name is callable (no live DB needed for this check alone).

4. **`hypothesis_eligibility.py`.** For each `RankedHypothesis` in `stage7_result.hypotheses` (only called at all when `stage7_result.abstained is False`): `UNKNOWN` bucket → `skipped` with `STAGE7_UNKNOWN` (unless `config.ALLOW_UNKNOWN`, off by default); no `stage5b_result` for this cluster, or no matching `CauseContribution` for this hypothesis's `member_causes` → `skipped` with `NO_VALIDATED_INTERVENTION_MECHANISM`; otherwise → eligible, carrying the matched `CauseContribution.share`. Test each branch, including a joint hypothesis matching a joint contribution by member-set equality (same matching logic Stage 7's own `evidence_analytical._stage5b_contribution_for` already uses — mirror it, don't diverge).

5. **`reconstruction.py`.** `build_trajectory(cur, episode_id, kpi_name, window_start, window_end, share, mode, intervention_day_offset)`: fetch `load_kpi_timeline` for `range(window_start - PRE_WINDOW_HISTORY_DAYS, window_end + 1)`, run `compute_residuals`, then for each day in `[window_start, window_end]`: if `expected` is `None` for that day (insufficient trailing history) → `CounterfactualPoint` with `counterfactual_value=None`, flagged, not fabricated; else `counterfactual = observed - share * residual` when the day is on/after the intervention day (day itself for `EVENT_NEVER_OCCURRED`, the requested day for `REMOVE_FROM_TIME`), else `counterfactual = observed`. Test: a synthetic `[(day, expected, residual)]` fixture recovers the exact arithmetic for both modes (design doc §59-61's own unit tests, adapted to this reconstruction instead of a mechanism class) — no live DB needed for this module's own tests.

6. **`uncertainty.py`.** `data_confidence` = `assess_eligibility` run on the fetched timeline (reused, not recomputed). Interval: stdev of `residual` over the pre-window trailing days, scaled into a point-wise ± band; `uncertainty_status = "LIMITED"` always in this slice (finding #7). Test the stdev computation on a fixed synthetic series.

7. **`impact.py`.** `estimated_impact = counterfactual_aggregate - observed_aggregate` (sum over trajectory points with a real `counterfactual_value`); `impact_pct_of_observed`/`impact_pct_of_counterfactual`; `impact_direction` read from the KPI's declared orientation — check whether `stage01_reconciliation_ingestion/semantic_contract.py` already declares a per-KPI direction (design doc §42 wants this, not a hardcoded "higher is better"); if it doesn't, declare a small local `KPI_DIRECTIONS` dict here for the 5 real KPIs (all "higher is better" in this dataset — no cost KPI exists — state that plainly rather than building unused generality). `recovered_potential = estimated_impact` when direction is favorable. Test the aggregation and direction sign on a fixed trajectory fixture.

8. **`output_schema.py`.** Assert: no `CounterfactualImpact` for a `NON_IDENTIFIABLE_JOINT` hypothesis carries a per-member field; no `estimation_status="ESTIMATED"` entry lacks a `stage5b_basis`-equivalent (i.e., every ESTIMATED entry really did come from step 4's 5b-match, not a fallback); `Stage8Result.estimates` is empty and `abstained_upstream=True` whenever `stage7_result.abstained`; no entry for an excluded `UNKNOWN` hypothesis; `sum(p.estimated_impact for p in trajectory if not None) ≈ estimated_impact` within tolerance; `impact_lower <= estimated_impact <= impact_upper`.

9. **`stage8.py` + `test_stage8.py`.** Orchestrator: `run_stage8(cur, episode_id, stage7_result, stage5b_result)` → `Stage8Result`, iterating eligible hypotheses through steps 5-8. CLI replays the full chain via `stage7_bridge` (mirroring `stage7.py`'s own `main()`, one layer deeper) — `should_fork`/`run_stage5b` reused directly, not re-derived a second time. Write every offline test first (steps 1-8's fixtures, no DB), run them, fix everything they catch, **then one single live-DB run against episode 15** (same cluster the chain happens to land on, per Stage 7's own test — not necessarily the seeded evidence cluster) to confirm the real chain produces a sane `Stage8Result` and to sanity-check the reconstruction's aggregate impact against Stage 5b's own reported `contribution` for the same hypothesis (should be in the same ballpark, not necessarily identical — a large divergence is worth a second look, not an automatic bug). Not a diagnostic per module.

## Tests and validation gate

```bash
cd pipeline/stage08_counterfactual_impact
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_sm   # transitively needed via stage7_bridge -> stage6
.venv/bin/python test_stage8.py       # must print OK: offline fixtures (steps 1-8) +
                                       # one live Stage 3->4->5a/5c->[5b]->6->7->8 run, episode 15
```

## Acceptance criteria

- [ ] `test_stage8.py` prints `OK`
- [ ] Stage 8 does not run (`abstained_upstream=True`, `estimates=[]`) when `stage7_result.abstained`
- [ ] Every `ESTIMATED` entry has a real matching Stage 5b `CauseContribution` — no hypothesis is estimated from Stage 5a probability or a bare baseline alone
- [ ] A joint (`NON_IDENTIFIABLE_JOINT`) hypothesis produces exactly one `CounterfactualImpact`, never a per-member split
- [ ] `UNKNOWN`-confidence hypotheses are skipped by default (`MECHANISM_UNAVAILABLE`/`STAGE7_UNKNOWN`, per `config.ALLOW_UNKNOWN=False`)
- [ ] `trajectory` aggregation reconciles with `estimated_impact` within tolerance
- [ ] `impact_direction` is read from a declared KPI orientation, never assumed
- [ ] Uncertainty is explicitly `uncertainty_status="LIMITED"`, never presented as calibrated
- [ ] No mechanism class reads `daily_state` or any other Layer 1 raw table
- [ ] `engine_version` present on every `Stage8Result`
- [ ] README states the mechanism-registry finding and the other real-contract corrections plainly (matching every prior stage's convention)

## Risks

- **The single biggest risk is the mechanism-availability finding itself turning out too narrow in practice.** Since `router.should_fork()` only forks on narrow-margin, multi-dimension-concentration clusters, most investigated clusters across the 150-episode dataset will have *no* Stage 5b result at all, meaning Stage 8 returns `MECHANISM_UNAVAILABLE` for every hypothesis on most runs. This is the honest, stated consequence of the architecture boundary above — not a bug — but it may make live demos look sparse. The lever, if a demo needs more `ESTIMATED` results, is widening Stage 5b's own fork criteria or `--n-per-cause` basis size (already flagged as Stage 5b's own known gap), not inventing a second Stage 8 mechanism.
- **Recovery is implicit, not modeled** (finding #5) — if Stage 4's window genuinely extends well past real recovery, the reconstruction would keep subtracting `share * residual` from days that shouldn't still show an effect. Not fixable without either a declared recovery profile (no simulator-justified one has been traced yet) or trusting Stage 4's window boundary as already recovery-bounded (unverified).
- **Uncertainty interval is a first pass, explicitly `LIMITED`** — same caveat every prior stage's first-slice knobs carry, stated here rather than presented as calibrated.
- **`impact_direction`'s "all 5 KPIs are higher-is-better" claim** needs a live check against `semantic_contract.py` before hardcoding — if a cost-style KPI exists there already, reuse its declared direction instead of asserting a new one.
- Time budget: Stage 9 (recommendation assembly) still needs to ship after this one for the stated EOD target.
