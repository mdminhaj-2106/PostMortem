# Stage 6 — Evidence Retrieval & Linking
## Implementation Plan — PS3 BusinessIntelligence.ai, Round 2 (AIC 2026)

**Context note:** this plan assumes the B2C retail pivot — segments are `VIP / New / Returning`, not `Enterprise / SMB / Consumer`. Evidence sources are correspondingly customer- and product-centric (support tickets, live chat, product reviews), not account-centric CRM notes. Update Stage 4's `taxonomy.yaml` segment values to match before this stage is built.

**Golden example, adapted:** revenue down 8%, concentrated in North region, VIP segment, Product A. Stage 6's job: find the actual evidence explaining why, specifically among VIP customers in North who interacted with Product A — not a blanket search.

---

## 1. Purpose & Scope

Stage 6 takes the entities and time window flagged by Stages 4/5 and retrieves the unstructured evidence (support tickets, live chat, product reviews) that supports or contradicts the numeric hypothesis — tagged with timing (before/during/after the changepoint) and entity linkage, never handed to an LLM at this stage. No reasoning happens here — only retrieval, filtering, and tagging.

---

## 2. Why B2C Evidence Is Structurally Different From B2B (and why this matters for the build)

**B2B evidence (the original design):** almost entirely account-centric. A CRM note is written *about* a known company. Linking evidence to the affected entity is a single identity-resolution problem (which account does this note belong to).

**B2C evidence (this pivot) has two separate kinds, and they need different handling:**
- **Customer-centric evidence** (support tickets, live chat): tied to a specific `customer_id`, resolvable via the Identity Resolution Graph exactly as before.
- **Product-centric evidence** (reviews, ratings): tied to a `product_id`, but **often weakly or not linkable to a specific customer's segment/region at all** — many retail platforms allow reviews from guests, or the reviewer's account isn't the same identity as their purchase record. This is a genuine real-world complication, not an edge case to hand-wave.

**The design consequence:** a review can't always be confidently attributed as "VIP, North region" evidence. Forcing that attribution when it isn't actually known would be exactly the over-merge risk Stage 1 already ruled against. So every piece of evidence needs an explicit **entity-link confidence tag**, not just a yes/no on whether it was retrieved.

---

## 3. Simulator Data Requirements (must exist before Stage 6 can be tested honestly)

Per the earlier discussion: without deliberately-seeded noise, "search" is fake — the system would just be reading the one file you planted. Three categories, now in B2C terms:

| Category | What it is | Purpose |
|---|---|---|
| **Background chatter** | Generic tickets/reviews across all customers, all segments, all times — billing questions, minor UI gripes, positive reviews, unrelated feature requests | Makes the corpus a real haystack, not an empty room with one needle |
| **Decoys — wrong segment/region** | Similar-sounding complaints ("app feels slow") from customers who are New or Returning, or in a different region, around the same time | Proves the entity/segment/region filter is doing real work, not just semantic ranking alone |
| **Decoys — same customer, unrelated topic** | The actual affected VIP/North/Product-A customers also file a billing question or unrelated review in the same pre-changepoint window | Proves the semantic-relevance step is doing real work, not just "right customer = assume relevant" |
| **Real evidence** | 2-3 genuine reliability complaints/reviews from VIP, North-region customers who bought Product A, timestamped in the weeks *before* the changepoint | The actual needle |

**Sizing for a prototype:** ~150-300 total background items is enough to demonstrate a real funnel without needing a huge synthetic corpus.

---

## 4. Exact Input Contract (from Stages 4/5)

```json
{
  "cluster_id": "cluster_2026_08_c17",
  "investigation_scope": {
    "region": "North",
    "segment": "VIP",
    "product": "Product A",
    "changepoint_date": "2026-08-05"
  },
  "cause_hypothesis_context": {
    "top_cause": "product_reliability",
    "cause_probabilities": {"product_reliability": 0.71, "competitor_activity": 0.18, "...": "..."}
  }
}
```

