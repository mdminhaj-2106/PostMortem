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
    return RELATIONSHIPS.get(kpi_name, [])
