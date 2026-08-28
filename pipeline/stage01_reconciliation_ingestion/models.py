"""Stage 1 output contract. See docs/02-stage-design-reports/stage1-reconciliation-design.md §7.

Every value Stage 1 hands to Stage 2 is a ReconciledValue -- never a bare number -- so
downstream stages can treat a shaky, heavily-imputed estimate with appropriate caution
instead of as an equally-trustworthy observation.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence, Tuple

CONFIDENCE_TIERS = ("exact", "aggregated", "estimated", "triangulated", "declared_unresolved")
IMPUTATION_FLAGS = ("untouched", "partially_imputed", "fully_imputed")


@dataclass
class ReconciledValue:
    episode_id: int
    day_offset: int
    kpi_name: str
    value: Optional[float]
    confidence_tier: str
    source_provenance: Sequence[str]
    imputation_flag: str = "untouched"
    value_range: Optional[Tuple[float, float]] = None
    imputation_method: Optional[str] = None
    uncertainty_width: Optional[float] = None
    provisional: bool = False
    provisional_resolution_date: Optional[date] = None
    version: int = 1
    restated_from_version: Optional[int] = None

    def __post_init__(self):
        if self.confidence_tier not in CONFIDENCE_TIERS:
            raise ValueError(f"invalid confidence_tier: {self.confidence_tier!r}")
        if self.imputation_flag not in IMPUTATION_FLAGS:
            raise ValueError(f"invalid imputation_flag: {self.imputation_flag!r}")
