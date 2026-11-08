"""Feasibility = capability feasibility + context feasibility (design doc §21).

Capability: stubbed AVAILABLE for every declared owner team -- single-company
hackathon demo, no multi-tenant capability system exists to query (plan finding
#4). Still a real lookup against config.CAPABILITY_AVAILABLE, not a bare
rubber stamp, and correctly reports UNAVAILABLE when no owner could be
resolved at all (no valid action mechanism).

Context: real check that the bound scope isn't internally contradictory.
Can't happen today given action_builder's single facet-per-dimension binding
(entity_scope_filter.flagged_facets already dedupes per dimension), but the
check stays real in case a future scope source is added (plan step 6).
"""

from config import CAPABILITY_AVAILABLE


def capability_feasibility(owner):
    """(status, reasons) -- status in models.CAPABILITY_STATUSES."""
    if owner is None:
        return "UNAVAILABLE", ["NO_VALID_ACTION_MECHANISM"]
    if CAPABILITY_AVAILABLE.get(owner, False):
        return "AVAILABLE", []
    return "UNAVAILABLE", [f"CAPABILITY_UNAVAILABLE:{owner}"]


def context_feasibility(target_scope):
    """(status, reasons) -- status in models.CONTEXT_STATUSES. A scope entry
    with an empty/None slice_value is contradictory (claims a dimension is
    flagged but names no value)."""
    reasons = [f"CONTEXT_INVALID:{dimension}" for dimension, slice_value in target_scope.items() if not slice_value]
    if reasons:
        return "CONTEXT_INVALID", reasons
    return "VALID", []
