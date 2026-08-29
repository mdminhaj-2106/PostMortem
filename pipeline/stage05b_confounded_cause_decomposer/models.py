"""Stage 5b output contract. See docs/02-stage-design-reports/stage5b-confounded-cause-decomposer-revised.md §6.

Flattened, matching this project's established dataclass style.
"""

from dataclasses import dataclass, field
from typing import List, Optional

BASIS_PROVENANCES = ("LEARNED", "SEASONAL_BASELINE", "RESIDUAL")
IDENTIFIABILITIES = ("IDENTIFIED", "NON_IDENTIFIABLE_JOINT")
VERDICTS = ("CLEAN_SPLIT", "PARTIAL_MERGE", "FULLY_MERGED")


@dataclass
class CauseContribution:
    cause: str  # a CAUSE_FAMILIES member, "seasonal", "unexplained", or "a+b" (joint)
    contribution: float  # KPI units, non-negative
    share: float  # contribution / total attributed magnitude
    basis_provenance: str
    basis_sample_count: Optional[int]
    identifiability: str
    member_causes: Optional[List[str]] = None

    def __post_init__(self):
        if self.basis_provenance not in BASIS_PROVENANCES:
            raise ValueError(f"invalid basis_provenance: {self.basis_provenance!r}")
        if self.identifiability not in IDENTIFIABILITIES:
            raise ValueError(f"invalid identifiability: {self.identifiability!r}")
        if self.contribution < 0:
            raise ValueError(f"contribution must be non-negative: {self.contribution!r}")
        if self.identifiability == "NON_IDENTIFIABLE_JOINT" and (not self.member_causes or len(self.member_causes) < 2):
            raise ValueError("a NON_IDENTIFIABLE_JOINT component must carry >=2 member_causes")


@dataclass
class ConfoundedAttributionResult:
    episode_id: int
    cluster_id: Optional[str]
    kpi_name: str
    window_start_day_offset: int
    window_end_day_offset: int
    observed_deviation: float
    contributions: List[CauseContribution] = field(default_factory=list)
    unexplained_share: float = 0.0
    fit_quality: float = 0.0
    identifiability_verdict: str = "CLEAN_SPLIT"

    def __post_init__(self):
        if self.identifiability_verdict not in VERDICTS:
            raise ValueError(f"invalid identifiability_verdict: {self.identifiability_verdict!r}")
        if not any(c.cause == "unexplained" for c in self.contributions):
            raise ValueError("unexplained must always be present, never silently dropped")
