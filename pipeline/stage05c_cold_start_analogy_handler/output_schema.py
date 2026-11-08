"""Rejects any free-text field outside the declared enums, plus the percentile/status
consistency rule -- belt-and-suspenders with models.BorrowedAttribution.__post_init__,
same dual-validation pattern as Stage 4/5b's own output_schema.py.
"""

from models import ANALOG_SOURCES, CONFIDENCE_TIERS, STATUSES


def validate(stage5c_result):
    for a in stage5c_result.attributions:
        assert a.status in STATUSES, f"free-text status: {a.status!r}"
        assert a.analog_source in ANALOG_SOURCES, f"free-text analog_source: {a.analog_source!r}"
        assert a.confidence_tier in CONFIDENCE_TIERS, f"free-text confidence_tier: {a.confidence_tier!r}"
        assert isinstance(a.slice_value, str) and a.slice_value, f"invalid slice_value: {a.slice_value!r}"
        has_percentile = a.borrowed_percentile is not None
        if a.status == "BORROWED":
            assert has_percentile, "status=BORROWED must carry a real borrowed_percentile"
            assert 0.0 <= a.borrowed_percentile <= 1.0, f"percentile out of range: {a.borrowed_percentile!r}"
        else:
            assert not has_percentile, "status=NO_REFERENCE_AVAILABLE must not carry a percentile"
