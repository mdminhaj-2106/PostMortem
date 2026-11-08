"""cause -> mechanism, declared only (design doc §13). See
.claude/plans/stage9-recommendation-assembly.md step 3.
"""

from config import CAUSE_MECHANISMS, NON_ACTIONABLE_CAUSES


def resolve_mechanism(cause):
    """The declared mechanism for a real actionable cause, or None for a
    non-actionable pseudo-cause (e.g. "seasonal" -- see config.py). Raises for
    anything outside the closed vocabulary -- should never happen given Stage
    7/8's own Hypothesis validation, but assert loudly rather than silently
    fall through."""
    if cause in NON_ACTIONABLE_CAUSES:
        return None
    if cause not in CAUSE_MECHANISMS:
        raise ValueError(f"undeclared cause: {cause!r}")
    return CAUSE_MECHANISMS[cause]
