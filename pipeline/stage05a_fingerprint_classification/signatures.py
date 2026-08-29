"""The three real signal functions (.claude/plans/stage5a-fingerprint-classification.md's
ceiling analysis). Pure functions -- no DB access, no import of onset_fetcher -- callers
(classifier.py/stage5a.py) do the fetching and pass data in.

Deliberately NOT implemented: geo_spread_entropy/segment_spread_entropy. Traced through
generate.py's real structural equations, no event type ever touches `region`, and
`affected_segment` is an orthogonal modifier independent of cause (any event type, 40%
chance) -- neither carries real cause-discriminating signal in this dataset, despite
being in the original Round 1 architecture report and the (uncorrected) design doc.
"""

# Step 1: needs a real number from a live eval run (eval_against_ground_truth.py), not a
# guessed one -- see the plan's Risk #1. Left as the plan's stated starting value until
# that calibration run.
PRODUCT_CONCENTRATION_THRESHOLD = 0.6

# Signal 2's "flat" cutoff: a KPI's window relative deviation below this is treated as
# "didn't move," not as a directional lean.
KPI_SHIFT_FLAT_THRESHOLD = 0.02

# Signal 3's day1/day7 |residual| ratio cutoffs (design doc's onset_shape_ratio, §3.2,
# against the real series instead of a pandas one). Onset noise is 55/45 by construction
# (generate.py's _sample_onset) -- these are leans, not rules.
ONSET_STEP_RATIO = 0.7
ONSET_RAMP_RATIO = 0.4

# A LIMITED_HISTORY/INSUFFICIENT_DATA slice's deviation_pct is computed from whatever
# partial residual data exists in the window (decomposer.py never nulls it, only
# unusualness_percentile) -- real, but not a trustworthy shape to fingerprint against.
# Stage 4's own eligibility gate already draws this exact line (its
# _NO_FABRICATED_PERCENTILE); product_concentration must draw it too, or it fabricates
# a HIGH-confidence cause from a slice Stage 4 itself refused to score. These slices are
# Stage 5c's job, not 5a's -- see .claude/plans/stage5c-cold-start-analogy-handler.md.
_THIN_ELIGIBILITIES = ("LIMITED_HISTORY", "INSUFFICIENT_DATA")


def product_concentration(decomposition_result):
    """(slice_value_or_None, score). score is the winning slice's share of total
    |deviation_pct| among that KPI's OBSERVED, non-thin product slices, when it clears
    the margin over the runner-up. Real, near-deterministic signal: only
    inventory_shortage ever touches `product` (generate.py cuts
    product_weights[affected_product_idx])."""
    by_kpi = {}
    for s in decomposition_result.slices:
        if (
            s.dimension != "product" or s.observation_status != "OBSERVED"
            or s.deviation_pct is None or s.eligibility in _THIN_ELIGIBILITIES
        ):
            continue
        by_kpi.setdefault(s.kpi_name, []).append(s)

    best = (None, 0.0)
    for slices in by_kpi.values():
        magnitudes = [(s.slice_value, abs(s.deviation_pct)) for s in slices]
        total = sum(m for _, m in magnitudes)
        if total <= 0 or len(magnitudes) < 2:
            continue
        magnitudes.sort(key=lambda pair: pair[1], reverse=True)
        top_value, top_mag = magnitudes[0]
        runner_up_mag = magnitudes[1][1]
        top_share = top_mag / total
        runner_up_share = runner_up_mag / total
        if top_share > PRODUCT_CONCENTRATION_THRESHOLD and top_share > runner_up_share and top_share > best[1]:
            best = (top_value, top_share)

    return best


def _relative_deviation(residual_series, window_start, window_end):
    """sum(residual)/sum(expected) over the window, same shape as Stage 4's
    SliceResult.deviation_pct -- None if nothing usable falls in the window."""
    rows = [
        (e, r) for d, e, r in residual_series
        if window_start <= d <= window_end and e is not None and r is not None
    ]
    if not rows:
        return None
    total_expected = sum(e for e, _ in rows)
    if total_expected == 0:
        return None
    return sum(r for _, r in rows) / total_expected


def dominant_kpi_shift(customers_series, orders_series, revenue_series, window_start, window_end):
    """"customers_first" | "orders_first" | None. Only `competitor_launch` drives churn
    (shrinks the active-customer pool) before/more than it drives orders/revenue; the
    other real event types hit orders/revenue directly with no customer-pool mechanism."""
    customers_rel = _relative_deviation(customers_series, window_start, window_end) if customers_series else None
    orders_rel = _relative_deviation(orders_series, window_start, window_end) if orders_series else None
    revenue_rel = _relative_deviation(revenue_series, window_start, window_end) if revenue_series else None

    orders_side = max((abs(v) for v in (orders_rel, revenue_rel) if v is not None), default=None)

    if customers_rel is not None and abs(customers_rel) > KPI_SHIFT_FLAT_THRESHOLD and (
        orders_side is None or abs(customers_rel) > orders_side
    ):
        return "customers_first"
    if orders_side is not None and orders_side > KPI_SHIFT_FLAT_THRESHOLD and (
        customers_rel is None or abs(customers_rel) <= KPI_SHIFT_FLAT_THRESHOLD
    ):
        return "orders_first"
    return None


def onset_lean(residual_series, window_start):
    """"step" | "ramp" | None from a day-1-vs-day-7 |residual| ratio. Only a tie-breaker
    between marketing_cut/product_outage (their TYPICAL_ONSET in generate.py) -- does not
    discriminate competitor_launch/inventory_shortage, so callers must not use it for those."""
    by_day = {d: r for d, _e, r in residual_series}
    day1, day7 = by_day.get(window_start + 1), by_day.get(window_start + 7)
    if day1 is None or day7 is None or day7 == 0:
        return None
    ratio = abs(day1) / abs(day7)
    if ratio > ONSET_STEP_RATIO:
        return "step"
    if ratio < ONSET_RAMP_RATIO:
        return "ramp"
    return None
