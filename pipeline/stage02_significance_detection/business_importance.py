"""Layer 4 -- Business Importance (design doc §9). Uses only the strongest
available *declared* evidence for this slice: known business criticality (§9.2)
and known KPI-relationship position (§9.3). No direct-outcome-formula conversion
(§9.1) or historical/correlation-based evidence (§9.4) -- see plan Scope/Out.
"""

import relationship_graph

CRITICALITY = {
    "revenue": "CRITICAL",
    "active_customers_purchased_30d": "HIGH",
}


def assess_importance(kpi_name, other_candidates_today):
    """other_candidates_today: iterable of kpi_names that are also candidates on
    the same day as kpi_name. Returns (level, evidence_list)."""
    evidence = []
    level = CRITICALITY.get(kpi_name, "NONE")
    if level != "NONE":
        evidence.append({"type": "KNOWN_BUSINESS_CRITICALITY", "target": kpi_name, "level": level})

    other_set = set(other_candidates_today) - {kpi_name}
    for related_kpi, relationship in relationship_graph.related_kpis(kpi_name):
        if related_kpi in other_set:
            evidence.append({"type": "KNOWN_RELATIONSHIP", "target": related_kpi, "relationship": relationship})
            if level == "NONE":
                level = "MEDIUM"

    return level, evidence
