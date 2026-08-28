"""Main decomposition loop: cluster -> per-KPI -> per-dimension -> per-slice-value ->
SliceResult. Reuses Stage 2's real eligibility/baseline/unusualness functions exactly
as they exist (list-based) via stage2_bridge -- no forked logic.
"""

import dimension_config
import slice_fetcher
import stage2_bridge
from models import DecompositionResult, SliceResult

_NO_FABRICATED_PERCENTILE = (stage2_bridge.LIMITED_HISTORY, stage2_bridge.INSUFFICIENT_DATA)


def decompose_cluster(cur, episode_id, stage3_result):
    slices = [
        _decompose_slice(
            cur, episode_id, kpi_name, dimension, slice_value,
            stage3_result.window_start_day_offset, stage3_result.window_end_day_offset,
        )
        for kpi_name in stage3_result.kpi_names
        for dimension in dimension_config.applicable_dimensions(kpi_name)
        for slice_value in slice_fetcher.distinct_slice_values(cur, episode_id, dimension)
    ]
    return DecompositionResult(episode_id=episode_id, cluster_id=stage3_result.cluster_id, slices=slices)


def _decompose_slice(cur, episode_id, kpi_name, dimension, slice_value, window_start, window_end):
    day_range = range(max(0, window_start - 30), window_end + 1)
    timeline = slice_fetcher.load_slice_timeline(cur, episode_id, kpi_name, dimension, slice_value, day_range)

    eligibility = stage2_bridge.assess_eligibility(timeline)
    residuals = stage2_bridge.compute_residuals(timeline)
    scores_by_day = dict(stage2_bridge.score_unusualness(residuals))

    window_residuals = [
        (d, e, r) for d, e, r in residuals if window_start <= d <= window_end and r is not None
    ]
    if window_residuals:
        expected = sum(e for _, e, _ in window_residuals)
        observed = expected + sum(r for _, _, r in window_residuals)
    else:
        expected = 0.0
        observed = 0.0

    deviation_pct = (observed - expected) / expected if expected != 0 else None
    unusualness_percentile = (
        None if eligibility in _NO_FABRICATED_PERCENTILE else scores_by_day.get(window_end)
    )

    return SliceResult(
        kpi_name=kpi_name, dimension=dimension, slice_value=str(slice_value),
        window_start_day_offset=window_start, window_end_day_offset=window_end,
        expected=expected, observed=observed, deviation_pct=deviation_pct,
        unusualness_percentile=unusualness_percentile, eligibility=eligibility,
    )
