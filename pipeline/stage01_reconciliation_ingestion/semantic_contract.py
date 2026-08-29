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
                "bias_factor": None,
            },
            "active_customers": {
                "grain": "daily (UTC day)",
                "definition": "purchased in trailing 30 days",
                "bias_direction": "none -- exact",
                "bias_factor": None,
            },
            "orders_count": {
                "grain": "daily (UTC day)",
                "definition": "COUNT(*) of atomic orders",
                "bias_direction": "none -- exact",
                "bias_factor": None,
            },
            "avg_order_value": {
                "grain": "daily (UTC day)",
                "definition": "AVG(quantity * unit_price) per order",
                "bias_direction": "none -- exact",
                "bias_factor": None,
            },
            "units_sold": {
                "grain": "daily (UTC day)",
                "definition": "SUM(quantity) across atomic orders -- moves with order MIX, "
                               "not just order count, so it can diverge from orders_count",
                "bias_direction": "none -- exact",
                "bias_factor": None,
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
                # Deliberately None, NOT "unmeasured": a different definition is not a bias,
                # and correcting for it would collapse a real signal into a fake agreement.
                "bias_factor": None,
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
                # The prose above is for humans; THIS is what apply_bias_correction reads.
                "bias_factor": {"before_midpoint": 0.87, "from_midpoint": 0.80},
            },
            "active_customers": {
                "grain": "30-day billing-cycle month (day-15 start, not calendar months)",
                "definition": "purchased in trailing 30 days -- same definition as billing's "
                               "active_customers, only the calendar grain differs (Scenario 5)",
                "bias_direction": "none -- same definition as billing, calendar-misaligned only",
                "bias_factor": None,
            },
        },
    },
}

def metric_contract(source_name, metric_name):
    """The declared contract entry for one (source, metric). Raises rather than
    returning a default -- an undeclared source/metric pair means the registry and the
    contract have drifted apart, which is exactly the silent-fallback bug class F9 cost
    this project once."""
    try:
        return SEMANTIC_CONTRACT[source_name]["metrics"][metric_name]
    except KeyError:
        raise KeyError(
            f"no semantic contract entry for {source_name!r}.{metric_name!r} -- declare it "
            f"in SEMANTIC_CONTRACT rather than letting the reconciler assume no bias"
        ) from None


def apply_bias_correction(source_name, metric_name, value, day_offset=None, n_days=None):
    """Undo a source's declared bias to make it directly comparable to the
    ground-truth-equivalent source (design doc Scenario 1, step 3).

    Reads `bias_factor` straight off the contract (audit finding F8). It used to be
    declared twice -- as prose in SEMANTIC_CONTRACT and again as module constants in an
    `if source_name == ... and metric_name == ...` branch here -- two sources of truth
    kept in sync by hand, with the brief's "semantic contract" checklist item satisfied
    by a dict nothing actually read.

    A `bias_factor` of None means no declared bias and passes through unchanged; a float
    is a constant factor; a dict is midpoint-split, mirroring views.sql's
    "CASE WHEN o.day_offset < e.n_days / 2 THEN 0.87 ELSE 0.80 END" including its
    integer division of n_days.
    """
    factor = metric_contract(source_name, metric_name).get("bias_factor")
    if factor is None:
        return value

    if isinstance(factor, dict):
        if day_offset is None or n_days is None:
            raise ValueError(
                f"day_offset and n_days are required to bias-correct "
                f"{source_name}.{metric_name} (its declared bias is midpoint-dependent)"
            )
        factor = factor["before_midpoint"] if day_offset < n_days // 2 else factor["from_midpoint"]

    return value / factor
