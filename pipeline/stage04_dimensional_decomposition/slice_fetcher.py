"""Pulls one slice's daily timeline from the new sliced Layer 2 views (billing_system
only -- see .claude/plans/stage4-dimensional-decomposition.md's blocking-prerequisite
note). Returns the same (day_offset, observation_or_None) shape Stage 2's own ingest.py
returns for a KPI timeline, so stage2_bridge's re-exported eligibility/baseline/
unusualness functions can run on it directly, no further adapter shim needed.

distinct_slice_values queries customers/products directly to enumerate which slice
values exist for an episode -- the same kind of Layer-1 metadata lookup Stage 1's own
reconcile.py already does for episode start dates, not a KPI-value read (those always
come from the new Layer 2 views, never from raw orders).
"""

from collections import namedtuple

Observation = namedtuple("Observation", ["value", "imputation_flag"])

_DIMENSION_SOURCE = {
    "region": ("customers", "region"),
    "segment": ("customers", "segment"),
    "product": ("products", "category"),
}

# (kpi_name, dimension) -> (view_name, slice_value_column, kpi_value_column)
_VIEW_BY_KPI_DIMENSION = {
    ("revenue", "region"): ("v_billing_daily_revenue_by_region", "region", "revenue"),
    ("revenue", "segment"): ("v_billing_daily_revenue_by_segment", "segment", "revenue"),
    ("revenue", "product"): ("v_billing_daily_revenue_by_product", "category", "revenue"),
    ("active_customers_purchased_30d", "region"): (
        "v_billing_active_customers_by_region", "region", "active_customers",
    ),
    ("active_customers_purchased_30d", "segment"): (
        "v_billing_active_customers_by_segment", "segment", "active_customers",
    ),
    ("orders_count", "region"): ("v_billing_daily_revenue_by_region", "region", "orders_count"),
    ("orders_count", "segment"): ("v_billing_daily_revenue_by_segment", "segment", "orders_count"),
    ("orders_count", "product"): ("v_billing_daily_revenue_by_product", "category", "orders_count"),
    ("units_sold", "region"): ("v_billing_daily_revenue_by_region", "region", "units_sold"),
    ("units_sold", "segment"): ("v_billing_daily_revenue_by_segment", "segment", "units_sold"),
    ("units_sold", "product"): ("v_billing_daily_revenue_by_product", "category", "units_sold"),
}


def distinct_slice_values(cur, episode_id, dimension):
    table, column = _DIMENSION_SOURCE[dimension]
    cur.execute(f"SELECT DISTINCT {column} FROM {table} WHERE episode_id=%s ORDER BY {column}", (episode_id,))
    return [row[0] for row in cur.fetchall()]


def load_slice_timeline(cur, episode_id, kpi_name, dimension, slice_value, day_range):
    """day_range: an iterable of day_offsets. A day the sliced view has no row for
    (a whole-day billing outage) becomes a bare None, matching ingest.py's own
    total-gap convention -- never a fabricated zero."""
    view, slice_column, value_column = _VIEW_BY_KPI_DIMENSION[(kpi_name, dimension)]
    day_range = list(day_range)
    cur.execute(
        f"SELECT day_offset, {value_column} FROM {view} WHERE episode_id=%s AND {slice_column}=%s",
        (episode_id, slice_value),
    )
    by_day = {day_offset: value for day_offset, value in cur.fetchall()}
    return [
        (
            day_offset,
            Observation(value=float(by_day[day_offset]), imputation_flag="untouched")
            if day_offset in by_day else None,
        )
        for day_offset in day_range
    ]
