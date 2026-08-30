"""Step 4 (design doc §13, corrected per plan finding #8): Stage 6's real
EvidenceItem has no candidate_causes/support_direction/strength -- Stage 6's own
semantic ranking already queries against fingerprint_result.top_cause
(embedding_index.build_query), so its evidence set is implicitly retrieved *for*
that one cause already. Every EvidenceItem links only to the hypothesis (or
hypotheses, if top_cause is also a member of a joint bucket) containing
top_cause; every other candidate hypothesis gets none in this slice -- an honest
reflection of what Stage 6 actually retrieved, not a bug to route around.

direction/strength are deterministic mappings off Stage 6's own already-computed
sentiment/relevance_score (VADER-derived, not an LLM call) -- no free-text
reinterpretation happens here.
"""

from cause_config import STRENGTH_MODERATE_FLOOR, STRENGTH_STRONG_FLOOR
from models import EvidenceReference

_SENTIMENT_DIRECTION = {"negative": "SUPPORTING", "positive": "CONTRADICTING", "neutral": "NEUTRAL"}


def _strength(relevance_score):
    if relevance_score >= STRENGTH_STRONG_FLOOR:
        return "STRONG"
    if relevance_score >= STRENGTH_MODERATE_FLOOR:
        return "MODERATE"
    return "WEAK"


def _direction(sentiment):
    return _SENTIMENT_DIRECTION[sentiment]


def link_evidence(hypotheses, evidence_result, top_cause):
    """{hypothesis_id: [EvidenceReference, ...]} for every hypothesis whose
    member_causes contains top_cause. Empty dict when top_cause is None/unset or
    there's no evidence at all."""
    target_ids = [h.hypothesis_id for h in hypotheses if top_cause in h.member_causes]
    if not target_ids or not evidence_result or not evidence_result.evidence:
        return {}

    refs = [
        EvidenceReference(
            evidence_id=f"E{i}",
            direction=_direction(item.sentiment),
            strength=_strength(item.relevance_score),
            text_snippet=item.text_snippet,
            day_offset=item.day_offset,
            temporal_tag=item.temporal_tag,
        )
        for i, item in enumerate(evidence_result.evidence)
    ]
    return {hid: refs for hid in target_ids}
