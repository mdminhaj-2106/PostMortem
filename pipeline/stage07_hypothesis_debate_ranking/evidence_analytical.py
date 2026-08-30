"""Step 3 (design doc §10-12): Stage 5a/5b/5c outputs -> AnalyticalEvidence per
hypothesis. Never relabels Stage 5a's classifier probability as a Stage 5b
contribution share -- the two fields stay separate on every hypothesis (design
doc's still-valid rule, §2/§10).
"""

from models import AnalyticalEvidence


def _stage5b_contribution_for(hypothesis, stage5b_result):
    """The one CauseContribution matching this hypothesis exactly -- a SINGLE
    hypothesis matches a single-cause (IDENTIFIED) contribution only, never a
    joint one it happens to be a member of (that joint's numbers belong to the
    joint hypothesis alone, design doc §29). Returns None when the cause was
    absorbed into a joint bucket instead -- the SINGLE hypothesis still exists
    (hypothesis_builder.py) but carries no 5b fields, 5a evidence still applies."""
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


def build_analytical_evidence(hypothesis, fingerprint_result, stage5b_result, cold_start_result):
    stage5a_probability = None
    if len(hypothesis.member_causes) == 1:
        stage5a_probability = fingerprint_result.cause_scores.get(hypothesis.member_causes[0])

    contribution = _stage5b_contribution_for(hypothesis, stage5b_result)

    return AnalyticalEvidence(
        stage5a_probability=stage5a_probability,
        stage5b_contribution=contribution.contribution if contribution else None,
        stage5b_share=contribution.share if contribution else None,
        stage5b_identifiability=contribution.identifiability if contribution else None,
        stage5b_basis_provenance=contribution.basis_provenance if contribution else None,
        # Stage 5c attributes a KPI slice, not a cause (plan finding #7) -- coarse,
        # uniform-per-run flag applied to every hypothesis alike, not a per-cause link.
        stage5c_is_borrowed=bool(cold_start_result and cold_start_result.attributions),
    )
