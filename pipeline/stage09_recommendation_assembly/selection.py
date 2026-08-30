"""Dominance + deterministic primary/alternative selection over the real,
reduced axis set (design doc §33-37, plan step 9): stage7_confidence,
estimated_impact magnitude, context_feasibility. No arbitrary weighted score
(design doc §3.3) -- axes stay explicit, dominance removes strictly-worse
candidates, ties break on Stage 7's own rank, never a fabricated decimal.

Also resolves action conflicts (design doc §38-42) before selection, so a
losing action becomes DEFER rather than being silently discarded or
recommended alongside its conflict. config.ACTION_COMPATIBILITY_CONFLICTS
starts empty -- none of the 4 real causes' default actions oppose each other
(plan finding #8) -- so this never fires against real data; the check itself
stays real for when a future cause/lever pair does conflict.
"""

from config import ACTION_COMPATIBILITY_CONFLICTS

# Same closed vocabulary/ranking as stage07's CONFIDENCE_BUCKET_RANK -- Stage 9
# never invents its own confidence tiers, only orders the ones Stage 7 assigned.
_CONFIDENCE_RANK = {"UNKNOWN": 0, "POSSIBLE": 1, "LIKELY": 2, "KNOWN": 3}


def _impact_rank(expected_impact):
    """(has_quantified_impact, magnitude) -- an ESTIMATED impact is never
    dominated by an UNAVAILABLE one at the same confidence tier (plan step 9),
    regardless of the ESTIMATED value's size."""
    if expected_impact is None:
        return (0, 0.0)
    return (1, abs(expected_impact))


def _context_rank(context_feasibility):
    return 1 if context_feasibility == "VALID" else 0


def _axes(candidate):
    return (
        _CONFIDENCE_RANK.get(candidate.stage7_confidence, -1),
        _impact_rank(candidate.expected_impact),
        _context_rank(candidate.context_feasibility),
    )


def _dominates(a, b):
    axes_a, axes_b = _axes(a), _axes(b)
    return all(x >= y for x, y in zip(axes_a, axes_b)) and any(x > y for x, y in zip(axes_a, axes_b))


def non_dominated(candidates):
    return [c for c in candidates if not any(_dominates(other, c) for other in candidates if other is not c)]


def resolve_conflicts(ordered, conflicts=ACTION_COMPATIBILITY_CONFLICTS):
    """Mutates decision_intent to "DEFER" on the lower-priority side of a
    declared action_type conflict. `ordered` must already be priority-sorted
    (highest first) -- only a later, lower-priority candidate can be deferred,
    never the one it conflicts with."""
    kept = []
    for candidate in ordered:
        loses_to = next(
            (other for other in kept if candidate.action_type in conflicts.get(other.action_type, ())),
            None,
        )
        if loses_to is not None:
            candidate.decision_intent = "DEFER"
        kept.append(candidate)
    return ordered


def _sort_key(candidate):
    has_value, magnitude = _impact_rank(candidate.expected_impact)
    return (
        -_CONFIDENCE_RANK.get(candidate.stage7_confidence, -1),
        -has_value,
        -magnitude,
        -_context_rank(candidate.context_feasibility),
        candidate.stage7_rank if candidate.stage7_rank is not None else 10 ** 9,
        candidate.hypothesis_id,
    )


def select_recommendations(candidates, max_alternatives=3):
    """(primary: ActionCandidate|None, alternatives: list[ActionCandidate]).
    Primary is the top of the deterministic ordering (design doc §36) among
    the non-dominated survivors; alternatives are the next non-dominated,
    materially different (distinct hypothesis_id) candidates, capped."""
    if not candidates:
        return None, []
    survivors = non_dominated(candidates)
    ordered = sorted(survivors, key=_sort_key)
    resolve_conflicts(ordered)
    primary = ordered[0]
    alternatives = [c for c in ordered[1:] if c.hypothesis_id != primary.hypothesis_id][:max_alternatives]
    return primary, alternatives
