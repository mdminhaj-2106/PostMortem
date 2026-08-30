"""Step 8-9 (design doc §23-25, §40-43): deterministic rule table, not a weighted
score. Precedence per §41: hard contradiction first (unless strong independent
evidence survives it), then support-level-driven bucket assignment, then the
borrowed cap applied last (§12/§30 -- a BORROWED hypothesis can never resolve
above BORROWED_MAX_BUCKET without independent native evidence, which here means
support_level reaching STRONG/MEANINGFUL from Stage 6 rather than the borrowed
flag alone).
"""

from cause_config import BORROWED_MAX_BUCKET
from models import CONFIDENCE_BUCKET_RANK


def _cap(bucket, max_bucket):
    return bucket if CONFIDENCE_BUCKET_RANK[bucket] <= CONFIDENCE_BUCKET_RANK[max_bucket] else max_bucket


def resolve_confidence(support_level, support_codes, contradiction_status, analytical_evidence, structural_evidence):
    reason_codes = list(support_codes)
    borrowed = analytical_evidence.stage5c_is_borrowed

    # §42: a contradiction is not blindly overridden by a raw Stage 5a probability
    # or Stage 5b share -- only genuinely STRONG independent support survives it.
    if contradiction_status == "PRESENT" and support_level != "STRONG":
        reason_codes.append("CONFLICTING_EVIDENCE")
        return ("POSSIBLE" if borrowed else "UNKNOWN"), reason_codes

    if support_level == "STRONG" and "DIRECT_OBSERVATIONAL_SUPPORT" in reason_codes:
        bucket = "KNOWN"
    elif support_level == "STRONG" or (support_level == "MEANINGFUL" and "MULTIPLE_INDEPENDENT_SOURCES" in reason_codes):
        bucket = "LIKELY"
    elif support_level == "MEANINGFUL" or borrowed:
        bucket = "POSSIBLE"
    else:
        bucket = "UNKNOWN"
        reason_codes.append("NO_EVIDENCE" if support_level == "NONE" else "INSUFFICIENT_EVIDENCE")

    if borrowed:
        capped = _cap(bucket, BORROWED_MAX_BUCKET)
        if capped != bucket:
            reason_codes.append("BORROWED_CAP_APPLIED")
        bucket = capped

    return bucket, reason_codes
