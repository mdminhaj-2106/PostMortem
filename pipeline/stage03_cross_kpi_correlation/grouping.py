"""Grouping (design doc §2): cluster two flagged KPIs only if the DAG says they're
adjacent AND they co-move in the correct direction within the expected lag window
for this specific incident. Failure defaults to standalone results -- never force
a cluster (§2's "don't force it," reusing Stage 1 Scenario 6's under-merge-is-safer
principle).
"""


def find_flagged_windows(stage2_results):
    """stage2_results: list[StageTwoResult] for one KPI, ordered by day_offset.
    Returns [(start_day, end_day), ...] contiguous runs where classification_state
    is SIGNIFICANT or STRUCTURAL."""
    windows = []
    start = None
    prev_day = None
    for r in stage2_results:
        flagged = r.classification_state in ("SIGNIFICANT", "STRUCTURAL")
        if flagged and start is None:
            start = r.day_offset
        if not flagged and start is not None:
            windows.append((start, prev_day))
            start = None
        prev_day = r.day_offset
    if start is not None:
        windows.append((start, prev_day))
    return windows


def _sign(value):
    if value is None or value == 0:
        return None
    return 1 if value > 0 else -1


def _mean_residual(residuals_by_day, start, end):
    values = [r for d, r in residuals_by_day.items() if start <= d <= end and r is not None]
    return sum(values) / len(values) if values else None


def windows_link(a_window, a_residuals, b_window, b_residuals, dag_entry):
    """Does this ONE pair of windows satisfy the edge -- adjacent in the expected lag AND
    co-moving in the expected direction? Returns (linked, adjacent) so a caller can tell
    "never adjacent" from "adjacent but the direction refuted it", which are different
    findings: the first means nothing was near it, the second means something was near it
    and the evidence said no.

    The core predicate for walking a whole DAG; attempt_cluster is the single-edge
    convenience wrapper over it.
    """
    lag_min, lag_max = dag_entry["expected_lag_days"]
    if not (lag_min <= b_window[0] - a_window[0] <= lag_max):
        return False, False

    sign_a = _sign(_mean_residual(dict(a_residuals), a_window[0], a_window[1]))
    sign_b = _sign(_mean_residual(dict(b_residuals), b_window[0], b_window[1]))
    if sign_a is None or sign_b is None:
        return False, True  # adjacent, but one side has no usable movement to compare

    if dag_entry["expected_direction"] == "SAME_SIGN":
        return sign_a == sign_b, True
    return sign_a != sign_b, True


def attempt_cluster(kpi_a_windows, kpi_a_residuals, kpi_b_windows, kpi_b_residuals, dag_entry):
    """kpi_a is the DAG-key KPI, kpi_b is dag_entry['target']. Returns
    ((window_start, window_end), None) for the first kpi_a window that clusters
    with a kpi_b window in the correct direction within the expected lag, else
    (None, reason) where reason distinguishes "no adjacent flagged KPI at all"
    from "adjacent but direction/co-movement didn't confirm"."""
    residuals_a = dict(kpi_a_residuals)
    residuals_b = dict(kpi_b_residuals)
    lag_min, lag_max = dag_entry["expected_lag_days"]
    any_adjacent = False

    for a_start, a_end in kpi_a_windows:
        matched_b = next(
            (b for b in kpi_b_windows if lag_min <= b[0] - a_start <= lag_max), None
        )
        if matched_b is None:
            continue
        any_adjacent = True
        b_start, b_end = matched_b
        sign_a = _sign(_mean_residual(residuals_a, a_start, a_end))
        sign_b = _sign(_mean_residual(residuals_b, b_start, b_end))
        if sign_a is None or sign_b is None:
            continue
        direction_ok = (sign_a == sign_b) if dag_entry["expected_direction"] == "SAME_SIGN" else (sign_a != sign_b)
        if direction_ok:
            return (min(a_start, b_start), max(a_end, b_end)), None

    if not kpi_a_windows or not kpi_b_windows or not any_adjacent:
        return None, "SEPARATE_NO_ADJACENT_KPI"
    return None, "SEPARATE_NO_CORRELATION"
