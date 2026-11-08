"""Rejects any value outside the fixed enums, plus the hard invariants: no
estimates at all when Stage 7 abstained, no ESTIMATED entry without a matched
Stage 5b mechanism, and trajectory/aggregate/interval reconciliation. Same
dual-validation pattern as every other stage's output_schema.py.
"""

from models import ESTIMATION_STATUSES, MODES, UNCERTAINTY_STATUSES

_REL_TOLERANCE = 1e-6


def validate(result):
    if result.abstained_upstream:
        assert not result.estimates, "Stage 8 must not produce estimates when Stage 7 abstained"
        return

    for est in result.estimates:
        assert est.scenario in MODES, f"free-text scenario: {est.scenario!r}"
        assert est.estimation_status in ESTIMATION_STATUSES, f"free-text estimation_status: {est.estimation_status!r}"

        if est.estimation_status != "ESTIMATED":
            assert "NO_VALIDATED_INTERVENTION_MECHANISM" not in est.estimation_reason_codes or \
                est.estimation_status == "MECHANISM_UNAVAILABLE", \
                "MECHANISM_UNAVAILABLE reason code must carry the matching estimation_status"
            continue

        assert "NO_VALIDATED_INTERVENTION_MECHANISM" not in est.estimation_reason_codes, \
            "an ESTIMATED entry must never carry the reason code that means no mechanism was found"
        assert est.uncertainty_status in UNCERTAINTY_STATUSES, \
            f"invalid uncertainty_status: {est.uncertainty_status!r}"

        usable = [p for p in est.trajectory if p.counterfactual_value is not None]
        if usable and est.estimated_impact is not None:
            reconciled = sum(p.estimated_impact for p in usable)
            tolerance = max(1e-6, abs(est.estimated_impact) * _REL_TOLERANCE + 1e-6)
            assert abs(reconciled - est.estimated_impact) < tolerance, \
                f"trajectory does not reconcile with aggregate: {reconciled!r} vs {est.estimated_impact!r}"

        if est.impact_lower is not None and est.impact_upper is not None and est.estimated_impact is not None:
            assert est.impact_lower <= est.estimated_impact <= est.impact_upper, \
                "interval must contain the point estimate"
