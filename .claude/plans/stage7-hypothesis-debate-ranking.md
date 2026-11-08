# Stage 7 — Hypothesis Debate & Ranking (first slice, reduced scale)

**Design report:** `docs/02-stage-design-reports/stage7-hypothesis-debate-ranking-architecture.md`
**Branch:** `feature/stage7-hypothesis-debate-ranking` (off `develop`)
**Consumes:** Stage 5a (`FingerprintResult`), Stage 5b (`ConfoundedAttributionResult`, only when the router forks), Stage 5c (`Stage5cResult`), Stage 6 (`EvidenceResult`), Stage 4 (`DecompositionResult`, for structural facets)

## Outcome

For episode 15's `cluster_15_93_94` (the same real cluster every stage since 5a has been live-verified against), Stage 7 emits a `Stage7Result` with one ranked hypothesis per Stage 5a candidate cause (`cause_scores >= 0.05`) plus, if Stage 5b's router forked on this cluster, one additional compound hypothesis per `NON_IDENTIFIABLE_JOINT` component — each carrying a `KNOWN`/`LIKELY`/`POSSIBLE`/`UNKNOWN` confidence bucket derived from a deterministic rule table (never a weighted score), reason codes, supporting/contradicting Stage 6 evidence, and an explicit `abstained` flag when no hypothesis clears the defensibility bar. `test_stage7.py` prints `OK` offline, plus one live-DB run against episode 15.

## Real contracts vs. the design doc (read this before writing any code)

