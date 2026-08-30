"""Step 6 (design doc §19-20): contradiction is evaluated independently of
support. Default action is retain + downgrade, never silent removal -- the
hypothesis stays visible but flagged (design doc §20/§21's stated prototype
default).
"""


def resolve_contradiction(contradicting_evidence):
    if not contradicting_evidence:
        return "NONE", []
    codes = ["CONTRADICTED_BY_OBSERVATIONAL_EVIDENCE"]
    if any(e.strength == "STRONG" for e in contradicting_evidence):
        codes.append("STRONG_CONTRADICTION")
    return "PRESENT", codes
