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

# Audit finding F10. A slice with no usable residual anywhere in the window used to
# report expected=0.0, observed=0.0 -- byte-identical to a slice that genuinely sold
# zero. Stage 5a would read that fabricated zero as an observed shape. These are
# opposite facts ("we don't know" vs "we know it was nothing") and must be
# distinguishable downstream.
OBSERVATION_STATUSES = ("OBSERVED", "NO_DATA_IN_WINDOW")


@dataclass
class SliceResult:
    kpi_name: str
    dimension: str
    slice_value: str
    window_start_day_offset: int
    window_end_day_offset: int
    expected: Optional[float]
    observed: Optional[float]
    deviation_pct: Optional[float]
    unusualness_percentile: Optional[float]
    eligibility: str
    observation_status: str = "OBSERVED"

    def __post_init__(self):
        if self.dimension not in DIMENSIONS:
            raise ValueError(f"invalid dimension: {self.dimension!r}")
        if self.eligibility not in ELIGIBILITIES:
            raise ValueError(f"invalid eligibility: {self.eligibility!r}")
        if self.observation_status not in OBSERVATION_STATUSES:
            raise ValueError(f"invalid observation_status: {self.observation_status!r}")
        measured = self.expected is not None or self.observed is not None
        if (self.observation_status == "OBSERVED") != measured:
            raise ValueError(
                f"observation_status={self.observation_status!r} contradicts "
                f"expected={self.expected!r}/observed={self.observed!r} -- a slice is "
                f"either measured or it is not"
            )


@dataclass
class DecompositionResult:
    episode_id: int
    cluster_id: Optional[str]
    slices: List[SliceResult] = field(default_factory=list)
