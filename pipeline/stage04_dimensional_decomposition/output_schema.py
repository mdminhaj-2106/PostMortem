"""Rejects any free-text field outside the fixed enums (design doc §5's still-valid
rule) -- a plain assertion, not a new dependency. slice_value is deliberately exempt:
it's real per-episode data (a region code, a segment name, a product category), not a
free-text field an upstream stage fabricated.
"""

from models import DIMENSIONS, ELIGIBILITIES, OBSERVATION_STATUSES


def validate(decomposition_result):
    for s in decomposition_result.slices:
        assert s.dimension in DIMENSIONS, f"free-text dimension: {s.dimension!r}"
        assert s.eligibility in ELIGIBILITIES, f"free-text eligibility: {s.eligibility!r}"
        assert s.observation_status in OBSERVATION_STATUSES, \
            f"free-text observation_status: {s.observation_status!r}"
        assert isinstance(s.slice_value, str) and s.slice_value, f"invalid slice_value: {s.slice_value!r}"
        # expected/observed are nullable ONLY when the slice is declared unmeasured
        # (F10) -- a null with an OBSERVED status would be exactly the ambiguity this
        # field exists to remove.
        for field_name in ("expected", "observed"):
            value = getattr(s, field_name)
            if s.observation_status == "NO_DATA_IN_WINDOW":
                assert value is None, f"{field_name} must be None when unmeasured: {value!r}"
            else:
                assert isinstance(value, (int, float)), f"non-numeric {field_name}: {value!r}"
        if s.observation_status == "NO_DATA_IN_WINDOW":
            assert s.deviation_pct is None and s.unusualness_percentile is None, \
                "an unmeasured slice must not carry a deviation or a percentile"
        for field_name in ("deviation_pct", "unusualness_percentile"):
            value = getattr(s, field_name)
            assert value is None or isinstance(value, (int, float)), f"non-numeric {field_name}: {value!r}"
