"""Combines signatures.py's three signals into a ranked {event_type: score} dict (sums
to 1, never a single unqualified guess) + a confidence tier. No trained artifact --
see the plan's Scope decision for why a threshold heuristic was chosen deliberately.
"""

from models import EVENT_TYPES

_ONSET_TO_CAUSE = {"step": "marketing_cut", "ramp": "product_outage"}
_INVENTORY_SHORTAGE_MASS = 0.7
_RESIDUAL_INVENTORY_MASS = 0.05  # kept small, not zero, when the near-deterministic signal didn't fire
_STRONG_LEAN_MASS = 0.6  # signals 2+3 agree
_WEAK_LEAN_MASS = 0.5  # only one of signals 2/3 available


def _even_split(scores, causes, total_mass):
    share = total_mass / len(causes)
    for c in causes:
        scores[c] = share


def classify(product_signal, kpi_shift_signal, onset_signal):
    """product_signal: (slice_value_or_None, score) from signatures.product_concentration.
    kpi_shift_signal: signatures.dominant_kpi_shift's return. onset_signal:
    signatures.onset_lean's return.

    Returns (cause_scores, confidence, top_cause, signals_used)."""
    product_slice, _product_score = product_signal
    scores = {c: 0.0 for c in EVENT_TYPES}
    signals_used = []

    if product_slice is not None:
        signals_used.append("product_concentration")
        scores["inventory_shortage"] = _INVENTORY_SHORTAGE_MASS
        _even_split(
            scores,
            [c for c in EVENT_TYPES if c != "inventory_shortage"],
            1.0 - _INVENTORY_SHORTAGE_MASS,
        )
        return scores, "HIGH", "inventory_shortage", signals_used

    scores["inventory_shortage"] = _RESIDUAL_INVENTORY_MASS
    remaining = 1.0 - _RESIDUAL_INVENTORY_MASS
    remaining_causes = ["marketing_cut", "competitor_launch", "product_outage"]

    if kpi_shift_signal is not None:
        signals_used.append("dominant_kpi_shift")
    if onset_signal is not None:
        signals_used.append("onset_lean")

    onset_cause = _ONSET_TO_CAUSE.get(onset_signal)

    if kpi_shift_signal == "customers_first":
        lean, agreed = "competitor_launch", False
    elif kpi_shift_signal == "orders_first" and onset_cause is not None:
        lean, agreed = onset_cause, True
    elif kpi_shift_signal == "orders_first":
        lean, agreed = None, False  # ambiguous between marketing_cut/product_outage, no tie-breaker
    else:
        lean, agreed = None, False

    if lean is not None:
        lean_mass = _STRONG_LEAN_MASS if agreed else _WEAK_LEAN_MASS
        scores[lean] = remaining * lean_mass
        _even_split(scores, [c for c in remaining_causes if c != lean], remaining * (1 - lean_mass))
        confidence = "MEDIUM" if agreed else "LOW"
        top_cause = lean
    else:
        _even_split(scores, remaining_causes, remaining)
        confidence = "LOW"
        top_cause = max(scores, key=lambda c: (scores[c], c))

    return scores, confidence, top_cause, signals_used
