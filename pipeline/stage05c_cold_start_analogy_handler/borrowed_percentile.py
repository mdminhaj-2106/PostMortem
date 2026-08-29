"""Core borrow-and-score mechanism (design doc §4, corpus-sourced per this plan's
Risk #1 correction). Reuses Stage 2's real score_unusualness exactly as it exists --
never reimplements the percentile-rank formula -- by building a synthetic residuals
list with the reference distribution as "prior history" and the thin slice's own
deviation as the final entry, then reading off that entry's score.
"""

import stage2_bridge


def score(deviation_pct, reference_entry):
    """reference_entry: {"samples": [float, ...], "n": int} or None/empty -- the pooled
    cross-episode relative-deviation distribution for this slice's own (kpi, dimension,
    slice_value), built by reference_builder.py. Returns None (abstain) when there's no
    reference to borrow from -- never a fabricated percentile."""
    if not reference_entry or not reference_entry.get("samples"):
        return None
    samples = reference_entry["samples"]
    synthetic = [(i, None, s) for i, s in enumerate(samples)] + [(len(samples), None, deviation_pct)]
    scored = stage2_bridge.score_unusualness(synthetic)
    return scored[-1][1]
