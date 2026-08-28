"""The declared DAG (design doc §2/§3): hand-authored, not inferred, same discipline
as Stage 2's own relationship_graph.py -- this extends that one edge with the
lag/direction annotations Stage 3's grouping test needs. Only one edge exists
because Stage 1 currently reconciles exactly 2 KPIs (plan Risk #1); extend once
Stage 1 reconciles more.
"""

# (expected_lag_days_min, expected_lag_days_max): a related KPI's flagged window
# should start within this many days of the KPI it's keyed under. Same-window here
# because active-customer purchases compose directly into the same window's revenue.
DAG = {
    "active_customers_purchased_30d": [
        {"target": "revenue", "relationship": "UPSTREAM_DRIVER",
         "expected_lag_days": (0, 3), "expected_direction": "SAME_SIGN"},
    ],
}


def related_kpis_with_lag(kpi_name):
    return DAG.get(kpi_name, [])
