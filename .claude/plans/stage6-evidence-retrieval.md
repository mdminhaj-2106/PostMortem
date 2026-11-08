# Stage 6 — Evidence Retrieval & Linking (customer-centric slice)

**Design report:** `docs/02-stage-design-reports/stage6-evidence-retrieval-implementation-plan.md` — **partially superseded, verified against live schema/data, not just style; read this plan's Risk #1-#3 before that doc.** The doc already got one thing right (segments are `VIP/New/Returning`, not `Enterprise/SMB`) but gets three other things wrong, inherited from the pre-pivot Round 1 example and never corrected the way Stage 4/5a/5b/5c's own plans corrected it:

1. **Region/product placeholders are stale.** Live query against Neon (`customers`, `products`, episode 1): segments = `('New','Returning','VIP')` ✅ matches the doc. But region is a real 2-letter Olist state code (27 distinct per episode: `SP` 518846 rows, `RJ` 160567, `MG` 145453, …), not `"North"`. Product is a real Olist category string (only 4 distinct per episode: `computers_accessories`, `health_beauty`, `housewares`, `perfumery`, …), not `"Product A"`. The doc's golden example (§ header, § "North, VIP, Product A") and JSON examples (§4, §9) still use the old placeholders — every occurrence needs a real value substituted (e.g. `region: "SP"`, `product: "computers_accessories"`).
2. **`Stage 4's taxonomy.yaml` doesn't exist and never will.** `find . -iname "taxonomy*"` returns nothing anywhere in the repo. Stage 4 was already built without one — it declares `DIMENSION_APPLICABILITY` as a plain dict (`dimension_config.py`) and reads distinct segment/region/product values straight off `customers`/`products` at query time (`slice_fetcher.py`). The design doc's instruction "update Stage 4's `taxonomy.yaml` segment values to match" targets a file that was never built that way — there is nothing to update. Stage 6 must follow the same live-schema-value pattern, not introduce a new static taxonomy config.
3. **The input contract (§4) doesn't match what Stage 4/5a actually emit.** There is no single flat object with `region`/`segment`/`product`/`changepoint_date` fields. The real contract is Stage 4's `DecompositionResult` (`episode_id`, `cluster_id`, `slices: List[SliceResult]`, one `SliceResult` per `(kpi_name, dimension, slice_value)` with `window_start_day_offset`/`window_end_day_offset` as **ints**, not ISO dates) joined with Stage 5a's `FingerprintResult` (`cause_scores: Dict[str, float]` keyed by the real 4 `EVENT_TYPES` — `product_outage`/`marketing_cut`/`competitor_launch`/`inventory_shortage`, not `"product_reliability"`/`"competitor_activity"` — plus a categorical `confidence` of `LOW/MEDIUM/HIGH`, not a probability). See §4 below for the corrected shape. There is also no single "changepoint_date" anywhere in the pipeline; the closest real field is `SliceResult.window_start_day_offset` (the analysis window boundary, an int day-offset — an approximation, not an exact single-day onset marker, and `injected_events` — the only place a real onset date lives — stays held out per the project's non-negotiables).

**Also flagging, not fixing via the design doc's own mechanism:** §5's plan to run every support-ticket record through Stage 1's Identity Resolution Graph is unnecessary work — `support_tickets.customer_id` is already the canonical key (Layer 1 writes it directly), so there's no CRM-style ambiguity to resolve. That graph exists for `v_crm_customer_mapping`'s account-mapping fuzziness (Scenario 6) only. Reviews/live-chat *would* need it if a genuinely ambiguous reviewer identity existed — see Risk #1 below for why that's out of scope for this slice.

**Priority:** next in the pipeline after Stage 5a (architecture.md: `S5A --> S6`). **Branch:** `feature/stage6-evidence-retrieval`.

---

## Outcome

