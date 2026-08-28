"""Rejects any free-text field outside the fixed enums (design doc §5's still-valid
rule) -- a plain assertion, not a new dependency. slice_value is deliberately exempt:
it's real per-episode data (a region code, a segment name, a product category), not a
free-text field an upstream stage fabricated.
"""

from models import DIMENSIONS, ELIGIBILITIES


def validate(decomposition_result):
    for s in decomposition_result.slices:
        assert s.dimension in DIMENSIONS, f"free-text dimension: {s.dimension!r}"
        assert s.eligibility in ELIGIBILITIES, f"free-text eligibility: {s.eligibility!r}"
        assert isinstance(s.slice_value, str) and s.slice_value, f"invalid slice_value: {s.slice_value!r}"
        for field_name in ("expected", "observed"):
            value = getattr(s, field_name)
            assert isinstance(value, (int, float)), f"non-numeric {field_name}: {value!r}"
        for field_name in ("deviation_pct", "unusualness_percentile"):
            value = getattr(s, field_name)
            assert value is None or isinstance(value, (int, float)), f"non-numeric {field_name}: {value!r}"
