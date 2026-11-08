"""Pulls the per-(dimension, slice_value) daily (day, expected, residual) matrix for a
window, reusing Stage 4's own slice_fetcher + Stage 2's compute_residuals via
stage4_bridge -- no new baseline logic. Skips any slice whose eligibility is
LIMITED_HISTORY/INSUFFICIENT_DATA, inheriting Stage 4's rule that such a slice never
gets a fabricated number (same discipline as decomposer.py).
"""

import stage4_bridge


def build(cur, episode_id, kpi_name, window_start, window_end, trailing=30):
    day_range = range(max(0, window_start - trailing), window_end + 1)
    matrix = {}
    for dimension in stage4_bridge.applicable_dimensions(kpi_name):
        for slice_value in stage4_bridge.distinct_slice_values(cur, episode_id, dimension):
            timeline = stage4_bridge.load_slice_timeline(
                cur, episode_id, kpi_name, dimension, slice_value, day_range
            )
            eligibility = stage4_bridge.assess_eligibility(timeline)
            if eligibility in (stage4_bridge.LIMITED_HISTORY, stage4_bridge.INSUFFICIENT_DATA):
                continue
            matrix[(dimension, slice_value)] = stage4_bridge.compute_residuals(timeline)
    return matrix