Given a Stage 4 cluster (`episode_id`, `cluster_id`, its flagged `SliceResult`s) and Stage 5a's `FingerprintResult` for the same cluster, Stage 6 emits a ranked, temporally-tagged, confidence-tagged evidence list drawn from real (seeded) `support_tickets` text — narrowing from the full seeded corpus (~150-300 items) down to 2-4 genuine planted-evidence items, with the funnel counts at each filter stage printed, exactly as the design doc's §8 demo requires. Product-review evidence is explicitly out of scope for this slice (Risk #1).

## Scope

**In:**
- Layer 1 schema extension: nullable `text` column on `support_tickets`, backfilled only for a freshly-seeded demo corpus (not retrofitted onto the existing 765K live rows).
- Entity/segment/region/product hard filter over support tickets, using real schema values (no identity-resolution reuse needed — see above).
- Temporal tagging (`BEFORE`/`DURING`/`AFTER` relative to `window_start_day_offset`).
- Semantic relevance ranking (`sentence-transformers`/MiniLM, local) + NER/sentiment tagging on the post-filter survivor set only.
- `run_stage6.py` wiring, funnel counts printed at each stage.

**Out (this slice):**
- Product-centric evidence (reviews/ratings/live chat) — no such table exists in Layer 1 at all (verified: `schema.sql` has only `episodes/customers/products/daily_state/orders/support_tickets/injected_events`, no reviews/chat entity). Building the `HIGH`/`UNLINKED` entity-link-confidence machinery for a data source that doesn't exist is speculative infra — add when a reviews table exists, matching this project's "gated, not fabricated" precedent (Stage 3's Case 2, Stage 5c's mixed-cluster case).
- Backfilling real text onto the existing 765K historical `support_tickets` rows — those rows were generated without text; retrofitting fabricated content onto already-generated data misrepresents it. Full-corpus text generation, if wanted later, belongs in `generate.py --reset`, not this stage.
- Multi-slice-value joint attribution (e.g. forcing one evidence item to be simultaneously "VIP AND SP AND computers_accessories") — Stage 4 decomposes each dimension independently, so Stage 6 filters per flagged `(dimension, slice_value)` facet, never assumes a false joint intersection.

## Files to read first

- `docs/02-stage-design-reports/stage6-evidence-retrieval-implementation-plan.md` — mechanism (§5-§9 still sound), read against this plan's corrections above.
- `pipeline/stage04_dimensional_decomposition/models.py` — real `SliceResult`/`DecompositionResult` shape.
- `pipeline/stage05a_fingerprint_classification/models.py` — real `FingerprintResult` shape, real `EVENT_TYPES`.
- `pipeline/stage05a_fingerprint_classification/stage4_bridge.py` — the established cross-stage import pattern (sys.path insert + sys.modules eviction) to copy for Stage 6's own `stage4_bridge.py`/`stage5a_bridge.py`.
- `pipeline/simulator/layer1_ground_truth/schema.sql` (`support_tickets`, lines ~71-78) — real columns, the `category` CHECK enum.
- `pipeline/stage01_reconciliation_ingestion/identity_resolution.py` — read to confirm it's *not* needed for tickets (already resolved above); keep the import ready for when reviews land.
- `.claude/reference/database.md`, `.claude/reference/architecture.md` — current schema/status (already read this session).

## Files to change/create

```
pipeline/simulator/layer1_ground_truth/
├── schema.sql                        # ALTER TABLE support_tickets ADD COLUMN text TEXT (nullable)
└── seed_stage6_evidence.py           # new: seeds ~150-300 category-based ticket text rows
                                       # (background/decoy/real-evidence) for one demo episode

pipeline/stage06_evidence_retrieval/
├── requirements.txt                  # sentence-transformers, spacy, vaderSentiment
├── models.py                         # EvidenceItem dataclass, TEMPORAL_TAGS, real DIMENSIONS reuse
├── stage4_bridge.py                  # reuses Stage 4's run_stage4 / DecompositionResult
├── stage5a_bridge.py                 # reuses Stage 5a's run_stage5a_and_5c / FingerprintResult
├── entity_scope_filter.py            # Step 1: segment+region+product hard filter (§5, minus identity-resolution reuse)
├── temporal_tagger.py                # Step 2: BEFORE/DURING/AFTER vs window_start_day_offset (§6)
├── embedding_index.py                # Step 3a: MiniLM embedding + cosine ranking (§7)
├── ner_sentiment_tagger.py           # Step 3b: spaCy + VADER, post-filter survivors only (§7)
├── output_schema.py                  # validates against models.py's declared enums (dual-validation pattern)
├── run_stage6.py                     # CLI entrypoint, prints funnel counts (§8)
└── test_stage6.py                    # offline + live-DB checks (§12, corrected)
```

## Implementation steps

1. **Schema extension (blocking).** `ALTER TABLE support_tickets ADD COLUMN text TEXT;` (nullable, existing rows stay `NULL` — not backfilled). Apply via `psql "$DATABASE_URL" -f schema.sql`, same live-migration discipline as the `segment` CHECK-constraint migration (`database.md`'s migration note). *Validation:* `\d support_tickets` shows the new column; existing row count unchanged; `SELECT count(*) FROM support_tickets WHERE text IS NOT NULL` returns 0 before seeding.

2. **Seed the three-category demo corpus** (design doc §3), via `seed_stage6_evidence.py`, targeting one demo episode already known to have a `product_outage` cluster (check `injected_events` — offline-scoring only, never imported by Stage 6 itself, just used by *this seeding script* to pick a realistic episode/window to seed against). Insert ~150-300 `support_tickets` rows with real `text`, spanning: background chatter (all segments/regions/products, all times), decoys-wrong-scope (similar text, different segment/region), decoys-same-customer-unrelated-topic, and 2-3 real evidence rows (real `text`, real affected segment/region/product, timestamped before the episode's `injected_events.start_day_offset` window — read only by this seeding script, which is allowed to peek at ground truth to construct a realistic test fixture; Stage 6's own pipeline code never queries `injected_events`). *Validation:* row counts per category printed; `category` values still respect the CHECK enum.

3. **`stage4_bridge.py` / `stage5a_bridge.py`** — re-derive a real `DecompositionResult` + `FingerprintResult` for the seeded episode's cluster, same `sys.path`-insert + `sys.modules`-eviction pattern as every other stage's bridge. *Validation:* returned objects pass their own stage's `__post_init__`/`output_schema.validate`.

4. **`entity_scope_filter.py`** — for each flagged `SliceResult` in the cluster (`dimension` region/segment/product, real `slice_value`), filter `support_tickets` joined to `customers` on `customer_id` down to rows matching that `(dimension, slice_value)`. No identity-resolution call (ticket `customer_id` is already canonical — see header). *Validation:* a ticket from a customer in a different segment/region is excluded; a matching ticket is kept.

5. **`temporal_tagger.py`** — tag each surviving ticket `BEFORE`/`DURING`/`AFTER` vs. the slice's `window_start_day_offset` (same-day case: falls on `DURING`, declared explicitly, not left ambiguous). *Validation:* a ticket dated before the window tags `BEFORE`; one inside tags `DURING`; one after tags `AFTER`; the same-day boundary case is asserted explicitly.

6. **`embedding_index.py`** — embed surviving tickets' `text` + a query built from the investigation scope + Stage 5a's `top_cause` (mapped to real `EVENT_TYPES` wording, e.g. `product_outage` → "outage, crash, unavailable"), rank by cosine similarity, keep ≥`RELEVANCE_THRESHOLD` (0.6, config-tunable) capped at `MAX_EVIDENCE_ITEMS` (5). *Validation:* a background/decoy item scores below threshold; a real-evidence item scores above it.

7. **`ner_sentiment_tagger.py`** — spaCy entity extraction + VADER sentiment, applied only to the post-ranking survivor set. *Validation:* a negative-complaint ticket tags `sentiment: negative`.

8. **`run_stage6.py`** — wires steps 4-7 in order, prints funnel counts at each stage (design doc §8), emits the `EvidenceItem` list per the corrected schema (§9, with real `segment_scope`/`region_scope`/`product_scope` values, `entity_link_confidence` always `HIGH` this slice since `UNLINKED` only applies to the out-of-scope review path).

9. **Edge cases** (design doc §12.3, still valid): zero evidence survives all filters → emit an explicit empty list, never force a low-relevance item through. A ticket with a missing/corrupted timestamp → excluded from temporal tagging with a logged reason, never silently defaulted to `BEFORE`.

## Tests and validation gate

- `test_stage6.py`, offline: `entity_scope_filter` on a small fixture (no live DB) — wrong-segment ticket excluded, matching-segment ticket kept; `temporal_tagger`'s same-day boundary case; `embedding_index`'s decoy-scores-below/real-scores-above assertion using two hardcoded strings (no live DB needed for this part).
- `test_stage6.py`, live-DB: run against the seeded demo episode — assert the funnel narrows from the seeded ~150-300 total down to 2-4 real evidence items, and that wrong-segment/wrong-topic decoys are excluded at the filter stage that should catch them (not accidentally caught by a later stage).
- Gate: `.venv/bin/python test_stage6.py` prints `OK`.

## Acceptance criteria

- [ ] `support_tickets.text` column added live, existing rows untouched (still `NULL`), migration applied via `psql -f schema.sql`.
- [ ] Seeded demo corpus (~150-300 rows) covers all four categories from design doc §3, real values only (`VIP/New/Returning`, real state codes, real Olist categories).
- [ ] `entity_scope_filter.py` uses live schema values directly, no `taxonomy.yaml`, no identity-resolution call for tickets.
- [ ] `stage4_bridge.py`/`stage5a_bridge.py` consume the real `DecompositionResult`/`FingerprintResult` dataclasses, not the design doc's flat JSON shape.
- [ ] Funnel counts print at each stage; final output matches §9's schema (corrected field values).
- [ ] `test_stage6.py` passes offline + live-DB, printing `OK`.
- [ ] Product-review evidence explicitly absent from this slice's code and tests (not half-built).

## Risks

1. **Product-centric evidence has no backing data source at all** (no reviews/ratings/live-chat table in Layer 1). This is bigger than a naming fix — it's a missing entity. Descoped from this slice (see Scope/Out); revisit only if the team decides a reviews table is worth a Layer 1 schema addition + regeneration.
2. **`window_start_day_offset` is an approximation of "changepoint," not an exact onset day** — the real onset date lives only in `injected_events` (held out, non-negotiable #5). The BEFORE/DURING/AFTER tagging is therefore only as precise as Stage 4's analysis window, a known, accepted imprecision inherited from every upstream stage.
3. **Seeding script reads `injected_events` to build a realistic fixture** — this is allowed (it's test-fixture construction, not pipeline logic) but must never be imported by `run_stage6.py`/any non-test module; enforce this the same way Stage 2's live scoring check keeps `injected_events` access confined to test/eval code only.
4. **`RELEVANCE_THRESHOLD`/`MAX_EVIDENCE_ITEMS` are prototype knobs**, not validated against real embedding behavior on this project's specific short ticket-text style — same caveat as Stage 2's `target_candidate_rate` (architecture.md's Known Risks).
