"""KPI Semantic Contract -- per-source metadata declared by hand at design time, not
inferred at runtime (design doc §3.1). A plain dict is the honest MVP of "authored, not
inferred" for 3 known sources; upgrade to a real table if/when a source needs
runtime-editable metadata.

Bias directions below are asserted to match pipeline/simulator/layer2_observed_sources/
views.sql, not guessed -- see test_reconcile.py's live check.
"""

SEMANTIC_CONTRACT = {
    "billing_system": {
        "cadence_days": 1,
        "calendar_convention": "daily",
        "metrics": {
            "revenue": {
                "grain": "daily (UTC day)",
                "definition": "exact revenue (SUM(quantity * unit_price)) from atomic orders",
                "bias_direction": "none -- ground-truth-equivalent, exact",
            },
            "active_customers": {
                "grain": "daily (UTC day)",
                "definition": "purchased in trailing 30 days",
                "bias_direction": "none -- exact",
            },
        },
    },
    "crm_system": {
        "cadence_days": 7,
        "calendar_convention": "iso_week",
        "metrics": {
            "active_customers": {
                "grain": "ISO week (Monday-start)",
                "definition": "order OR support ticket in trailing 30 days -- broader than "
                               "billing's purchase-only definition, not a biased version of it",
                "bias_direction": "none -- genuinely different definition (Scenario 2), kept "
                                   "as a separate feature, never collapsed into billing's number",
            },
        },
    },
    "marketing_system": {
        "cadence_days": 1,
        "calendar_convention": "daily",
        "metrics": {
            "attributed_revenue": {
                "grain": "daily (UTC day)",
                "definition": "revenue attributed to the marketing channel, a biased fraction "
                               "of true revenue",
                "bias_direction": "undercounts by ~13% (0.87x) before the episode midpoint, "
                                   "silently tightens to ~20% undercount (0.80x) from the "
                                   "midpoint onward -- matches views.sql exactly",
            },
            "active_customers": {
                "grain": "30-day billing-cycle month (day-15 start, not calendar months)",
                "definition": "purchased in trailing 30 days -- same definition as billing's "
                               "active_customers, only the calendar grain differs (Scenario 5)",
                "bias_direction": "none -- same definition as billing, calendar-misaligned only",
            },
        },
    },
}

# Bias correction factors for marketing_system's attributed_revenue, keyed by whether the
# day falls before or at/after the episode midpoint -- mirrors views.sql's
# "CASE WHEN o.day_offset < e.n_days / 2 THEN 0.87 ELSE 0.80 END" exactly, including
# integer division of n_days.
_MARKETING_REVENUE_BIAS_BEFORE_MIDPOINT = 0.87
_MARKETING_REVENUE_BIAS_AFTER_MIDPOINT = 0.80


def apply_bias_correction(source_name, metric_name, value, day_offset=None, n_days=None):
    """Undo a source's declared bias to make it directly comparable to the
    ground-truth-equivalent source (design doc Scenario 1, step 3). Sources/metrics with
    no declared bias pass through unchanged."""
    if source_name == "marketing_system" and metric_name == "attributed_revenue":
        if day_offset is None or n_days is None:
            raise ValueError("day_offset and n_days are required to bias-correct attributed_revenue")
        factor = (
            _MARKETING_REVENUE_BIAS_BEFORE_MIDPOINT
            if day_offset < n_days // 2
            else _MARKETING_REVENUE_BIAS_AFTER_MIDPOINT
        )
        return value / factor
    return value
