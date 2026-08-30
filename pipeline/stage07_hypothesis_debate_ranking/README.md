# Stage 7 — Hypothesis Debate & Ranking

**Status:** First implementation slice built and passing (`test_stage7.py`, offline + one live-DB end-to-end run). Importable Python functions + a CLI, no FastAPI wiring yet.

**Design report:** [`docs/02-stage-design-reports/stage7-hypothesis-debate-ranking-architecture.md`](../../docs/02-stage-design-reports/stage7-hypothesis-debate-ranking-architecture.md) — the mechanism (constrained hypothesis construction, evidence support/contradiction/confidence resolution via a deterministic rule table, ranking with ties, abstention) is followed. Several of its input assumptions were written before Stage 5a/5b/5c/6 shipped and turned out wrong — corrected here, stated plainly rather than silently narrowed.

**Implementation plan:** [`.claude/plans/stage7-hypothesis-debate-ranking.md`](../../.claude/plans/stage7-hypothesis-debate-ranking.md) — has the full reasoning behind every correction below.

**Real-contract corrections from the design doc (read before touching this stage again):**
1. Cause vocabulary is the real 4-class `CAUSE_FAMILIES` (+ `seasonal`/`unexplained` pseudo-causes from Stage 5b), not an open taxonomy — `test_stage7.py` asserts this stays equal to Stage 5b's own copy.
2. Compound hypotheses are built **only** from Stage 5b's `NON_IDENTIFIABLE_JOINT` components (mechanism 9.1). Mechanisms 9.2 (Stage 7 building its own compound from a declared relationship) and 9.3 (ad-hoc evidence-supported pairing) are out of scope — `DEPENDENT_PAIRS` is already consumed by Stage 5b's own `identifiability.py` before a joint ever reaches Stage 7, and there is no declared combination-policy config anywhere in this repo for 9.3. Building either would double-count or fabricate.
3. A cause absorbed into a joint bucket still gets its own competing `SINGLE` hypothesis (matches the design doc's own §26 ranking example, where `product_outage` appears both inside a joint and alone) — this is deliberate, not a dedup bug.
4. Stage 5b only runs when `router.should_fork()` returns true (narrow top-2 margin + ≥2 dimensions concentrating). Most clusters never get a Stage 5b result at all; Stage 7 resolves confidence from Stage 5a + Stage 6 alone in that case.
5. A `NON_IDENTIFIABLE_JOINT` component can have more than 2 members — the one live Stage 5b run merged all 5 candidates (4 causes + seasonal) into one `FULLY_MERGED` bucket. `candidate_assembler.py`/`hypothesis_builder.py` are generic over member count, not hardcoded to pairs.
6. **Stage 5c attributes a KPI slice (`kpi_name, dimension, slice_value`), not a cause** — there's no `cause` field on `BorrowedAttribution` to link to a specific hypothesis. Reduced rule: if any slice in the decomposition needed cross-episode borrowing, `stage5c_is_borrowed=True` is applied uniformly to every hypothesis in the run, and the `BORROWED → max POSSIBLE` cap (design doc §30) applies to all of them alike. Coarser than the design doc's per-hypothesis model, stated here rather than silently narrowed.
7. **Stage 6's real `EvidenceItem` carries no `candidate_causes`/`support_direction`/`strength`** — only `sentiment`, `relevance_score`, and scope fields. Worse, Stage 6's own semantic ranking already queries against `fingerprint_result.top_cause`, so its evidence set is implicitly retrieved *for* that one cause already. `evidence_observational.py` links every Stage 6 item only to the hypothesis (or hypotheses, if `top_cause` is also a joint member) containing `top_cause` — every other candidate hypothesis gets no Stage 6 evidence in this slice. `direction` comes from `sentiment` (negative→SUPPORTING, positive→CONTRADICTING, neutral→NEUTRAL — deterministic, VADER-derived, not an LLM call); `strength` comes from `relevance_score` bucket edges calibrated against Stage 6's own live episode-15 run.
8. Stage 6's `EvidenceItem` carries no stable id/`customer_id` downstream of its own entity-scope filter, so independence grouping (design doc §16) can't be computed beyond "one evidence-list item = one independent source/entity" in this slice — `independent_source_count`/`independent_entity_count` both equal `evidence_count`.
9. Structural evidence is limited to `dependency_consistent` (a joint hypothesis's members being a declared `DEPENDENT_PAIRS` key) — `direction_consistent`/`timing_consistent` stay `None` (not evaluated), since Stage 5a carries no per-cause onset day to check them against (`stage05b/router.py`'s own admission).

**Covers in this slice:**
- `models.py` — `Hypothesis`/`RankedHypothesis`/`Stage7Result`/evidence dataclasses, real declared enums
- `cause_config.py` — probability floor, borrowed-cap policy, relevance-score strength buckets, the shared `DEPENDENT_PAIRS` declaration (kept equal to Stage 5b's own copy, asserted in `test_stage7.py`)
- `candidate_assembler.py` / `hypothesis_builder.py` — Steps 1-2, single + Stage-5b-joint-only compound construction
- `evidence_analytical.py` / `evidence_observational.py` / `evidence_structural.py` — Steps 3-4/6, corrections #6-#9 above
- `support_resolver.py` / `contradiction_resolver.py` / `confidence_resolver.py` — Steps 5/6/8-9, deterministic rule table (never a weighted score), enforces the borrowed cap and the joint non-split invariant
- `ranker.py` / `abstention.py` — Steps 10-11, competition ranking with shared `rank_group` for genuine ties, abstention when nothing defensible survives
- `output_schema.py` — Step 12, rejects a fabricated joint split and a borrowed hypothesis exceeding `POSSIBLE`
- `stage3_bridge.py`/`stage4_bridge.py`/`stage5a_bridge.py`/`stage5b_bridge.py`/`stage6_bridge.py` — re-export the real upstream `run_stageN` functions (+ needed model classes/constants for fixtures), same `sys.path`/`sys.modules`-eviction pattern as every other stage's own bridges
- `stage7.py` — orchestrator (`run_stage7`) + CLI entrypoint, prints rank/bucket/reason-codes per hypothesis

**Output contract (→ Stage 8):** `models.Stage7Result` — ranked `RankedHypothesis` list with confidence bucket, support/contradiction reason codes, evidence provenance, identifiability, and a `resolver_version`. Stage 8 answers "what would the KPI have been without it"; Stage 7 only says "this is the leading supported hypothesis" and hands over Stage 5b's contribution where available.

**Consumes:** Stage 5a's `FingerprintResult` (+ Stage 5c's `Stage5cResult` via the same `run_stage5a_and_5c` call), Stage 5b's `ConfoundedAttributionResult` (only when `router.should_fork()` is true), Stage 6's `EvidenceResult`.

**Deferred, not implemented:**
- Compound-hypothesis mechanisms 9.2/9.3 (correction #2) — would need either a real declared-relationship-to-hypothesis policy at this layer (redundant with what Stage 5b already does) or a combination-policy config that doesn't exist anywhere in this repo.
- Per-hypothesis Stage 5c linkage (correction #6) — would need Stage 5c to carry cause attribution it structurally doesn't have.
- `direction_consistent`/`timing_consistent` structural checks (correction #9) — needs Stage 5a to carry per-cause onset days; gated, not fabricated (this project's established precedent — Stage 3's Case 2, Stage 5c's mixed-cluster case).
- Multi-cause Stage 6 linkage (correction #7) — would need Stage 6's own retrieval query construction to change.
- Evidence independence beyond list-index (correction #8) — would need Stage 6 to carry a stable ticket/customer id through to `EvidenceItem`.
- Any numeric threshold beyond what's calibrated against the one live episode-15 run — same caveat every prior stage's first-slice knobs carry.
- FastAPI wiring — same phased-build reasoning as Stages 1-6.

**Run:**
```bash
cd pipeline/stage07_hypothesis_debate_ranking
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_sm
.venv/bin/python test_stage7.py            # must print OK (offline + one live episode-15 run)
.venv/bin/python stage7.py --episode-id 15
```
