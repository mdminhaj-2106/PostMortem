"""Stage 5a output contract. See .claude/plans/stage5a-fingerprint-classification.md.

Flattened, matching this project's established dataclass style
(pipeline/stage03_cross_kpi_correlation/models.py, pipeline/stage04_dimensional_decomposition/models.py).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# The real 4 injectable causes (pipeline/simulator/layer1_ground_truth/generate.py's
# EVENT_TYPES) -- not the design doc's 8-class taxonomy. Must agree with that list;
# same "every declaration site must agree" discipline as stage02/ingest.py's KPI_NAMES.
EVENT_TYPES = ("product_outage", "marketing_cut", "competitor_launch", "inventory_shortage")
CONFIDENCES = ("LOW", "MEDIUM", "HIGH")


@dataclass
class FingerprintResult:
    episode_id: int
    cluster_id: Optional[str]
    cause_scores: Dict[str, float] = field(default_factory=dict)
    top_cause: Optional[str] = None
    confidence: str = "LOW"
    signals_used: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.confidence not in CONFIDENCES:
            raise ValueError(f"invalid confidence: {self.confidence!r}")
        if set(self.cause_scores) - set(EVENT_TYPES):
            raise ValueError(f"cause_scores has unknown event types: {self.cause_scores!r}")
        if self.cause_scores:
            total = sum(self.cause_scores.values())
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"cause_scores must sum to 1.0, got {total}")
