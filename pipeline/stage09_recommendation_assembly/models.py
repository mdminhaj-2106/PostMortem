"""Stage 9 output contract. See .claude/plans/stage9-recommendation-assembly.md.

Flattened, matching this project's established dataclass style. Trimmed from
the design doc's own ActionCandidate (design doc §29) -- effort/time_to_impact
stay UNKNOWN placeholders only (no config anywhere populates them, plan
Scope/Out), no monetary-cost field exists anywhere (design doc §22, plan
acceptance criteria).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

DECISION_INTENTS = ("ACT", "INVESTIGATE", "MONITOR", "DEFER")
ACTION_TYPES = (
    "RESTORE", "REPAIR", "REPLENISH", "ROLLBACK", "INCREASE", "DECREASE",
    "REALLOCATE", "INVESTIGATE", "MONITOR",
)
RISK_TIERS = ("LOW_REGRET", "HIGH_COMMITMENT")
CAPABILITY_STATUSES = ("AVAILABLE", "UNAVAILABLE")
CONTEXT_STATUSES = ("VALID", "CONTEXT_INVALID")
SUCCESS_STATUSES = ("DERIVABLE", "NOT_DERIVABLE")
DECISION_STATUSES = (
    "RECOMMENDATION_AVAILABLE", "INVESTIGATION_RECOMMENDED",
    "MONITORING_RECOMMENDED", "NO_DEFENSIBLE_ACTION",
)


@dataclass
class MonitoringPlan:
    affected_kpis: List[str]
    expected_direction: str
    monitoring_horizon: str = "NOT_SPECIFIED"


@dataclass
class SuccessCriteria:
    status: str
    basis: Optional[str] = None

    def __post_init__(self):
        if self.status not in SUCCESS_STATUSES:
            raise ValueError(f"invalid success criteria status: {self.status!r}")


@dataclass
class ActionCandidate:
    action_id: str
    hypothesis_id: str

    driver: List[str]
    mechanism: List[str]
    lever: Optional[str]

    action_type: Optional[str]
    target_scope: Dict[str, str]

    affected_kpi: str

    primary_owner: Optional[str]
    secondary_owners: List[str]

    decision_intent: str

    stage7_confidence: str
    identifiability: str
    borrowed: bool

    expected_impact: Optional[float]
    impact_lower: Optional[float]
    impact_upper: Optional[float]

    historical_effectiveness: str

    capability_feasibility: str
    context_feasibility: str
    feasibility_reasons: List[str]

    stage7_rank: Optional[int]
    estimation_status: str

    monitoring_plan: MonitoringPlan
    success_criteria: SuccessCriteria

    provenance: Dict[str, str]

    def __post_init__(self):
        if self.decision_intent not in DECISION_INTENTS:
            raise ValueError(f"invalid decision_intent: {self.decision_intent!r}")
        if self.action_type is not None and self.action_type not in ACTION_TYPES:
            raise ValueError(f"invalid action_type: {self.action_type!r}")


@dataclass
class Recommendation:
    hypothesis_id: str
    driver: List[str]
    mechanism: List[str]
    lever: Optional[str]
    action_type: Optional[str]
    target_scope: Dict[str, str]
    primary_owner: Optional[str]
    secondary_owners: List[str]
    decision_intent: str
    expected_impact: Optional[float]
    impact_lower: Optional[float]
    impact_upper: Optional[float]
    stage7_confidence: str
    historical_effectiveness: str
    capability_feasibility: str
    context_feasibility: str
    monitoring_plan: MonitoringPlan
    success_criteria: SuccessCriteria
    provenance: Dict[str, str]
    parallel_action: bool = False


@dataclass
class Stage9Result:
    episode_id: int
    cluster_id: Optional[str]
    decision_status: str
    primary_recommendation: Optional[Recommendation] = None
    alternatives: List[Recommendation] = field(default_factory=list)
    abstention_reason_codes: List[str] = field(default_factory=list)
    engine_version: str = "stage9-engine-v1"

    def __post_init__(self):
        if self.decision_status not in DECISION_STATUSES:
            raise ValueError(f"invalid decision_status: {self.decision_status!r}")
