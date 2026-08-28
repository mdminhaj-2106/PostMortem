"""Prioritization (design doc §4/§5/§8). Axis 1 (Stage 2 confidence) gates
*ranking*, it never discards a result from the output -- score_priority always
computes a real score/basis per §8's "carried through" contract; gate_by_confidence
and rank() are the ranking view a caller (Stage 4, or a future rank-and-hand-off
step) applies on top. Case 2 (revenue not in cluster) has no declared equation
connecting any other KPI to revenue in this project's real 2-KPI universe (plan
Risk #1) -- gated as unavailable rather than fabricated.
"""

GATED_OUT_CONFIDENCE = "LOW"


def gate_by_confidence(confidence):
    return confidence != GATED_OUT_CONFIDENCE


def score_priority(kpi_names, window_start, window_end, residuals_by_kpi):
    """Case 1 (revenue in cluster): revenue's own observed dollar delta, summed
    over the window (design doc §5 -- "use revenue's own observed dollar change
    directly," never added to other members' movement, which is part of *why*
    revenue moved, not a separate loss). Case 2: PROJECTED_UNAVAILABLE, see module
    docstring."""
    if "revenue" not in kpi_names:
        return None, "PROJECTED_UNAVAILABLE"
    revenue_residuals = dict(residuals_by_kpi["revenue"])
    values = [r for d, r in revenue_residuals.items() if window_start <= d <= window_end and r is not None]
    if not values:
        return None, "PROJECTED_UNAVAILABLE"
    return sum(values), "OBSERVED"


def rank(results):
    """Axis 1 as a gate, Axis 2 (priority_score) as the ranking scale (design doc
    §4) -- excludes LOW-confidence or unscored results from the ranking without
    mutating or dropping them from the caller's own result list."""
    eligible = [r for r in results if gate_by_confidence(r.confidence) and r.priority_score is not None]
    return sorted(eligible, key=lambda r: r.priority_score, reverse=True)
