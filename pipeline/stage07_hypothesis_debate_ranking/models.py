"""Stage 7 output contract. See .claude/plans/stage7-hypothesis-debate-ranking.md.

Flattened, matching this project's established dataclass style
(pipeline/stage05a_.../models.py, .../stage05b_.../models.py, .../stage06_.../models.py).
"""

from dataclasses import dataclass, field
from typing import List, Optional

# The real 4 injectable causes (pipeline/simulator/layer1_ground_truth/generate.py's
# EVENT_TYPES) -- must equal stage05a/stage05b's own copies of this list.
# test_stage7.py asserts this against stage05b's cause_config.CAUSE_FAMILIES, same
# "every declaration site must agree" discipline as test_stage5b.py.
CAUSE_FAMILIES = ("product_outage", "marketing_cut", "competitor_launch", "inventory_shortage")
SEASONAL = "seasonal"
UNEXPLAINED = "unexplained"

# unexplained is deliberately excluded -- it's Stage 5b's residual bucket, never a
# hypothesis (plan finding #2).
_KNOWN_CAUSES = set(CAUSE_FAMILIES) | {SEASONAL}

HYPOTHESIS_TYPES = ("SINGLE", "COMPOUND")
IDENTIFIABILITIES = ("IDENTIFIED", "NON_IDENTIFIABLE_JOINT")
CONFIDENCE_BUCKETS = ("KNOWN", "LIKELY", "POSSIBLE", "UNKNOWN")
CONFIDENCE_BUCKET_RANK = {"UNKNOWN": 0, "POSSIBLE": 1, "LIKELY": 2, "KNOWN": 3}
SUPPORT_LEVELS = ("STRONG", "MEANINGFUL", "WEAK", "NONE")
DIRECTIONS = ("SUPPORTING", "CONTRADICTING", "NEUTRAL")
# NONE/DIRECT dropped from the design doc's 5-level list -- unreachable from Stage
# 6's real relevance_score signal in this slice (plan finding #5).
STRENGTHS = ("STRONG", "MODERATE", "WEAK")
CONTRADICTION_STATUSES = ("NONE", "PRESENT")


@dataclass
class EvidenceReference:
    evidence_id: str
    direction: str
    strength: str
    text_snippet: str
    day_offset: int
    temporal_tag: str

    def __post_init__(self):
        if self.direction not in DIRECTIONS:
            raise ValueError(f"invalid direction: {self.direction!r}")
        if self.strength not in STRENGTHS:
            raise ValueError(f"invalid strength: {self.strength!r}")


@dataclass
class AnalyticalEvidence:
    stage5a_probability: Optional[float] = None
    stage5b_contribution: Optional[float] = None
    stage5b_share: Optional[float] = None
    stage5b_identifiability: Optional[str] = None
    stage5b_basis_provenance: Optional[str] = None
    # Stage 5c attributes a KPI slice, not a cause -- this is a coarse, uniform-
    # per-run flag, not a per-hypothesis link (plan finding #7).
    stage5c_is_borrowed: bool = False


@dataclass
class StructuralEvidence:
    dependency_consistent: Optional[bool] = None
    # Not evaluated in this slice -- Stage 5a carries no per-cause onset day, so
    # these stay None (not evaluated) rather than fabricated (plan finding #9).
    direction_consistent: Optional[bool] = None
    timing_consistent: Optional[bool] = None


@dataclass
class Hypothesis:
    hypothesis_id: str
    member_causes: List[str]
    hypothesis_type: str
    identifiability: str = "IDENTIFIED"

    def __post_init__(self):
        if self.hypothesis_type not in HYPOTHESIS_TYPES:
            raise ValueError(f"invalid hypothesis_type: {self.hypothesis_type!r}")
        if self.identifiability not in IDENTIFIABILITIES:
            raise ValueError(f"invalid identifiability: {self.identifiability!r}")
        if set(self.member_causes) - _KNOWN_CAUSES:
            raise ValueError(f"member_causes has unknown cause(s): {self.member_causes!r}")
        if self.hypothesis_type == "COMPOUND" and len(self.member_causes) < 2:
            raise ValueError("a COMPOUND hypothesis must carry >=2 member_causes")
        if self.identifiability == "NON_IDENTIFIABLE_JOINT" and len(self.member_causes) < 2:
            raise ValueError("NON_IDENTIFIABLE_JOINT must carry >=2 member_causes")


@dataclass
class RankedHypothesis:
    hypothesis_id: str
    member_causes: List[str]
    hypothesis_type: str
    identifiability: str
    borrowed: bool

    confidence_bucket: str
    confidence_reason_codes: List[str]

    analytical_evidence: AnalyticalEvidence
    supporting_evidence: List[EvidenceReference]
    contradicting_evidence: List[EvidenceReference]
    neutral_evidence: List[EvidenceReference]

    structural_evidence: StructuralEvidence

    contradiction_status: str
    contradiction_reason_codes: List[str]

    evidence_count: int
    independent_source_count: int
    independent_entity_count: int

    rank: Optional[int] = None
    rank_group: Optional[str] = None

    def __post_init__(self):
        if self.confidence_bucket not in CONFIDENCE_BUCKETS:
            raise ValueError(f"invalid confidence_bucket: {self.confidence_bucket!r}")
        if self.contradiction_status not in CONTRADICTION_STATUSES:
            raise ValueError(f"invalid contradiction_status: {self.contradiction_status!r}")


@dataclass
class Stage7Result:
    episode_id: int
    cluster_id: Optional[str]
    hypotheses: List[RankedHypothesis] = field(default_factory=list)
    abstained: bool = False
    abstention_reason_codes: List[str] = field(default_factory=list)
    resolver_version: str = "stage7-resolver-v1"
