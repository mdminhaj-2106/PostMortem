"""Rejects any value outside the fixed enums, plus the two hard invariants: a
NON_IDENTIFIABLE_JOINT hypothesis never carries a fabricated per-member split,
and a borrowed hypothesis never resolves above BORROWED_MAX_BUCKET (design doc
§52-53). Same dual-validation pattern as every other stage's output_schema.py.
"""

from cause_config import BORROWED_MAX_BUCKET
from models import CONFIDENCE_BUCKET_RANK, CONFIDENCE_BUCKETS, CONTRADICTION_STATUSES, DIRECTIONS, STRENGTHS


def validate(result):
    for rh in result.hypotheses:
        assert rh.confidence_bucket in CONFIDENCE_BUCKETS, f"free-text confidence_bucket: {rh.confidence_bucket!r}"
        assert rh.contradiction_status in CONTRADICTION_STATUSES, \
            f"free-text contradiction_status: {rh.contradiction_status!r}"
        for e in rh.supporting_evidence + rh.contradicting_evidence + rh.neutral_evidence:
            assert e.direction in DIRECTIONS, f"free-text direction: {e.direction!r}"
            assert e.strength in STRENGTHS, f"free-text strength: {e.strength!r}"

        if rh.identifiability == "NON_IDENTIFIABLE_JOINT":
            assert len(rh.member_causes) >= 2, "a NON_IDENTIFIABLE_JOINT hypothesis must carry >=2 member_causes"
            assert rh.analytical_evidence.stage5a_probability is None, \
                "a joint hypothesis must never carry a fabricated per-member stage5a_probability"

        if rh.borrowed:
            assert CONFIDENCE_BUCKET_RANK[rh.confidence_bucket] <= CONFIDENCE_BUCKET_RANK[BORROWED_MAX_BUCKET], \
                f"borrowed hypothesis exceeded {BORROWED_MAX_BUCKET}: {rh.confidence_bucket!r}"