`cause_hypothesis_context` is optional context, used only to bias the search query terms (Section 6) — Stage 6 must still retrieve evidence even if this hypothesis turns out to be wrong; it is not told to only look for confirming evidence.

---

## 5. Step 1 — Hard Entity/Segment/Region/Product Filter

**For customer-centric sources (tickets, chat):** resolve each record's identity via Stage 1's Identity Resolution Graph, then filter to records whose resolved customer matches the investigation's segment + region.

**For product-centric sources (reviews):** filter first by `product_id = Product A`. Then attempt identity resolution on the reviewer:
- **Confident match** (verified purchase, known customer_id) → check if that customer is VIP + North; if yes, keep with `entity_link_confidence: HIGH`.
- **No linkable identity** (anonymous/guest review) → **do not discard**, but do not force a segment attribution either. Keep as `entity_link_confidence: UNLINKED`, `segment_scope: null` — it's still evidence about Product A generally, just not confidently VIP-North-specific evidence. Same three-zone handling as Stage 1's entity resolution (confident / reject / ambiguous), reused a second time.

---

## 6. Step 2 — Time Window Filter

Tag every surviving record relative to `changepoint_date`:
- `BEFORE` — potential leading/causal evidence.
- `DURING` / `AFTER` — more likely a symptom (customers complaining *because* something already broke), still retained and shown, but visually and structurally distinguished, never presented as equally strong causal evidence.

This is a single date comparison — cheap, and it's what prevents the classic mistake of treating a consequence as a cause.

---

## 7. Step 3 — Semantic Relevance Ranking

**Mechanism:** embed all surviving (post-filter) text using a small pretrained sentence embedding model (`sentence-transformers`/MiniLM — local, no API cost). Embed a query built from the investigation scope + cause hypothesis (e.g., "reliability issues, crashes, product defects, Product A"). Rank surviving candidates by cosine similarity; keep anything above a declared threshold, up to a declared cap.

```python
RELEVANCE_THRESHOLD = 0.6   # config-tunable
MAX_EVIDENCE_ITEMS = 5      # config-tunable, keeps Stage 7/11's LLM context small and cheap
```

**Named-entity and sentiment tagging**, applied to surviving candidates only (not the whole corpus, to keep cost down): spaCy for entity extraction (product/customer mentions), VADER (or a small DistilBERT sentiment model) to flag complaint vs. neutral tone.

---

## 8. The Funnel (what actually gets demoed)

```
All evidence items in the system:                 ~200 (tickets + reviews, all segments/regions/products, all time)
        ↓ Filter 1: Segment + region + product scope (with confidence-tagged entity linking)
Narrowed to:                                        ~12-18
        ↓ Filter 2: Time window (BEFORE changepoint prioritized)
Narrowed to:                                        ~6-9
        ↓ Filter 3: Semantic relevance ranking (≥0.6 similarity, capped at 5)
Final evidence set to Stage 7:                      2-4 — the real, planted evidence
```

This funnel, with real numbers printed at each stage, is a genuinely strong thing to show a judge — and it's honest, because the noise at every level is real, deliberately-seeded data, not a staged absence of alternatives.

---

## 9. Exact Output Schema (to Stage 7)

```json
{
  "cluster_id": "cluster_2026_08_c17",
  "evidence": [
    {
      "source_type": "support_ticket",
      "text_snippet": "App crashed twice this week, very frustrating for a product I paid extra for.",
      "timestamp": "2026-07-22",
      "temporal_tag": "BEFORE",
      "entity_link_confidence": "HIGH",
      "segment_scope": "VIP",
      "region_scope": "North",
      "product_scope": "Product A",
      "relevance_score": 0.83,
      "sentiment": "negative"
    },
    {
      "source_type": "product_review",
      "text_snippet": "Kept freezing on checkout, had to restart twice.",
      "timestamp": "2026-07-28",
      "temporal_tag": "BEFORE",
      "entity_link_confidence": "UNLINKED",
      "segment_scope": null,
      "region_scope": null,
      "product_scope": "Product A",
      "relevance_score": 0.79,
      "sentiment": "negative"
    }
  ]
}
```

