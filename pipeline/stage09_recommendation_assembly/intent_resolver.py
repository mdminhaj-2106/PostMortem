"""stage7_confidence + action's declared risk_tier -> ACT/INVESTIGATE/MONITOR,
per config.CONFIDENCE_POLICY (design doc §69's decision matrix, collapsed to
what's real -- plan step 7). estimation_status (ESTIMATED vs UNAVAILABLE) does
not change the intent in this reduced policy -- only the impact numbers shown;
KNOWN/LIKELY act regardless of whether Stage 8 could quantify a dollar figure
(design doc §30's "ACT may still be possible" with expected_impact=UNAVAILABLE).

DEFER is never produced here -- it's only reachable through a real action
conflict (plan Scope: "DEFER only if a real conflict is ever detected"), which
compatibility.py resolves, not this module.
"""

from config import CONFIDENCE_POLICY


def resolve_intent(stage7_confidence, risk_tier):
    if risk_tier is None:
        # no valid action mechanism was ever resolved -- nothing to ACT on.
        return "INVESTIGATE"

    if stage7_confidence == "POSSIBLE":
        return "MONITOR" if risk_tier == "LOW_REGRET" else "INVESTIGATE"

    if stage7_confidence not in CONFIDENCE_POLICY:
        raise ValueError(f"undeclared stage7_confidence: {stage7_confidence!r}")
    return CONFIDENCE_POLICY[stage7_confidence]
