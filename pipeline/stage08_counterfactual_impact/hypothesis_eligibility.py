"""Step: which Stage 7 ranked hypotheses are counterfactually estimable at all.
See .claude/plans/stage8-counterfactual-impact-engine.md's central finding --
the only validated quantitative mechanism in this codebase is Stage 5b's fitted
contribution share; nothing else (no per-cause mechanism re-simulating Layer 1
internals, which nothing downstream of Layer 2 may query) exists to estimate from.
"""

from config import ALLOW_UNKNOWN


def _stage5b_contribution_for(hypothesis, stage5b_result):
    """Mirrors Stage 7's own evidence_analytical._stage5b_contribution_for -- same
    matching rule (single hypothesis -> IDENTIFIED contribution with the same
    cause; compound hypothesis -> NON_IDENTIFIABLE_JOINT contribution with the
    same member set). Kept independent rather than bridging across Stage 7 a
    second time for one small function."""
    if stage5b_result is None:
        return None
    if len(hypothesis.member_causes) == 1:
        target = hypothesis.member_causes[0]
        for c in stage5b_result.contributions:
            if c.identifiability == "IDENTIFIED" and c.cause == target:
                return c
        return None
    target_members = set(hypothesis.member_causes)
    for c in stage5b_result.contributions:
        if c.identifiability == "NON_IDENTIFIABLE_JOINT" and set(c.member_causes or []) == target_members:
            return c
    return None


def assess(hypothesis, stage5b_result):
    """(eligible: bool, contribution_or_None, reason_codes: list[str])."""
    if hypothesis.confidence_bucket == "UNKNOWN" and not ALLOW_UNKNOWN:
        return False, None, ["STAGE7_UNKNOWN"]

    contribution = _stage5b_contribution_for(hypothesis, stage5b_result)
    if contribution is None:
        return False, None, ["NO_VALIDATED_INTERVENTION_MECHANISM"]

    return True, contribution, ["STAGE5B_QUANTITATIVE_CONSTRAINT"]
