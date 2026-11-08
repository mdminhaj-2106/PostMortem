"""Stage 8 output contract. See .claude/plans/stage8-counterfactual-impact-engine.md.

Flattened, matching this project's established dataclass style. Trimmed from the
design doc's own dataclasses (§46) -- `stage5b_basis`/`interaction` sub-objects
dropped until something real populates them beyond `None` (no declared interaction
config exists anywhere in this repo -- see the plan's finding #3).
"""

from dataclasses import dataclass, field
from typing import List, Optional

MODES = ("EVENT_NEVER_OCCURRED", "REMOVE_FROM_TIME")
ESTIMATION_STATUSES = ("ESTIMATED", "UNAVAILABLE", "DATA_LIMITED", "MECHANISM_UNAVAILABLE", "INVALID_INPUT")
# All 5 real KPIs are higher-is-better in this dataset -- no cost-style KPI is
# declared anywhere (checked against semantic_contract.py, which only declares
# source bias_direction, a different concept). See impact.py.
IMPACT_DIRECTIONS = ("HIGHER_IS_BETTER",)
# This slice never claims a statistically calibrated interval (design doc §38's
# own escape hatch) -- LIMITED is the only value ESTIMATED entries carry.
UNCERTAINTY_STATUSES = ("LIMITED",)


@dataclass
class InterventionSpec:
    hypothesis_id: str
    member_causes: List[str]
    mode: str
    intervention_day_offset: Optional[int] = None

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"invalid mode: {self.mode!r}")
        if self.mode == "REMOVE_FROM_TIME" and self.intervention_day_offset is None:
            raise ValueError("REMOVE_FROM_TIME requires intervention_day_offset")


@dataclass
class CounterfactualPoint:
    day_offset: int
    observed_value: Optional[float]
    baseline_value: Optional[float]
    counterfactual_value: Optional[float]
    estimated_impact: Optional[float]
    data_confidence: str
    point_lower: Optional[float] = None
    point_upper: Optional[float] = None


@dataclass
class CounterfactualImpact:
    hypothesis_id: str
    member_causes: List[str]
    hypothesis_type: str

    scenario: str
    intervention_day_offset: Optional[int]

    observed_aggregate: Optional[float]
    counterfactual_aggregate: Optional[float]
    estimated_impact: Optional[float]
    impact_pct_of_observed: Optional[float]
    impact_direction: Optional[str]

    impact_lower: Optional[float]
    impact_upper: Optional[float]

    trajectory: List[CounterfactualPoint]

    stage7_confidence: str
    data_confidence: str
    uncertainty_status: str

    identifiability: str
    borrowed: bool

    estimation_status: str
    estimation_reason_codes: List[str]

    def __post_init__(self):
        if self.scenario not in MODES:
            raise ValueError(f"invalid scenario: {self.scenario!r}")
        if self.estimation_status not in ESTIMATION_STATUSES:
            raise ValueError(f"invalid estimation_status: {self.estimation_status!r}")
        if self.impact_direction is not None and self.impact_direction not in IMPACT_DIRECTIONS:
            raise ValueError(f"invalid impact_direction: {self.impact_direction!r}")
        if self.estimation_status == "ESTIMATED" and self.uncertainty_status not in UNCERTAINTY_STATUSES:
            raise ValueError(f"invalid uncertainty_status: {self.uncertainty_status!r}")


@dataclass
class Stage8Result:
    episode_id: int
    cluster_id: Optional[str]
    window_start_day_offset: Optional[int]
    window_end_day_offset: Optional[int]
    estimates: List[CounterfactualImpact] = field(default_factory=list)
    skipped_hypotheses: List[dict] = field(default_factory=list)
    abstained_upstream: bool = False
    engine_version: str = "stage8-engine-v1"
