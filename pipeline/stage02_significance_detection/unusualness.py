"""Layer 3 -- Self-Normalized Unusualness (design doc §7). Every KPI is normalized
against its OWN historical residual distribution before being compared with anything
else. The percentile is causal: a day's score only ever looks at residuals strictly
before it, never at the full-episode distribution -- otherwise an early day's score
would depend on data that wasn't knowable yet at the time.
"""

BASIS = "HISTORICAL_RESIDUAL_EXTREMENESS"


def score_unusualness(residuals):
    """residuals: [(day_offset, expected, residual_or_None), ...], ordered by
    day_offset. Returns [(day_offset, score_or_None), ...] -- None where there's
    no prior history yet to compare against."""
    scores = []
    prior_abs_residuals = []
    for day_offset, _expected, residual in residuals:
        if residual is None:
            scores.append((day_offset, None))
            continue
        abs_r = abs(residual)
        if not prior_abs_residuals:
            scores.append((day_offset, None))
        else:
            n_at_or_below = sum(1 for r in prior_abs_residuals if r <= abs_r)
            scores.append((day_offset, n_at_or_below / len(prior_abs_residuals)))
        prior_abs_residuals.append(abs_r)
    return scores
