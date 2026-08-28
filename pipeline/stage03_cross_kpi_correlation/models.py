"""Stage 3 output contract. See docs/02-stage-design-reports/stage3-cross-kpi-correlation-prioritization.md §8.

Flattened, matching this project's established dataclass style
(pipeline/stage01_reconciliation_ingestion/models.py, pipeline/stage02_significance_detection/models.py).
"""

from dataclasses import dataclass, field
from typing import List, Optional

PRIORITY_BASES = ("OBSERVED", "PROJECTED_UNAVAILABLE")
GROUPING_BASES = (
    "SINGLE_KPI",
    "DAG_AND_CORRELATION",
    "SEPARATE_NO_ADJACENT_KPI",
    "SEPARATE_NO_CORRELATION",
)
CONFIDENCES = ("HIGH", "MEDIUM", "LOW")


@dataclass
class StageThreeResult:
    episode_id: int
    cluster_id: Optional[str]
    kpi_names: List[str] = field(default_factory=list)
    window_start_day_offset: int = 0
    window_end_day_offset: int = 0
    priority_score: Optional[float] = None
    priority_basis: str = "PROJECTED_UNAVAILABLE"
    confidence: str = "LOW"
    grouping_basis: str = "SINGLE_KPI"

    def __post_init__(self):
        if self.priority_basis not in PRIORITY_BASES:
            raise ValueError(f"invalid priority_basis: {self.priority_basis!r}")
        if self.grouping_basis not in GROUPING_BASES:
            raise ValueError(f"invalid grouping_basis: {self.grouping_basis!r}")
        if self.confidence not in CONFIDENCES:
            raise ValueError(f"invalid confidence: {self.confidence!r}")
