"""Stage 5c output contract. See .claude/plans/stage5c-cold-start-analogy-handler.md.

Flattened, matching this project's established dataclass style
(pipeline/stage04_dimensional_decomposition/models.py, .../stage05a_.../models.py,
.../stage05b_.../models.py).
"""

from dataclasses import dataclass, field
from typing import List, Optional

STATUSES = ("BORROWED", "NO_REFERENCE_AVAILABLE")
ANALOG_SOURCES = ("CROSS_EPISODE_CORPUS",)
CONFIDENCE_TIERS = ("BORROWED",)


@dataclass
class BorrowedAttribution:
    kpi_name: str
    dimension: str
    slice_value: str
    deviation_pct: float
    borrowed_percentile: Optional[float]
    reference_sample_count: int
    status: str
    analog_source: str = "CROSS_EPISODE_CORPUS"
    confidence_tier: str = "BORROWED"

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"invalid status: {self.status!r}")
        if self.analog_source not in ANALOG_SOURCES:
            raise ValueError(f"invalid analog_source: {self.analog_source!r}")
        if self.confidence_tier not in CONFIDENCE_TIERS:
            raise ValueError(f"invalid confidence_tier: {self.confidence_tier!r}")
        has_percentile = self.borrowed_percentile is not None
        if (self.status == "BORROWED") != has_percentile:
            raise ValueError(
                f"status={self.status!r} contradicts borrowed_percentile="
                f"{self.borrowed_percentile!r} -- a slice is either borrowed or it is not"
            )
        if self.reference_sample_count < 0:
            raise ValueError(f"reference_sample_count must be non-negative: {self.reference_sample_count!r}")


@dataclass
class Stage5cResult:
    episode_id: int
    cluster_id: Optional[str]
    attributions: List[BorrowedAttribution] = field(default_factory=list)
