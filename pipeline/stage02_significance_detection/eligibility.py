"""Layer 1 -- Data Eligibility Gate (design doc §5). An analytical-validity decision,
not a business-significance threshold: can this KPI's timeline be meaningfully
analyzed at all? Stage 1 already reconciled the data; this only asks whether there's
enough of it, and how much of it is imputed/unresolved rather than observed.
"""

ELIGIBLE = "ELIGIBLE"
LIMITED_HISTORY = "LIMITED_HISTORY"
LOW_CONFIDENCE = "LOW_CONFIDENCE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

MIN_OBSERVATIONS_FOR_ELIGIBLE = 30
MIN_OBSERVATIONS_FOR_LIMITED = 10
MAX_DEGRADED_FRACTION = 0.3


def _is_usable(rv):
    return rv is not None and rv.value is not None


def _is_degraded(rv):
    if rv is None or rv.value is None:
        return True
    return rv.imputation_flag != "untouched"


def assess_eligibility(
    timeline,
    min_observations_for_eligible=MIN_OBSERVATIONS_FOR_ELIGIBLE,
    min_observations_for_limited=MIN_OBSERVATIONS_FOR_LIMITED,
    max_degraded_fraction=MAX_DEGRADED_FRACTION,
):
    usable = [rv for _, rv in timeline if _is_usable(rv)]
    n_usable = len(usable)

    if n_usable < min_observations_for_limited:
        return INSUFFICIENT_DATA

    degraded_fraction = sum(1 for _, rv in timeline if _is_degraded(rv)) / max(1, len(timeline))
    if degraded_fraction > max_degraded_fraction:
        return LOW_CONFIDENCE

    if n_usable < min_observations_for_eligible:
        return LIMITED_HISTORY

    return ELIGIBLE
