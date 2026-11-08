"""Step 2 (design doc §8-9): the only place allowed to create Hypothesis objects.

A cause absorbed into a joint bucket still gets its own competing SINGLE
hypothesis alongside the COMPOUND one -- this is not an oversight, it matches the
design doc's own §26 ranking example, where `product_outage` appears both inside
`product_outage + marketing_cut` (rank 1) and alone (rank 4): Stage 5a's
classifier and Stage 5b's joint-attribution gate are separate evidentiary claims
about the same cause, not mutually exclusive ones.
"""

from models import Hypothesis


def build_hypotheses(single_causes, joint_candidates):
    hypotheses = []
    for i, members in enumerate(joint_candidates):
        hypotheses.append(Hypothesis(
            hypothesis_id=f"H_JOINT_{i}",
            member_causes=sorted(members),
            hypothesis_type="COMPOUND",
            identifiability="NON_IDENTIFIABLE_JOINT",
        ))
    for cause in single_causes:
        hypotheses.append(Hypothesis(
            hypothesis_id=f"H_{cause}",
            member_causes=[cause],
            hypothesis_type="SINGLE",
            identifiability="IDENTIFIED",
        ))
    return hypotheses
