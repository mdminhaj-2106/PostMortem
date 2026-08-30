"""Step: uncertainty interval (explicitly LIMITED, not calibrated -- design doc
§38's own escape hatch) + data_confidence via Stage 2's real eligibility.py. See
.claude/plans/stage8-counterfactual-impact-engine.md finding #7.
"""

import statistics

from canonical_bridge import assess_eligibility


def data_confidence(timeline):
    return assess_eligibility(timeline)


def residual_stdev(expected_by_day, observed_by_day, pre_window_days):
    """Stdev of (observed - expected) over the trailing pre-window days -- the one
    real, computable noise signal available without a calibrated model. None when
    fewer than 2 usable days exist (stdev is undefined)."""
    values = [
        observed_by_day[d] - expected_by_day[d]
        for d in pre_window_days
        if observed_by_day.get(d) is not None and expected_by_day.get(d) is not None
    ]
    if len(values) < 2:
        return None
    return statistics.stdev(values)


def impact_interval(estimated_impact, stdev, n_days, share):
    """A transparent, explicitly-uncalibrated band -- design doc §38: "the output
    must not pretend the interval is statistically calibrated." Width scales with
    the pre-window residual noise, the number of days summed, and the fitted
    share (a smaller share means the intervention is a smaller, less certain
    slice of the movement, so the same absolute noise represents more relative
    uncertainty around it)."""
    if estimated_impact is None or stdev is None:
        return None, None
    width = stdev * (n_days ** 0.5) * max(share, 0.1)
    return estimated_impact - width, estimated_impact + width
