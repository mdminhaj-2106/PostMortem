"""Structured post-action success condition, built from Stage 8's own
estimation_status -- DERIVABLE iff a real counterfactual trajectory exists to
compare against (design doc §46, plan step 8). No fake numerical target is
ever invented.
"""

from models import SuccessCriteria


def build_success_criteria(estimation_status):
    if estimation_status == "ESTIMATED":
        return SuccessCriteria(status="DERIVABLE", basis="COUNTERFACTUAL_TRAJECTORY")
    return SuccessCriteria(status="NOT_DERIVABLE", basis=None)
