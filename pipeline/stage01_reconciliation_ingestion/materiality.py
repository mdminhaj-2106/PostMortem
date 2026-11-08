"""Materiality gate (design doc §5, principle 2) -- never resolve/recompute just because
a number moved, only when the discrepancy could plausibly change a downstream decision.
Shared across Scenarios 1 (value conflicts), 4 (gap fill confidence), and eventually 7
(drift) once those exist.

This is deliberately the simple relative-difference version. The design doc's fuller
"would this flip a downstream decision" version needs Stage 3+ to exist to know what
decisions are actually downstream -- upgrade this once that stage exists.
"""

# Keyed on the REAL reconciled KPI names. The original table keyed on a bare
# "active_customers" that only one caller ever passes, so every call using the actual
# reconciled name (active_customers_purchased_30d / _interacted_30d) silently fell
# through to the 0.05 fallback instead of the intended 0.10 (audit finding F9,
# .claude/plans/remediation-audit-and-fix-plan.md).
DEFAULT_THRESHOLDS = {
    "revenue": 0.05,
    "active_customers": 0.10,                    # calendar-aligned comparison (Scenario 5)
    "active_customers_purchased_30d": 0.10,
    "active_customers_interacted_30d": 0.10,
    "orders_count": 0.05,
    "avg_order_value": 0.05,
    "units_sold": 0.05,
}
_FALLBACK_THRESHOLD = 0.05


def is_material(value_a, value_b, kpi_name, threshold=None):
    if value_a is None or value_b is None:
        raise ValueError("is_material requires two non-null values")
    if threshold is None:
        if kpi_name not in DEFAULT_THRESHOLDS:
            raise ValueError(
                f"no declared materiality threshold for {kpi_name!r} -- add one to "
                f"DEFAULT_THRESHOLDS rather than silently inheriting {_FALLBACK_THRESHOLD} (F9)"
            )
        threshold = DEFAULT_THRESHOLDS[kpi_name]
    denom = max(abs(value_a), abs(value_b), 1e-9)
    return abs(value_a - value_b) / denom > threshold
