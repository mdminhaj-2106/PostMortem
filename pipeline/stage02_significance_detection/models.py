"""Stage 2 output contract. See docs/02-stage-design-reports/stage2-relevance-extraction-architecture.md §18.

Flattened (not nested) to match this project's established dataclass style
(pipeline/stage01_reconciliation_ingestion/models.py) -- the §18 JSON's nested
objects (unusualness{}, business_importance{}, ...) become flat field groups here.
"""

from dataclasses import dataclass, field
from typing import List, Optional

ANALYSIS_STATUSES = ("ANALYZED", "INSUFFICIENT_DATA")
HISTORY_CONFIDENCES = ("HIGH", "MEDIUM", "LOW")
IMPORTANCE_LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE")
RELEVANCE_LEVELS = ("HIGH", "MEDIUM", "LOW", "NOT_RELEVANT")
CLASSIFICATION_STATES = ("NORMAL", "EMERGING", "SIGNIFICANT", "STRUCTURAL")
CONFIDENCES = ("HIGH", "MEDIUM", "LOW")


@dataclass
class StageTwoResult:
    episode_id: int
    day_offset: int
    kpi_name: str
    analysis_status: str
    confidence: str
    unusualness_score: Optional[float] = None
    unusualness_basis: Optional[str] = None
    history_confidence: Optional[str] = None
    business_importance_level: str = "NONE"
    business_importance_evidence: List[dict] = field(default_factory=list)
    cluster_id: Optional[str] = None
    related_candidates: List[str] = field(default_factory=list)
    relevance_level: str = "NOT_RELEVANT"
    priority_tier: Optional[int] = None
    classification_state: str = "NORMAL"
    classification_evidence: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.analysis_status not in ANALYSIS_STATUSES:
            raise ValueError(f"invalid analysis_status: {self.analysis_status!r}")
        if self.confidence not in CONFIDENCES:
            raise ValueError(f"invalid confidence: {self.confidence!r}")
        if self.history_confidence is not None and self.history_confidence not in HISTORY_CONFIDENCES:
            raise ValueError(f"invalid history_confidence: {self.history_confidence!r}")
        if self.business_importance_level not in IMPORTANCE_LEVELS:
            raise ValueError(f"invalid business_importance_level: {self.business_importance_level!r}")
        if self.relevance_level not in RELEVANCE_LEVELS:
            raise ValueError(f"invalid relevance_level: {self.relevance_level!r}")
        if self.classification_state not in CLASSIFICATION_STATES:
            raise ValueError(f"invalid classification_state: {self.classification_state!r}")
