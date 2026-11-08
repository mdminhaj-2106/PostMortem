"""Rejects any free-text field outside the declared enums, plus the two §6 contract
rules models.py's __post_init__ doesn't already cover: a cause name must be a real
member of the declared taxonomy (or a real joint combination of them), and a joint
component must never be accompanied by separate entries for its own members.
"""

from cause_config import CAUSE_FAMILIES, SEASONAL, UNEXPLAINED

_KNOWN_CAUSES = set(CAUSE_FAMILIES) | {SEASONAL, UNEXPLAINED}


def _is_known_cause(name):
    if name in _KNOWN_CAUSES:
        return True
    parts = name.split("+")
    return len(parts) > 1 and all(p in _KNOWN_CAUSES for p in parts)


def validate(result):
    named_singletons = {c.cause for c in result.contributions if c.identifiability == "IDENTIFIED"}
    for c in result.contributions:
        assert _is_known_cause(c.cause), f"free-text cause: {c.cause!r}"
        assert isinstance(c.contribution, (int, float)) and c.contribution >= 0, \
            f"non-numeric or negative contribution: {c.contribution!r}"
        assert isinstance(c.share, (int, float)), f"non-numeric share: {c.share!r}"
        if c.identifiability == "NON_IDENTIFIABLE_JOINT":
            for member in c.member_causes:
                assert member not in named_singletons, (
                    f"joint component {c.cause!r} must not be accompanied by a separate "
                    f"entry for member {member!r}"
                )
    assert any(c.cause == UNEXPLAINED for c in result.contributions), "unexplained must always be present"
