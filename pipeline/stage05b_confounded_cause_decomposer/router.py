"""Design report §7.5: fork to 5b when 5a's top-2 margin is narrow AND corroborating
structural evidence exists. A narrow margin alone is "weak classification", not
"confounded" -- it stays with 5a. Simplified relative to the design doc: changepoint
detection isn't implemented (needs a per-day series 5a doesn't carry), and the declared
dependent-pair check isn't either -- confirming it needs each candidate's own onset day,
which 5a's FingerprintResult doesn't carry in this slice, and "both members clear the
5% probability floor" is true for nearly every narrow-margin case (5a spreads mass
close to evenly whenever it's unsure), so it isn't real corroborating evidence on its
own. The one structural check that IS both cheap and honest from existing stage output
-- >=2 dimensions independently concentrating in Stage 4's own decomposition -- is what's
implemented.
# ponytail: one of the design doc's three evidence checks implemented (multi-dimension
# concentration); changepoint detection and the onset-gated dependent-pair check are
# deferred until 5a's contract carries per-cause onset days, not built speculatively.
"""

MARGIN_THRESHOLD = 0.20
DEVIATION_SIGNAL_THRESHOLD = 0.30


def should_fork(cause_scores, decomposition_result, margin_threshold=MARGIN_THRESHOLD):
    ranked = sorted(cause_scores.items(), key=lambda kv: kv[1], reverse=True)
    if len(ranked) < 2:
        return False, "single candidate, nothing to confound"

    margin = ranked[0][1] - ranked[1][1]
    if margin >= margin_threshold:
        return False, f"clear margin ({margin:.2f}) -- no fork needed"

    dims_with_signal = {
        s.dimension for s in decomposition_result.slices
        if s.observation_status == "OBSERVED" and s.deviation_pct is not None
        and abs(s.deviation_pct) > DEVIATION_SIGNAL_THRESHOLD
    }
    if len(dims_with_signal) >= 2:
        return True, f"narrow margin ({margin:.2f}) + {len(dims_with_signal)} dimensions concentrating independently"

    return False, f"narrow margin ({margin:.2f}) but no corroborating structural evidence -- weak classification, not confounded"
