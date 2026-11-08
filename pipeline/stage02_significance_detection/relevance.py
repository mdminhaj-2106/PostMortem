"""Layer 6 -- Relevance Resolution (design doc §14). Interpretable rules, not an
unexplained weighted formula. Priority tiers per §15.
"""

VERY_HIGH_CUTOFF = 0.98
HIGH_CUTOFF = 0.90
MEDIUM_CUTOFF = 0.70


def _unusualness_tier(score, very_high_cutoff, high_cutoff, medium_cutoff):
    if score is None:
        return "low"
    if score >= very_high_cutoff:
        return "very_high"
    if score >= high_cutoff:
        return "high"
    if score >= medium_cutoff:
        return "medium"
    return "low"


def resolve_relevance(
    unusualness_score,
    importance_level,
    has_relationship_context,
    very_high_cutoff=VERY_HIGH_CUTOFF,
    high_cutoff=HIGH_CUTOFF,
    medium_cutoff=MEDIUM_CUTOFF,
):
    """Design doc §14's matrix, row by row, then a conservative fallback for
    combinations the table doesn't spell out. Returns (relevance_level, priority_tier)."""
    tier = _unusualness_tier(unusualness_score, very_high_cutoff, high_cutoff, medium_cutoff)

    if tier == "low":
        # row: Low unusualness + any importance + any context -> Not relevant
        return "NOT_RELEVANT", None

    if tier in ("high", "very_high") and importance_level in ("HIGH", "CRITICAL"):
        # row: High unusualness + High importance + any context -> High
        return "HIGH", 1

    if tier == "very_high" and importance_level == "MEDIUM" and has_relationship_context:
        # row: Very high unusualness + Medium importance + strong connection -> High
        return "HIGH", 2

    if tier == "very_high" and importance_level in ("LOW", "NONE") and not has_relationship_context:
        # row: Very high unusualness + Low importance + no context -> Low
        return "LOW", 4

    if tier == "medium" and importance_level == "CRITICAL":
        # row: Medium unusualness + Critical importance -> Medium or High (taking Medium,
        # the conservative reading -- design doc leaves this ambiguous)
        return "MEDIUM", 3

    if importance_level in ("CRITICAL", "HIGH") or has_relationship_context:
        return "MEDIUM", 3
    return "LOW", 4
