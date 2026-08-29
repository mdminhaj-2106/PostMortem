"""Layer 5 -- KPI Relationship Graph (design doc §11). Declared, not inferred --
same "declared, don't infer what can be declared" principle as Stage 1's Semantic
Contract. Only one edge exists: Stage 1 currently reconciles exactly 2 KPIs
(revenue, active_customers_purchased_30d), so this is honestly thin rather than
the richer Traffic->Conversion->Orders->Revenue graph the design doc illustrates
(plan Risk #2) -- extend once Stage 1 reconciles more KPIs.
"""

RELATIONSHIPS = {
    "active_customers_purchased_30d": [("revenue", "UPSTREAM_DRIVER")],
}


def related_kpis(kpi_name):
    """Both directions, from one declaration. RELATIONSHIPS declares only the
    forward (driver -> driven) edge, so a lookup on the *driven* KPI used to return
    [] -- meaning revenue could never see active_customers as related, and
    KNOWN_RELATIONSHIP evidence stayed at 0 occurrences live even after Stage 3
    correctly threaded the other KPI's candidate days through (audit finding F3,
    .claude/plans/remediation-audit-and-fix-plan.md). Deriving the reverse edge
    here rather than writing each edge twice keeps one source of truth: F14's
    2 -> 7 KPI expansion adds ~6 edges, and hand-maintaining both directions is
    the same silent-drift bug class as F9's out-of-sync threshold keys."""
    forward = list(RELATIONSHIPS.get(kpi_name, []))
    reverse = [
        (driver, "DOWNSTREAM_OF")
        for driver, edges in RELATIONSHIPS.items()
        for target, _relationship in edges
        if target == kpi_name
    ]
    return forward + reverse
