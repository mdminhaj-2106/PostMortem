"""The declared DAG (design doc §2/§3): hand-authored, not inferred, same discipline
as Stage 2's own relationship_graph.py -- this extends that one edge with the
lag/direction annotations Stage 3's grouping test needs. Only one edge exists
because Stage 1 currently reconciles exactly 2 KPIs (plan Risk #1); extend once
Stage 1 reconciles more.
"""

# (expected_lag_days_min, expected_lag_days_max): a related KPI's flagged window should
# start within this many days of the KPI it's keyed under.
#
# Two kinds of edge, and the lag reflects which:
#   - ARITHMETIC composition (revenue = orders_count x avg_order_value; units_sold sums
#     the same orders) -- these resolve on the SAME day by construction, so (0, 1) with
#     one day of slack for window-edge fuzz. A wider window here would let genuinely
#     unrelated movements masquerade as composition.
#   - BEHAVIOURAL drive (customers -> orders) -- a real-world response with some lag,
#     so (0, 3), the tolerance the original edge was validated at.
#
# Mirrors stage02/relationship_graph.py's RELATIONSHIPS; that module declares WHAT
# relates to what for Layer 4, this one adds the lag/direction Stage 3's co-movement
# test needs. test_stage3 asserts the two stay consistent.
DAG = {
    "active_customers_purchased_30d": [
        {"target": "orders_count", "relationship": "UPSTREAM_DRIVER",
         "expected_lag_days": (0, 3), "expected_direction": "SAME_SIGN"},
        {"target": "revenue", "relationship": "UPSTREAM_DRIVER",
         "expected_lag_days": (0, 3), "expected_direction": "SAME_SIGN"},
    ],
    "orders_count": [
        {"target": "revenue", "relationship": "UPSTREAM_DRIVER",
         "expected_lag_days": (0, 1), "expected_direction": "SAME_SIGN"},
        {"target": "units_sold", "relationship": "UPSTREAM_DRIVER",
         "expected_lag_days": (0, 1), "expected_direction": "SAME_SIGN"},
    ],
    "avg_order_value": [
        {"target": "revenue", "relationship": "UPSTREAM_DRIVER",
         "expected_lag_days": (0, 1), "expected_direction": "SAME_SIGN"},
    ],
}


def related_kpis_with_lag(kpi_name):
    return DAG.get(kpi_name, [])


def edges():
    """Every (source, entry) pair, for callers that walk the whole graph rather than
    one hardcoded edge."""
    return [(source, entry) for source, entries in DAG.items() for entry in entries]


def kpis():
    """Every KPI mentioned anywhere in the DAG, as sources or targets."""
    names = set(DAG)
    for _source, entry in edges():
        names.add(entry["target"])
    return sorted(names)
