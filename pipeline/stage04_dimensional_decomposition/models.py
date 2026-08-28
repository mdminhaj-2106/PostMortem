"""Stage 4 output contract. See docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md
§5 -- adapted to real day_offset windows instead of ISO dates (.claude/plans/stage4-dimensional-decomposition.md).

Flattened, matching this project's established dataclass style
(pipeline/stage01_reconciliation_ingestion/models.py, .../stage02_significance_detection/models.py,
.../stage03_cross_kpi_correlation/models.py).
"""

from dataclasses import dataclass, field
from typing import List, Optional

DIMENSIONS = ("region", "segment", "product")
ELIGIBILITIES = ("ELIGIBLE", "LIMITED_HISTORY", "LOW_CONFIDENCE", "INSUFFICIENT_DATA")


@dataclass
class SliceResult:
    kpi_name: str
    dimension: str
    slice_value: str
    window_start_day_offset: int
    window_end_day_offset: int
    expected: float
    observed: float
    deviation_pct: Optional[float]
    unusualness_percentile: Optional[float]
    eligibility: str

    def __post_init__(self):
        if self.dimension not in DIMENSIONS:
            raise ValueError(f"invalid dimension: {self.dimension!r}")
        if self.eligibility not in ELIGIBILITIES:
            raise ValueError(f"invalid eligibility: {self.eligibility!r}")


@dataclass
class DecompositionResult:
    episode_id: int
    cluster_id: Optional[str]
    slices: List[SliceResult] = field(default_factory=list)
