"""lever -> atomic action (design doc §16). Joint hypotheses: mechanism/lever/
action resolved per actionable member cause (deduplicated, sorted for
determinism), combined into one action description -- never a fabricated
per-member split (design doc §41's "joint remediation" pattern, plan step 4).
"""

from config import LEVER_ACTIONS
from lever_resolver import resolve_lever
from mechanism_resolver import resolve_mechanism


def resolve_actionable_members(member_causes):
    """[(cause, mechanism, lever, atomic_action, default_owner, risk_tier), ...]
    for every member cause with a real declared mechanism, sorted by cause name
    for a deterministic primary/secondary split. A non-actionable cause (e.g.
    "seasonal", see config.NON_ACTIONABLE_CAUSES) is silently excluded here --
    it stays in `driver` for provenance but contributes no mechanism/lever/
    action/owner."""
    resolved = []
    for cause in sorted(set(member_causes)):
        mechanism = resolve_mechanism(cause)
        if mechanism is None:
            continue
        lever = resolve_lever(mechanism)
        atomic_action, default_owner, risk_tier = LEVER_ACTIONS[lever]
        resolved.append((cause, mechanism, lever, atomic_action, default_owner, risk_tier))
    return resolved


def build_action(member_causes):
    """(mechanism: list[str], lever: str|None, action_type: str|None,
    risk_tier: str|None). All None/empty when no member cause is actionable --
    design doc §10's "no valid action mechanism" case. lever/action_type/
    risk_tier collapse to the primary (first, sorted) actionable member when
    more than one exists; every distinct lever still survives in a
    " + "-joined string so a joint action never silently drops a member's
    lever."""
    resolved = resolve_actionable_members(member_causes)
    if not resolved:
        return [], None, None, None

    mechanisms = sorted({m for _, m, _, _, _, _ in resolved})
    levers = sorted({l for _, _, l, _, _, _ in resolved})
    lever = levers[0] if len(levers) == 1 else " + ".join(levers)
    _primary_cause, _primary_mechanism, _primary_lever, action_type, _owner, risk_tier = resolved[0]
    return mechanisms, lever, action_type, risk_tier


def resolve_target_scope(decomposition_result, flagged_facets_fn):
    """{dimension: slice_value} bound once per Stage 9 run (facets are
    cluster-level, not hypothesis-level -- plan step 4) and reused for every
    action. Empty dict when there's no decomposition to bind against, or when
    entity_scope_filter.flagged_facets legitimately found nothing to flag
    (plan finding #3 -- never fabricated as "Global")."""
    if decomposition_result is None:
        return {}
    facets = flagged_facets_fn(decomposition_result)
    return {dimension: slice_value for dimension, slice_value in facets}
