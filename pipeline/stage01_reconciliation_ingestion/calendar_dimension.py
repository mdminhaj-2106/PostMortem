"""Calendar Dimension -- buckets an atomic day_offset into any declared calendar
convention (design doc §3.2, Scenario 5). Layer 1 is atomic-grain and owned by the team,
so re-bucketing on demand from raw truth is exact -- this deliberately avoids
materializing a separate pre-aggregated copy of a KPI per convention.

Bucket boundaries here must match what Layer 2's SQL views already compute
(views.sql), so a value can be aligned across grains for comparison without a fourth
materialized grain. See test_reconcile.py's live check against
v_crm_weekly_active_customers and v_marketing_monthly_active_customers.
"""

from datetime import timedelta

CONVENTIONS = ("daily", "iso_week", "billing_cycle_month")

# Matches v_marketing_monthly_active_customers' "WHERE day_offset >= 15" -- billing
# cycles aren't defined before day 15.
_BILLING_CYCLE_START_DAY = 15
_BILLING_CYCLE_LENGTH = 30


def bucket_day(day_offset, convention, start_date):
    """Return the bucket id day_offset falls into under `convention`, or None if the
    convention isn't yet defined that early in the episode (billing_cycle_month before
    day 15)."""
    if convention == "daily":
        return day_offset
    if convention == "iso_week":
        actual_date = start_date + timedelta(days=day_offset)
        monday = actual_date - timedelta(days=actual_date.weekday())
        return (monday - start_date).days
    if convention == "billing_cycle_month":
        if day_offset < _BILLING_CYCLE_START_DAY:
            return None
        return (day_offset - _BILLING_CYCLE_START_DAY) // _BILLING_CYCLE_LENGTH
    raise ValueError(f"unknown calendar convention: {convention!r}")


def billing_cycle_end_day(cycle_index, n_days):
    """The one day within a billing cycle where a daily-grain trailing-30-day value is
    directly comparable to v_marketing_monthly_active_customers' snapshot for that cycle
    -- the view snapshots at the cycle's last day (cycle_end_day), not every day in the
    cycle, so comparing against any other day compares two different 30-day windows."""
    if cycle_index is None:
        return None
    return min(
        _BILLING_CYCLE_START_DAY + (cycle_index + 1) * _BILLING_CYCLE_LENGTH - 1,
        n_days - 1,
    )
