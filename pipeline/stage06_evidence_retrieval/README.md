# Stage 6 — Evidence Retrieval & Linking

**Job:** given Stage 4's decomposition + Stage 5a's fingerprint for a cluster, pull the real seeded `support_tickets` text that actually supports the hypothesis, tag it `BEFORE`/`DURING`/`AFTER` the changepoint, and rank it by semantic relevance -- narrowing a ~150-300 item corpus down to 2-4 genuine evidence items.

**Status:** Built and passing (`test_stage6.py`, offline + live-DB). Importable Python functions + a CLI, no FastAPI wiring yet.

**Design report:** [`docs/02-stage-design-reports/stage6-evidence-retrieval-implementation-plan.md`](../../docs/02-stage-design-reports/stage6-evidence-retrieval-implementation-plan.md) -- **partially superseded**, see the implementation plan below for the corrections (stale region/product placeholders, no `taxonomy.yaml`, wrong input contract).
**Implementation plan:** [`.claude/plans/stage6-evidence-retrieval.md`](../../.claude/plans/stage6-evidence-retrieval.md)

**Scope decision (customer-centric slice, not the full design doc):** only `support_tickets` is a real backing source -- no reviews/ratings/live-chat table exists in Layer 1 at all. Product-review evidence and its `UNLINKED` entity-link-confidence path are deferred, not half-built (`models.SOURCE_TYPES`/`ENTITY_LINK_CONFIDENCES` only declare the one real value each). No identity-resolution call either: `support_tickets.customer_id` is already canonical (Layer 1 writes it directly), unlike `v_crm_customer_mapping`'s account-mapping fuzziness.

**Covers in this slice:**
- `models.py` -- `EvidenceItem`/`EvidenceResult` dataclasses, the real declared enums (`DIMENSIONS`, `TEMPORAL_TAGS`, `SENTIMENTS`, etc.)
- `entity_scope_filter.py` -- Step 1: `flagged_facets()` reuses the same top-share-of-deviation signal Stage 5a's `product_concentration` already uses, generalized to `region`/`segment`/`product`; `filter_tickets()` keeps a ticket if its customer matches ANY flagged facet (never a false joint region-AND-segment-AND-product intersection -- Stage 4 decomposes each dimension independently)
- `temporal_tagger.py` -- Step 2: `BEFORE`/`DURING`/`AFTER` vs. `window_start_day_offset`/`window_end_day_offset`, same-day boundary is `DURING` (declared, not left ambiguous), missing `day_offset` excluded rather than silently defaulted
- `embedding_index.py` -- Step 3a: `all-MiniLM-L6-v2` cosine ranking against a query built from Stage 5a's `top_cause` (mapped to real `EVENT_TYPES` wording). `RELEVANCE_THRESHOLD = 0.35` is calibrated against the real seeded corpus (real evidence scored 0.39-0.55, decoys 0.05-0.33 -- a live-verified gap, not the design doc's unverified 0.6 placeholder), still a prototype knob checked against only one seeded episode
- `ner_sentiment_tagger.py` -- Step 3b: spaCy entities + VADER sentiment, applied only to the post-ranking survivor set (never the full corpus)
- `stage4_bridge.py` / `stage5a_bridge.py` -- re-export `run_stage4`/`run_stage5a_and_5c`, same `sys.path`/`sys.modules`-eviction pattern as every other stage's own bridges
- `output_schema.py` -- validates against `models.py`'s declared enums (dual-validation pattern)
- `run_stage6.py` -- orchestrator (`run_stage6`) + CLI entrypoint, prints funnel counts at each filter stage

**Layer 1 schema extension:** `support_tickets.text` (nullable `TEXT`), applied live via `schema.sql`'s `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. Existing 765K historical rows stay `NULL` -- never retrofitted; only `seed_stage6_evidence.py`'s demo corpus (`pipeline/simulator/layer1_ground_truth/seed_stage6_evidence.py`, 188 rows across background/decoy/real-evidence categories, episode 15's `cluster_15_93_94`) carries real text.

**A real result from live verification:** running the full Stage 3→4→5a→6 chain against episode 15's `cluster_15_93_94` narrows the funnel 188 (all seeded tickets) → 78 (entity scope) → 78 (temporal tagging, none excluded) → 3 (semantic relevance ≥ 0.35, capped at 5) -- inside the plan's target 2-4 real evidence items.

**Output contract (→ Stage 7):** `models.EvidenceResult` -- a ranked, temporally-tagged, confidence-tagged evidence list per cluster, for Stage 7's hypothesis-debate agents to retrieve pre-filtered to their entity scope and time window rather than a generic RAG dump.

**Consumes:** Stage 4's `DecompositionResult` (via `stage4_bridge.py`) and Stage 5a's `FingerprintResult` (via `stage5a_bridge.py`).

**Deferred, not implemented:**
- Product-review/live-chat evidence and the `UNLINKED` entity-link-confidence tier -- no backing table exists yet; add when one does (this project's "gated, not fabricated" precedent, Stage 3's Case 2 / Stage 5c's mixed-cluster case).
- Full-corpus text backfill onto the existing 765K historical `support_tickets` rows -- belongs in `generate.py --reset` if ever wanted, not this stage.
- `RELEVANCE_THRESHOLD` calibration beyond the one seeded episode -- a real gap, not silently assumed away (see `embedding_index.py`'s docstring).
- FastAPI wiring -- same phased-build reasoning as Stages 1-5c.

**Run:**
```bash
cd pipeline/stage06_evidence_retrieval
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_sm
.venv/bin/python test_stage6.py            # must print OK (offline + live Stage 3->4->5a->6 run)
.venv/bin/python run_stage6.py --episode-id 15
```
