"""Step 10 (design doc §26-27): ordering by confidence bucket, then independent
evidence, then analytical support (Stage 5a probability, then Stage 5b share),
then structural consistency, then contradiction burden. Genuine ties share the
same rank AND rank_group (competition ranking, e.g. 1,1,3 -- design doc §27's own
example shows two hypotheses both at rank=1) instead of a fabricated ordering.
"""

from models import CONFIDENCE_BUCKET_RANK


def _sort_key(rh):
    return (
        CONFIDENCE_BUCKET_RANK[rh.confidence_bucket] * -1,  # KNOWN first
        -rh.independent_source_count,
        -(rh.analytical_evidence.stage5a_probability or 0.0),
        -(rh.analytical_evidence.stage5b_share or 0.0),
        0 if rh.structural_evidence.dependency_consistent else 1,
        1 if rh.contradiction_status == "PRESENT" else 0,
    )


def rank(ranked_hypotheses):
    ordered = sorted(ranked_hypotheses, key=_sort_key)
    group = "A"
    current_rank = 1
    prev_key = None
    for i, rh in enumerate(ordered, start=1):
        key = _sort_key(rh)
        if prev_key is not None and key != prev_key:
            group = chr(ord(group) + 1)
            current_rank = i
        rh.rank = current_rank
        rh.rank_group = group
        prev_key = key
    return ordered
