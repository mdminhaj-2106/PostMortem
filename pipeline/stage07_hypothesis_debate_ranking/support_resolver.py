"""Step 5 (design doc §18): deterministic reason-code assignment, no scoring.
Determines a support level without producing final confidence -- that's
confidence_resolver.py's job alone.
"""

from cause_config import HIGH_CLASSIFIER_SUPPORT_FLOOR, HIGH_CONTRIBUTION_SHARE_FLOOR


def resolve_support(hypothesis, analytical_evidence, supporting_evidence, structural_evidence):
    codes = []
    a = analytical_evidence

    if a.stage5a_probability is not None and a.stage5a_probability >= HIGH_CLASSIFIER_SUPPORT_FLOOR:
        codes.append("HIGH_CLASSIFIER_SUPPORT")
    if a.stage5b_share is not None and a.stage5b_share >= HIGH_CONTRIBUTION_SHARE_FLOOR:
        codes.append("HIGH_MOVEMENT_CONTRIBUTION")
    # STRONG is the highest strength Stage 6 evidence can reach in this slice
    # (models.STRENGTHS drops the design doc's NONE/DIRECT tiers -- plan finding #5),
    # so it stands in for "direct observational support" here.
    if any(e.strength == "STRONG" for e in supporting_evidence):
        codes.append("DIRECT_OBSERVATIONAL_SUPPORT")
    elif supporting_evidence:
        codes.append("OBSERVATIONAL_SUPPORT")
    if len(supporting_evidence) >= 2:
        codes.append("MULTIPLE_INDEPENDENT_SOURCES")
    if hypothesis.hypothesis_type == "COMPOUND":
        codes.append("NON_IDENTIFIABLE_JOINT_SUPPORT")
    if structural_evidence.dependency_consistent:
        codes.append("EXPECTED_DEPENDENCY")
    if a.stage5c_is_borrowed:
        codes.append("BORROWED_ANALOG_SUPPORT")

    if not codes:
        level = "NONE"
    elif "DIRECT_OBSERVATIONAL_SUPPORT" in codes and (
        "HIGH_CLASSIFIER_SUPPORT" in codes or "HIGH_MOVEMENT_CONTRIBUTION" in codes
    ):
        level = "STRONG"
    elif (
        "HIGH_CLASSIFIER_SUPPORT" in codes
        or "HIGH_MOVEMENT_CONTRIBUTION" in codes
        or "DIRECT_OBSERVATIONAL_SUPPORT" in codes
    ):
        level = "MEANINGFUL"
    else:
        level = "WEAK"

    return level, codes
