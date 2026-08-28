"""Materiality gate (design doc §5, principle 2) -- never resolve/recompute just because
a number moved, only when the discrepancy could plausibly change a downstream decision.
Shared across Scenarios 1 (value conflicts), 4 (gap fill confidence), and eventually 7
(drift) once those exist.

This is deliberately the simple relative-difference version. The design doc's fuller
"would this flip a downstream decision" version needs Stage 3+ to exist to know what
decisions are actually downstream -- upgrade this once that stage exists.
"""

DEFAULT_THRESHOLDS = {
    "revenue": 0.05,
    "active_customers": 0.10,
}
_FALLBACK_THRESHOLD = 0.05


def is_material(value_a, value_b, kpi_name, threshold=None):
    if value_a is None or value_b is None:
        raise ValueError("is_material requires two non-null values")
    if threshold is None:
        threshold = DEFAULT_THRESHOLDS.get(kpi_name, _FALLBACK_THRESHOLD)
    denom = max(abs(value_a), abs(value_b), 1e-9)
    return abs(value_a - value_b) / denom > threshold
