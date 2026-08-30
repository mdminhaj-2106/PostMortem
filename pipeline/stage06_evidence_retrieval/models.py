"""Stage 6 output contract. See .claude/plans/stage6-evidence-retrieval.md.

Flattened, matching this project's established dataclass style
(pipeline/stage04_dimensional_decomposition/models.py,
pipeline/stage05a_fingerprint_classification/models.py).
"""

from dataclasses import dataclass, field
from typing import List, Optional

# Same 3 dimensions Stage 4 decomposes (pipeline/stage04_dimensional_decomposition/models.py).
DIMENSIONS = ("region", "segment", "product")

# product_review is deferred -- no reviews/ratings/live-chat table exists in Layer 1 at all
# (plan Scope/Out, Risk #1). Only real backing source this slice has.
SOURCE_TYPES = ("support_ticket",)

TEMPORAL_TAGS = ("BEFORE", "DURING", "AFTER")

# UNLINKED only applies to the out-of-scope product-review path (design doc §5) --
# every support_ticket carries a canonical customer_id already, so this slice's
# evidence is always a confident, known-identity match.
ENTITY_LINK_CONFIDENCES = ("HIGH",)

SENTIMENTS = ("negative", "neutral", "positive")


@dataclass
class EvidenceItem:
    source_type: str
    text_snippet: str
    day_offset: int
    temporal_tag: str
    entity_link_confidence: str
    segment_scope: Optional[str]
    region_scope: Optional[str]
    product_scope: Optional[str]
    relevance_score: float
    sentiment: str

    def __post_init__(self):
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"invalid source_type: {self.source_type!r}")
        if self.temporal_tag not in TEMPORAL_TAGS:
            raise ValueError(f"invalid temporal_tag: {self.temporal_tag!r}")
        if self.entity_link_confidence not in ENTITY_LINK_CONFIDENCES:
            raise ValueError(f"invalid entity_link_confidence: {self.entity_link_confidence!r}")
        if self.sentiment not in SENTIMENTS:
            raise ValueError(f"invalid sentiment: {self.sentiment!r}")
        if not self.text_snippet:
            raise ValueError("evidence item must carry real text")


@dataclass
class EvidenceResult:
    episode_id: int
    cluster_id: Optional[str]
    evidence: List[EvidenceItem] = field(default_factory=list)
