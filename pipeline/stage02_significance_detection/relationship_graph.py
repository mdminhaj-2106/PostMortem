"""Layer 5 -- KPI Relationship Graph (design doc §11). Declared, not inferred --
same "declared, don't infer what can be declared" principle as Stage 1's Semantic
Contract. Only one edge exists: Stage 1 currently reconciles exactly 2 KPIs
(revenue, active_customers_purchased_30d), so this is honestly thin rather than
the richer Traffic->Conversion->Orders->Revenue graph the design doc illustrates
(plan Risk #2) -- extend once Stage 1 reconciles more KPIs.
"""

# F14 turned this from one edge into a real DAG. Every edge below is a structural fact
# about how this dataset is generated, not an inferred correlation:
#   revenue = orders_count x avg_order_value   (an identity, from atomic orders)
#   more active customers -> more orders        (orders come from purchasing customers)
#   more orders -> more units                   (units_sold = SUM(quantity) over orders)
#
#     active_customers ──> orders_count ──> revenue
#                     └──────────────┐      ▲
#                                    └──> units_sold
#     avg_order_value ─────────────────────┘
#
# Direction/lag annotations for Stage 3's co-movement test live in stage03/dag.py; this
# module declares only WHAT relates to what, which is all Layer 4 needs.
RELATIONSHIPS = {
    "active_customers_purchased_30d": [
        ("orders_count", "UPSTREAM_DRIVER"),
        ("revenue", "UPSTREAM_DRIVER"),
    ],
    "orders_count": [
        ("revenue", "UPSTREAM_DRIVER"),
        ("units_sold", "UPSTREAM_DRIVER"),
    ],
    "avg_order_value": [
        ("revenue", "UPSTREAM_DRIVER"),
    ],
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
