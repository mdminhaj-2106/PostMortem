"""Design report §7.1: one shared shape-vector builder, used by BOTH offline basis
learning and the runtime path -- no train/serve skew. The vector is a pure function of
(BASIS_WINDOW_DAYS, TOP_K_SLICES) so a basis and a live observation always align.

x = concat(temporal profile[L], region profile[K], segment profile[3], product profile[K])
Region/product use sorted |residual| shares (comparable across episodes with different
slice identities); segment keeps its declared New/Returning/VIP identity (stable across
episodes).
"""

import numpy as np

from cause_config import BASIS_WINDOW_DAYS, TOP_K_SLICES

FEATURE_VERSION = "v1"
SEGMENT_ORDER = ("New", "Returning", "VIP")
VECTOR_LENGTH = BASIS_WINDOW_DAYS + TOP_K_SLICES + len(SEGMENT_ORDER) + TOP_K_SLICES


def _normalize(values):
    total = sum(abs(v) for v in values)
    if total <= 0:
        return [0.0] * len(values)
    return [v / total for v in values]


def _temporal_profile(matrix, window_start):
    """Sum of region-dimension residuals per day -- region slices partition the whole
    customer base, so this approximates the company-wide daily series without a new query."""
    by_day = {d: 0.0 for d in range(window_start, window_start + BASIS_WINDOW_DAYS)}
    for (dimension, _slice_value), residuals in matrix.items():
        if dimension != "region":
            continue
        for day, _expected, residual in residuals:
            if residual is not None and day in by_day:
                by_day[day] += residual
    return _normalize([by_day[d] for d in sorted(by_day)])


def _concentration_profile(matrix, dimension, window_start, window_end, k):
    totals = []
    for (dim, _slice_value), residuals in matrix.items():
        if dim != dimension:
            continue
        magnitude = sum(
            abs(residual) for day, _expected, residual in residuals
            if residual is not None and window_start <= day <= window_end
        )
        totals.append(magnitude)
    totals.sort(reverse=True)
    totals = totals[:k] + [0.0] * max(0, k - len(totals))
    return _normalize(totals)


def _segment_profile(matrix, window_start, window_end):
    per_segment = {}
    for (dimension, slice_value), residuals in matrix.items():
        if dimension != "segment":
            continue
        per_segment[slice_value] = sum(
            abs(residual) for day, _expected, residual in residuals
            if residual is not None and window_start <= day <= window_end
        )
    return _normalize([per_segment.get(s, 0.0) for s in SEGMENT_ORDER])


def build_shape_vector(matrix, window_start, window_end):
    temporal = _temporal_profile(matrix, window_start)
    region = _concentration_profile(matrix, "region", window_start, window_end, TOP_K_SLICES)
    segment = _segment_profile(matrix, window_start, window_end)
    product = _concentration_profile(matrix, "product", window_start, window_end, TOP_K_SLICES)
    vector = np.array(temporal + region + segment + product, dtype=float)
    assert len(vector) == VECTOR_LENGTH
    return vector
