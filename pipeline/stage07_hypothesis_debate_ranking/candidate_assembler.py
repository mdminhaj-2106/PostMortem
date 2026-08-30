"""Step 1 (design doc §7, corrected per the plan's finding #6): candidate causes
come from Stage 5a's cause_scores (floor-filtered) plus, when Stage 5b forked, one
candidate per NON_IDENTIFIABLE_JOINT component. Mechanisms 9.2/9.3 (Stage 7
constructing its own compound from a declared relationship or an ad-hoc pairing)
are out of scope -- DEPENDENT_PAIRS is already consumed by Stage 5b's own
identifiability gate before a joint component ever reaches here, and there is no
declared combination-policy config for 9.3 anywhere in this repo. No arbitrary
Cartesian product of causes is ever built.
"""

from cause_config import CANDIDATE_PROBABILITY_FLOOR


def assemble_single_candidates(fingerprint_result):
    """[cause, ...] -- Stage 5a candidates clearing the probability floor."""
    return [
        cause for cause, score in fingerprint_result.cause_scores.items()
        if score >= CANDIDATE_PROBABILITY_FLOOR
    ]


def assemble_joint_candidates(stage5b_result):
    """[[cause, ...], ...] -- one member list per NON_IDENTIFIABLE_JOINT component,
    generic over member count (the one live Stage 5b run merged all 5 candidates
    into one FULLY_MERGED bucket -- see stage05b's README's live-verification
    note). Empty when Stage 5b never ran (router.should_fork()==False, the common
    case)."""
    if stage5b_result is None:
        return []
    return [
        list(c.member_causes)
        for c in stage5b_result.contributions
        if c.identifiability == "NON_IDENTIFIABLE_JOINT"
    ]
