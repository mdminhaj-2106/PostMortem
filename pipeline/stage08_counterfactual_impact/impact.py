"""Step: aggregate impact + pct + KPI direction annotation. See
.claude/plans/stage8-counterfactual-impact-engine.md's impact_direction finding --
all 5 real KPIs are higher-is-better in this dataset (checked against
stage01_reconciliation_ingestion/semantic_contract.py: no declared per-KPI cost/
revenue orientation exists there, only source bias_direction, a different
concept), so `estimated_impact = counterfactual - observed` needs no sign flip
and this module declares the one real direction value rather than inventing a
generic registry nothing else in this codebase populates.
"""

KPI_DIRECTION = "HIGHER_IS_BETTER"


def aggregate(trajectory_points):
    """(observed_aggregate, counterfactual_aggregate, estimated_impact,
    impact_pct_of_observed) -- summed only over points with a real
    counterfactual_value, never fabricated for a day with insufficient trailing
    history. All four are None when no point in the window is usable."""
    usable = [p for p in trajectory_points if p["counterfactual_value"] is not None]
    if not usable:
        return None, None, None, None
    observed_aggregate = sum(p["observed_value"] for p in usable)
    counterfactual_aggregate = sum(p["counterfactual_value"] for p in usable)
    estimated_impact = counterfactual_aggregate - observed_aggregate
    impact_pct = (estimated_impact / observed_aggregate * 100) if observed_aggregate else None
    return observed_aggregate, counterfactual_aggregate, estimated_impact, impact_pct
