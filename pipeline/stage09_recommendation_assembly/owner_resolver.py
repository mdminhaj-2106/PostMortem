"""A lever's declared default_owner -> primary_owner; joint hypotheses get
every other distinct actionable member cause's owner as secondary_owners
(design doc §19-20), never implying a numeric ownership split.
"""

from action_builder import resolve_actionable_members


def resolve_owners(member_causes):
    """(primary_owner: str|None, secondary_owners: list[str]) -- primary is the
    first (sorted) actionable member cause's declared owner; secondary_owners
    are every other distinct actionable member's owner, excluding the primary.
    Both empty when no member cause is actionable."""
    resolved = resolve_actionable_members(member_causes)
    if not resolved:
        return None, []
    owners = [owner for _, _, _, _, owner, _ in resolved]
    primary = owners[0]
    secondary = sorted({o for o in owners[1:] if o != primary})
    return primary, secondary
