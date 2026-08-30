"""Step 6 (design doc §21-22, corrected per plan finding #9): only
dependency_consistent is computable from real upstream output -- Stage 5a carries
no per-cause onset day (stage05b/router.py's own admission), so
direction_consistent/timing_consistent stay None (not evaluated) rather than
fabricated. Structural evidence cannot prove causation and never creates a
candidate from nothing (design doc §22) -- it only annotates hypotheses that
already exist.
"""

from itertools import combinations

from cause_config import DEPENDENT_PAIRS
from models import StructuralEvidence


def build_structural_evidence(hypothesis):
    if hypothesis.hypothesis_type != "COMPOUND":
        return StructuralEvidence()
    members = hypothesis.member_causes
    dependency_consistent = any(
        (a, b) in DEPENDENT_PAIRS or (b, a) in DEPENDENT_PAIRS
        for a, b in combinations(members, 2)
    )
    return StructuralEvidence(dependency_consistent=dependency_consistent)