**Hard rule:** `entity_link_confidence: UNLINKED` items are still passed forward — they're real, relevant evidence about the product — but Stage 7 must never present them with the same specificity as `HIGH`-confidence items ("VIP customers in North said X" vs. "a Product A reviewer said X, segment unconfirmed"). The confidence tag has to survive into narration, same propagation discipline as every earlier stage.

---

## 10. Module Breakdown

```
stage6/
├── config/
│   ├── relevance_thresholds.yaml
│   └── query_templates.yaml         # maps cause hypothesis -> search query phrasing
├── identity_bridge.py               # reuses Stage 1's Identity Resolution Graph, no reimplementation
├── entity_scope_filter.py           # Section 5
├── temporal_tagger.py               # Section 6
├── embedding_index.py               # builds/queries the vector store (sqlite-vec or in-memory FAISS)
├── relevance_ranker.py              # Section 7
├── ner_sentiment_tagger.py          # spaCy + VADER, applied post-filter only
├── output_schema.py
└── run_stage6.py
```

---

## 11. Build Order

1. **Seed the three-category simulator data** (Section 3) — blocking; without this, every test below is meaningless.
2. **Confirm Stage 1's Identity Resolution Graph is importable** as a function, same reuse discipline as every other stage's cross-import.
3. **Build `entity_scope_filter.py`** — includes the three-zone confidence handling (HIGH / UNLINKED / reject) for product reviews specifically.
4. **Build `temporal_tagger.py`** — simple date comparison, trivial to test alone.
5. **Build `embedding_index.py`** — one-time embedding of the corpus at load time, or incrementally as data arrives.
6. **Build `relevance_ranker.py`** — depends on 5.
7. **Build `ner_sentiment_tagger.py`** — applied only to the final surviving candidate set, not the whole corpus, to keep this cheap.
8. **Wire `run_stage6.py`** end-to-end, print the funnel counts at each step (Section 8) for demo purposes.
9. **Run the regression test** (Section 12) before connecting to real Stage 4/5/7 interfaces.

---

## 12. Test Plan

### 12.1 Unit tests
- `entity_scope_filter`: a verified-purchase review with known customer_id correctly resolves to `HIGH` confidence; an anonymous review correctly returns `UNLINKED`, not a forced guess.
- `temporal_tagger`: dates before/after the changepoint are correctly tagged; a same-day edge case is handled explicitly (define which side it falls on, don't leave it ambiguous in code).
- `relevance_ranker`: a synthetic decoy ("billing question") scores below threshold; the planted real evidence scores above it.

### 12.2 Integration / golden-path regression test
Using the seeded three-category corpus: assert the funnel narrows from ~200 to the 2-4 real evidence items, that decoys (wrong segment, same-customer-unrelated-topic) are correctly excluded at the right filter stage (not accidentally caught by the wrong filter), and that the funnel counts at each stage are logged/printed for the demo.

### 12.3 Edge cases
- Zero evidence survives all filters (a genuinely evidence-free investigation) → Stage 6 should emit an empty evidence set explicitly, not force a low-relevance item through just to have something to show.
- A review with a corrupted/missing timestamp → excluded from temporal tagging with a logged reason, not silently mis-tagged as `BEFORE`.

---

## 13. Explicit Non-Goals for This Implementation

- No LLM calls anywhere in this stage — embeddings, NER, and sentiment are all small, fixed, non-generative models.
- No attempt to force a segment/region attribution onto an unlinkable review — `UNLINKED` is a legitimate, permanent output state, not a temporary placeholder to resolve later.
- No full-corpus NER/sentiment tagging — applied only to the post-filter survivor set, to control cost (directly serves the brief's LLM/processing-economics requirement even though no LLM is used here).
- No cross-segment evidence blending — evidence scoped to one investigation's segment/region/product does not get shared across a different investigation's scope, even if the text looks similar.