The design report was written before Stage 5a/5b/5c/6 shipped, so several of its input assumptions are wrong. Corrections, found by reading the actual `models.py`/`cause_config.py` of each upstream stage (not re-deriving live — see `.claude/reference/architecture.md`'s build-status table):

1. **Cause vocabulary is 4 values, not an open taxonomy.** `EVENT_TYPES = ("product_outage", "marketing_cut", "competitor_launch", "inventory_shortage")` (`stage05a_fingerprint_classification/models.py`, `stage05b_confounded_cause_decomposer/cause_config.py:CAUSE_FAMILIES` — both must agree, `test_stage5b.py` already asserts this against the simulator's own `EVENT_TYPES`). Stage 7's `cause_config.py` must declare the same 4 and assert equality the same way.
2. **`seasonal`/`unexplained` are real pseudo-causes Stage 5b can emit**, not something Stage 7 invents (design doc §46 forbids inventing seasonal — it's fine here because Stage 5b is the declared upstream source). `unexplained` is a residual bucket, never promoted to a hypothesis; `seasonal` can become a `SINGLE` hypothesis if Stage 5b emits it as its own contribution, or a member of a joint bucket.
3. **Stage 5a's real output is a flat `Dict[cause, float]` summing to 1.0** (`cause_scores`) + `top_cause` + `confidence` (LOW/MEDIUM/HIGH) — not the design doc's per-cause `{probability, rank, margin, fingerprint support}` objects. Use `cause_scores` directly as `AnalyticalEvidence.stage5a_probability`; `confidence` feeds `evidence_quality`, not the bucket directly.
4. **Stage 5b only runs when `router.should_fork()` returns True** (narrow top-2 margin + ≥2 dimensions independently concentrating in Stage 4's decomposition — `stage05b_confounded_cause_decomposer/router.py`). Most clusters never get a Stage 5b result at all; Stage 7 must resolve confidence from Stage 5a + Stage 6 alone in that case, exactly as design doc §4.2 already anticipates ("when Stage 5b was invoked").
5. **A `NON_IDENTIFIABLE_JOINT` component can have >2 member causes.** The one live Stage 5b run merged all 5 candidates (4 causes + seasonal) into one `FULLY_MERGED` bucket with `basis_sample_count=5` (`stage05b_confounded_cause_decomposer/README.md`'s live-verification note) — build the joint hypothesis from `CauseContribution.member_causes` generically (`list[str]`, not a hardcoded pair).
6. **The declared cause-dependency relationship already exists and is already consumed upstream.** `cause_config.DEPENDENT_PAIRS = {("product_outage", "marketing_cut"): (3, 10)}` feeds Stage 5b's `identifiability.py` directly — by the time a joint component reaches Stage 7, the dependency has already produced the joint bucket. **Design doc mechanism 9.2 (Stage 7 constructing its own compound from a declared relationship) is therefore redundant with mechanism 9.1 and is out of scope for this slice** — implementing it a second time at Stage 7 would double-count the same relationship. Mechanism 9.3 (evidence-supported ad-hoc combination) has no declared combination-policy config anywhere in the repo — also out of scope; building it now would be exactly the "arbitrary Cartesian product" the design doc itself forbids. **Compound hypotheses in this slice come only from Stage 5b's `NON_IDENTIFIABLE_JOINT` components (mechanism 9.1).**
7. **Stage 5c attributes a KPI *slice* (`kpi_name, dimension, slice_value`), not a cause.** `Stage5cResult.attributions` carries no `cause` field at all — it tells you a decomposition slice was thin and had to borrow a cross-episode reference percentile, nothing about which of the 4 causes that implicates. There is no clean per-hypothesis link. **Reduced rule for this slice:** if `cold_start_result.attributions` is non-empty for the investigated cluster (any slice in this decomposition needed cross-episode borrowing), mark `analytical_evidence.stage5c_is_borrowed = True` uniformly on every hypothesis in the run, and apply the `BORROWED → max POSSIBLE` cap (§30) to all of them alike. This is coarser than the design doc's per-hypothesis borrowing model — stated here plainly, not silently narrowed. A per-cause link would require Stage 5c to carry cause attribution it structurally doesn't have (see `stage05c_cold_start_analogy_handler/README.md`'s own finding that eligibility is uniform per `(kpi, dimension)`, not per cause).
8. **Stage 6's real `EvidenceItem` has no `candidate_causes`/`support_direction`/`strength` fields** (design doc §4.4/§13-16 assumed Stage 6 hands over pre-linked, pre-classified evidence; it doesn't). What it actually carries: `source_type`, `text_snippet`, `day_offset`, `temporal_tag` (BEFORE/DURING/AFTER), `entity_link_confidence` (always HIGH in this slice), `segment_scope`/`region_scope`/`product_scope`, `relevance_score` (0-1 float), `sentiment` (negative/neutral/positive, VADER-derived — deterministic, not an LLM call, so this doesn't violate the LLM-boundary rule). Critically, **Stage 6's own semantic ranking already queries against `fingerprint_result.top_cause`** (`embedding_index.build_query`), so its evidence set is implicitly retrieved *for* the single top-scoring cause, not multi-cause. Stage 7's `evidence_observational.py` must therefore:
   - Link every Stage 6 `EvidenceItem` to the hypothesis containing `top_cause` (single or, if `top_cause` is a member of a joint bucket, the compound hypothesis) — not to every candidate hypothesis. Hypotheses that don't contain `top_cause` get no Stage 6 evidence in this slice; that's an honest reflection of what Stage 6 actually retrieved, not a bug to route around today.
   - Derive `direction` from `sentiment`: `negative → SUPPORTING`, `positive → CONTRADICTING`, `neutral → NEUTRAL`. Deterministic mapping, no free-text interpretation.
   - Derive `strength` from `relevance_score` buckets calibrated once against the live episode-15 run (Stage 6's README: real evidence scored 0.39-0.55 there) — e.g. `>=0.45 STRONG`, `>=0.35 MODERATE` (the retrieval floor is already 0.35, nothing survives below it), else unreachable/`WEAK`. Confirm the actual bucket edges against the live run in the validation step, don't guess and ship.
   - `EvidenceItem` carries no stable id or `customer_id` downstream of Stage 6 (dropped after the entity-scope filter) — **independence grouping (§16) cannot be computed** beyond "one Stage 6 evidence list item = one independent source/entity" in this slice. Use the list index as `evidence_id`; `independent_source_count`/`independent_entity_count` both equal `evidence_count`. State this as a real gap (same as Stage 6's own README states its `RELEVANCE_THRESHOLD` gap), not silently assumed.
9. **Structural evidence is limited to what's actually computable.** Stage 5a's `FingerprintResult` carries no per-cause onset day (`router.py`'s own admission — this is why the router doesn't check `DEPENDENT_PAIRS` timing either). Stage 7 cannot evaluate `timing_consistent` or `direction_consistent` for real; only `dependency_consistent` is computable (a joint hypothesis's `member_causes` pair being a `DEPENDENT_PAIRS` key). Leave `direction_consistent`/`timing_consistent` as `None` (not evaluated) rather than fabricating `True`/`False` — matches the project's "gated, not fabricated" precedent (Stage 3's Case 2, Stage 5c's mixed-cluster case).

## Scope

**In:** input validation against the real upstream contracts above; candidate assembly from Stage 5a (+ Stage 5b joint, when present); `SINGLE`/`COMPOUND` hypothesis construction; analytical evidence from 5a/5b/5c; observational evidence from Stage 6 (top-cause-linked only, per #8); the `dependency_consistent`-only structural check; deterministic support/contradiction/confidence resolution via a rule table; ranking with tie groups; abstention; `output_schema.py` validation (enum-only vocabulary, no member-level split on a joint, borrowed cap enforced); `resolver_version`.

**Out (stated, not hidden):** mechanisms 9.2/9.3 compound construction (#6); per-hypothesis Stage 5c linkage (#7); `direction_consistent`/`timing_consistent` structural checks (#9); multi-cause Stage 6 linkage (#8); evidence independence beyond list-index (#8); any numeric-confidence-threshold tuning beyond the one live episode; FastAPI wiring.

## Files to read first

- `docs/02-stage-design-reports/stage7-hypothesis-debate-ranking-architecture.md` — mechanism (§2-30 especially; §31-32 for the dataclass shapes to adapt, not copy verbatim)
- `pipeline/stage05a_fingerprint_classification/models.py`, `stage5a.py` — real `FingerprintResult`, `run_stage5a_and_5c`
- `pipeline/stage05b_confounded_cause_decomposer/models.py`, `cause_config.py`, `router.py`, `stage5b.py` — real `ConfoundedAttributionResult`, `DEPENDENT_PAIRS`, fork gate
- `pipeline/stage05c_cold_start_analogy_handler/models.py` — real `Stage5cResult`
- `pipeline/stage06_evidence_retrieval/models.py`, `run_stage6.py`, `README.md` — real `EvidenceResult`, the top-cause-only retrieval bias
- `pipeline/stage04_dimensional_decomposition/models.py` — `DecompositionResult` (for the one facet flag Stage 6 already used, reused here only if needed by structural checks)
- Any stage's `output_schema.py` + `test_stage*.py` for the dual-validation / plain-assert pattern to match

## Files to change/create

```
pipeline/stage07_hypothesis_debate_ranking/
├── README.md                (rewrite — currently a stub)
├── requirements.txt          (python-dotenv, psycopg2-binary only — no new deps)
├── models.py                 (Hypothesis, AnalyticalEvidence, EvidenceReference,
│                               StructuralEvidence, HypothesisResolution,
│                               RankedHypothesis, Stage7Result — flattened dataclasses,
│                               same style as stage06/models.py)
├── cause_config.py           (CAUSE_FAMILIES == 5b's, SEASONAL/UNEXPLAINED,
│                               CANDIDATE_PROBABILITY_FLOOR=0.05, BORROWED_MAX="POSSIBLE",
│                               RELEVANCE_STRENGTH_BUCKETS)
├── candidate_assembler.py    (Stage 5a floor filter + Stage 5b joint component -> candidates)
├── hypothesis_builder.py     (candidates -> Hypothesis objects, SINGLE/COMPOUND)
├── evidence_analytical.py    (5a/5b/5c -> AnalyticalEvidence per hypothesis)
├── evidence_observational.py (Stage 6 EvidenceItem list -> EvidenceReference per hypothesis,
│                               top_cause-linked, sentiment->direction, relevance->strength)
├── evidence_structural.py    (DEPENDENT_PAIRS membership -> dependency_consistent only)
├── support_resolver.py       (support level + reason codes, no final confidence)
├── contradiction_resolver.py (contradiction status + reason codes; retain+downgrade default)
├── confidence_resolver.py    (rule table -> KNOWN/LIKELY/POSSIBLE/UNKNOWN; enforces
│                               borrowed cap + joint non-split)
├── ranker.py                 (confidence bucket -> independent evidence -> analytical
│                               support -> 5b share -> structural -> contradiction burden;
│                               ties share rank_group)
├── abstention.py             (ABSTAIN when no hypothesis clears the bar)
├── output_schema.py          (validate against declared enums + joint/borrowed invariants)
├── stage3_bridge.py / stage4_bridge.py / stage5a_bridge.py / stage5b_bridge.py /
│   stage6_bridge.py          (re-export pattern from stage06's own bridges — same
│                               sys.path/sys.modules-eviction convention)
├── stage7.py                 (orchestrator: run_stage7() + CLI entrypoint)
└── test_stage7.py
```

## Implementation steps

1. **`models.py` + `cause_config.py`.** Declare the 4 real `CAUSE_FAMILIES` (assert-equal to 5b's, same discipline as `test_stage5b.py`), `SEASONAL`/`UNEXPLAINED`, confidence bucket enum (`KNOWN`/`LIKELY`/`POSSIBLE`/`UNKNOWN`), support/strength/direction enums per design doc §14-15. `HypothesisResolution`/`RankedHypothesis`/`Stage7Result` dataclasses per design doc §31-32, trimmed to fields this slice actually populates (drop `provenance_status`/`freshness` sub-objects if evidence.py #8's gap means they'd always be the same placeholder value — state that trim in the README instead of shipping dead fields). Validation: no live DB needed.

2. **`candidate_assembler.py`.** From `fingerprint_result.cause_scores`, keep causes `>= CANDIDATE_PROBABILITY_FLOOR`. If a Stage 5b result exists, add one candidate per `CauseContribution` whose `identifiability == "NON_IDENTIFIABLE_JOINT"` (its `member_causes` list, joined). Test: floor filter drops a low-probability cause; a 5-way `FULLY_MERGED` joint (the real live case) produces exactly one 5-member candidate, not an error.

3. **`hypothesis_builder.py`.** One `SINGLE` hypothesis per single-cause candidate; one `COMPOUND` hypothesis per joint candidate, carrying `identifiability="NON_IDENTIFIABLE_JOINT"`. Test: joint hypothesis never gets a per-member probability split (assert only the joint-level fields exist).

4. **`evidence_analytical.py`.** Map `cause_scores[cause]` → `stage5a_probability`; if Stage 5b ran, map the matching `CauseContribution.share`/`.contribution`/`.basis_provenance` → the 5b fields (joint hypothesis reads its own joint `CauseContribution`, singles read theirs if `identifiability_verdict != FULLY_MERGED` merged them away — handle the case where a single candidate has no matching 5b contribution because it got absorbed into the joint bucket: 5a evidence still applies, 5b fields stay `None`). `stage5c_is_borrowed` per rule #7. Test against a synthetic fixture covering: 5a-only, 5a+5b-clean-split, 5a+5b-fully-merged, 5a+5c-borrowed.

5. **`evidence_observational.py`.** Link every `EvidenceItem` to the hypothesis containing `fingerprint_result.top_cause` (rule #8). `direction` from `sentiment`, `strength` from `relevance_score` bucket (confirm the bucket edges against the live episode-15 run in step 12, don't hardcode blind). `evidence_id` = list index, `independent_source_count`/`independent_entity_count` = `evidence_count` (state the gap in a comment, not silently). Test: a negative-sentiment, high-relevance item produces `SUPPORTING`/`STRONG`; a positive-sentiment item produces `CONTRADICTING`.

6. **`evidence_structural.py`.** `dependency_consistent = True` iff the compound hypothesis's `member_causes` (as an unordered pair check across all adjacent pairs) is a `DEPENDENT_PAIRS` key; `direction_consistent`/`timing_consistent` stay `None`. Single hypotheses get an all-`None` `StructuralEvidence` (nothing to check). Test: a joint with `product_outage`+`marketing_cut` gets `dependency_consistent=True`; any other pairing gets `False`.

7. **`support_resolver.py`.** Deterministic reason-code assignment per design doc §18's pattern (`HIGH_CLASSIFIER_SUPPORT` if `stage5a_probability >= 0.5`, `HIGH_MOVEMENT_CONTRIBUTION` if `stage5b_share >= 0.5`, `DIRECT_OBSERVATIONAL_SUPPORT` if any `SUPPORTING` evidence with `strength >= STRONG`, `NON_IDENTIFIABLE_JOINT_SUPPORT` if compound). Output a `support` level (`STRONG`/`MEANINGFUL`/`WEAK`/`NONE`) from the reason-code set, not a score. Test each reason code fires on the fixture that should trigger it and only that one.

8. **`contradiction_resolver.py`.** `contradiction_status = PRESENT` iff any `CONTRADICTING` evidence exists; default action is `retain + downgrade` (design doc §20's stated default), never silent removal. Test: a `CONTRADICTING` item downgrades but doesn't delete the hypothesis.

9. **`confidence_resolver.py`.** Rule table per design doc §23/§40, in the precedence order of §41 (hard borrowed/joint constraints first, then contradiction, then direct evidence, then multiple independent evidence, then analytical, then structural, then borrowed-only). Enforce: `stage5c_is_borrowed and no other independent support → cap at POSSIBLE` (never `LIKELY`/`KNOWN`); joint hypothesis confidence is evaluated at the joint level only. Test the 4 bucket outcomes + the borrowed-cap test + a Stage-5a-vs-Stage-6-conflict test (§42: high 5a probability + a `CONTRADICTING` Stage 6 item → `UNKNOWN`, not the raw 0.8x preserved as confidence).

10. **`ranker.py`.** Sort by confidence bucket, then independent evidence count, then `stage5a_probability`/`stage5b_share`, then `dependency_consistent`, then contradiction burden (descending penalty). Equal-on-all-tested-fields hypotheses share a `rank_group`. Test a synthetic 2-hypothesis tie produces the same `rank_group`.

11. **`abstention.py`.** `abstained=True` when every hypothesis is `UNKNOWN`, or candidates is empty, or the only candidate has `identifiability=NON_IDENTIFIABLE_JOINT` with `FULLY_MERGED`-level evidence quality and no independent Stage 6 support (i.e. nothing defensible survives). Ranked candidates still emitted per design doc §28. Test each trigger.

12. **`output_schema.py` + `stage7.py` + bridges + `test_stage7.py`.** Bridges follow stage06's exact `sys.path`/`sys.modules`-eviction pattern (copy the working convention, including the `stage5c_bridge` cache-retention wrinkle if the call chain routes through `run_stage5a_and_5c` again). `stage7.py` orchestrates: `run_stage3 → run_stage4 → run_stage5a_and_5c → router.should_fork → run_stage5b (if forked) → run_stage6 → run_stage7`. Write all offline tests first (steps 1-11, no DB), run them, fix everything they catch, **then one single live-DB run against episode 15's `cluster_15_93_94`** to confirm the real chain produces a sane `Stage7Result` and to calibrate the `relevance_score` strength-bucket edges from #5 against real numbers — not a diagnostic per module.

## Tests and validation gate

```bash
cd pipeline/stage07_hypothesis_debate_ranking
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_stage7.py       # must print OK: offline fixtures (step 1-11 cases)
                                       # + one live Stage 3->4->5a/5c->[5b]->6->7 run, episode 15
```

## Acceptance criteria

- [ ] `test_stage7.py` prints `OK`
- [ ] Candidate causes only from Stage 5a floor + Stage 5b joint (no invented causes)
- [ ] A `NON_IDENTIFIABLE_JOINT` component (2-way or N-way) never gets a member-level probability/contribution split — `output_schema.py` rejects it if it did
- [ ] `stage5c_is_borrowed=True` hypotheses cannot resolve above `POSSIBLE` without independent Stage 6 support
- [ ] Stage 5a probabilities are stored as `stage5a_probability`, never relabeled as a contribution share
- [ ] Confidence buckets come from the rule table in `confidence_resolver.py`, not an inline weighted formula anywhere
- [ ] Ranking is deterministic; genuine ties share a `rank_group` instead of a fabricated ordering
- [ ] `abstained=True` case emits the full ranked candidate list, not an empty result
- [ ] No LLM call anywhere in this stage
- [ ] `resolver_version` present on every `Stage7Result`
- [ ] README states the 9 real-contract corrections above plainly (matching Stage 5b/5c/6's own "scope cuts stated, not hidden" convention)

## Risks

- **Stage 6 top-cause-only linkage (#8)** means a hypothesis Stage 5a scored second-highest gets zero Stage 6 evidence even if real evidence for it exists in `support_tickets` — Stage 6's own retrieval never looked for it. Only fixable by changing Stage 6's query construction (out of scope today, not a Stage 7 bug).
- **Stage 5c's slice-level (not cause-level) borrowing (#7)** means the borrowed cap is coarser than the design doc intends — could over-cap a hypothesis that has nothing to do with the thin slice. Flagged, not fixed, given today's deadline.
- **Independence counting (#8)** degenerates to "1 item = 1 independent source" — if Stage 6 ever returns near-duplicate tickets from the same customer, Stage 7 would overcount independent confirmation. Not observed in the one live corpus (188→3 real items, no duplicates), but not structurally prevented.
- **Strength-bucket edges for `relevance_score`** are a fresh calibration, not empirically validated beyond one episode — same caveat every prior stage's first-slice knobs carry (5a's `PRODUCT_CONCENTRATION_THRESHOLD`, 6's `RELEVANCE_THRESHOLD`).
- Time budget: Stages 8-11 still need to ship today after this one — if Stage 7 runs long, prefer shipping steps 1-11 with a smaller live-DB check over polishing the abstention edge cases further.
