"""Layer 2 -- Expected Behavior (design doc §6). One baseline method for this
slice: a rolling median over trailing non-null observations (§6.2's formula,
used as the default for every history length, not just "limited" ones -- the
design doc itself says a simple robust baseline "should be the initial default,"
and no KPI here has enough episode-length data to justify seasonal decomposition).
"""

import statistics

DEFAULT_WINDOW = 14
MIN_WINDOW_FOR_ESTIMATE = 5


def compute_residuals(timeline, window=DEFAULT_WINDOW, min_window_for_estimate=MIN_WINDOW_FOR_ESTIMATE):
    """timeline: [(day_offset, ReconciledValue_or_None), ...], ordered by day_offset.
    Returns [(day_offset, expected, residual), ...] -- only for days with at least
    min_window_for_estimate usable observations in the trailing window."""
    residuals = []
    history = []  # trailing usable values, most recent last
    for day_offset, rv in timeline:
        value = rv.value if rv is not None else None
        if len(history) >= min_window_for_estimate:
            expected = statistics.median(history[-window:])
            residuals.append((day_offset, expected, value - expected if value is not None else None))
        if value is not None:
            history.append(value)
    return residuals
