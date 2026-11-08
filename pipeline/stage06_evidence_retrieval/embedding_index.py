"""Step 3a (design doc §7): MiniLM embedding + cosine ranking, applied only to the
Step 1+2 survivor set -- never the whole corpus (design doc §13's non-goal, keeps
this stage's cost bounded the same way NER/sentiment tagging is bounded below).

RELEVANCE_THRESHOLD is a prototype knob -- but unlike the design doc's un-verified
0.6 placeholder, this one IS calibrated against this project's real seeded ticket
text (all-MiniLM-L6-v2 cosine similarity on short, single-sentence customer
complaints): a plain keyword query against the real seeded corpus
(pipeline/simulator/layer1_ground_truth/seed_stage6_evidence.py, episode 15) scored
real evidence at 0.39-0.55, same-customer-unrelated-topic decoys and background
chatter at 0.05-0.33 -- a live-verified gap, not an assumption. Still a prototype
knob in the Stage 2 target_candidate_rate sense (plan Risk #4): the margin (~0.06)
is real but not large, and was only checked against this one seeded episode's
phrasing, not a broad corpus.
"""

from sentence_transformers import SentenceTransformer, util

MODEL_NAME = "all-MiniLM-L6-v2"
RELEVANCE_THRESHOLD = 0.35
MAX_EVIDENCE_ITEMS = 5

# Maps Stage 5a's real EVENT_TYPES (pipeline/stage05a_fingerprint_classification/models.py)
# to search-query phrasing -- biases the query only, never gates retrieval (Stage 6 must
# still surface evidence even if this hypothesis is wrong, design doc §4). Plain
# keyword phrasing scored a clearly wider real-vs-decoy margin live than a
# "Customer complaints about: ..." sentence wrapper did -- see module docstring.
_CAUSE_QUERY_TERMS = {
    "product_outage": "app outage, crash, service down, cannot log in, unavailable",
    "marketing_cut": "fewer promotions, discount ended, ads stopped, deals disappeared",
    "competitor_launch": "switching to a competitor, cheaper alternative, leaving for another app",
    "inventory_shortage": "out of stock, backordered, cannot order, sold out, no inventory available",
}
_DEFAULT_QUERY_TERMS = "customer complaint, problem, frustrated, issue"

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def build_query(top_cause):
    return _CAUSE_QUERY_TERMS.get(top_cause, _DEFAULT_QUERY_TERMS)


def rank(survivors, query_text, threshold=RELEVANCE_THRESHOLD, max_items=MAX_EVIDENCE_ITEMS):
    """survivors: [(ticket, matched_dims, temporal_tag), ...], ticket=(ticket_id,
    day_offset, customer_id, text). Returns [(ticket, matched_dims, temporal_tag,
    relevance_score), ...] sorted by score desc, thresholded, capped."""
    if not survivors:
        return []
    model = _get_model()
    texts = [ticket[3] for ticket, _dims, _tag in survivors]
    embeddings = model.encode(texts, convert_to_tensor=True)
    query_embedding = model.encode(query_text, convert_to_tensor=True)
    scores = util.cos_sim(query_embedding, embeddings)[0].tolist()

    scored = [
        (ticket, dims, temporal_tag, score)
        for (ticket, dims, temporal_tag), score in zip(survivors, scores)
        if score >= threshold
    ]
    scored.sort(key=lambda row: row[3], reverse=True)
    return scored[:max_items]
