"""Stage 4 self-check -- offline invariant checks (no DB) + live-DB checks against
the real Neon dataset, mirroring Stage 2/3's test_stage2.py/test_stage3.py split.

Run: .venv/bin/python test_stage4.py
"""

import os

import psycopg2
from dotenv import load_dotenv

import decomposer
import dimension_config
import output_schema
from models import DecompositionResult, SliceResult
from slice_fetcher import Observation
from stage4 import run_stage4

# --- offline ---


def test_slice_result_rejects_invalid_dimension():
    try:
        SliceResult(
            kpi_name="revenue", dimension="channel", slice_value="SP",
            window_start_day_offset=0, window_end_day_offset=5,
            expected=1.0, observed=1.0, deviation_pct=0.0,
            unusualness_percentile=None, eligibility="ELIGIBLE",
        )
        assert False, "expected ValueError for an undeclared dimension"
    except ValueError:
        pass


def test_slice_result_rejects_invalid_eligibility():
    try:
        SliceResult(
            kpi_name="revenue", dimension="region", slice_value="SP",
            window_start_day_offset=0, window_end_day_offset=5,
            expected=1.0, observed=1.0, deviation_pct=0.0,
            unusualness_percentile=None, eligibility="MADE_UP",
        )
        assert False, "expected ValueError for a free-text eligibility"
    except ValueError:
        pass


def test_decomposition_result_holds_slices():
    s = SliceResult(
        kpi_name="revenue", dimension="region", slice_value="SP",
        window_start_day_offset=0, window_end_day_offset=5,
        expected=100.0, observed=110.0, deviation_pct=0.1,
        unusualness_percentile=0.9, eligibility="ELIGIBLE",
    )
    result = DecompositionResult(episode_id=1, cluster_id="cluster_1_0_5", slices=[s])
    assert result.slices == [s]


def test_dimension_applicability_excludes_product_for_active_customers():
    assert "product" not in dimension_config.applicable_dimensions("active_customers_purchased_30d")
    assert set(dimension_config.applicable_dimensions("active_customers_purchased_30d")) == {"region", "segment"}
    assert set(dimension_config.applicable_dimensions("revenue")) == {"region", "segment", "product"}


def test_decompose_slice_eligible_and_insufficient():
    """Synthetic two-slice fixture: one dense/eligible, one fully-missing/insufficient.
    Monkeypatches slice_fetcher.load_slice_timeline (not the real DB) to isolate the
    aggregation + eligibility-gated-percentile logic in decomposer._decompose_slice."""
    dense = [(d, Observation(value=100.0 + (d % 3), imputation_flag="untouched")) for d in range(0, 40)]
    sparse = [(d, None) for d in range(0, 40)]

    def fake_load(cur, episode_id, kpi_name, dimension, slice_value, day_range):
        return dense if slice_value == "SP" else sparse

    original = decomposer.slice_fetcher.load_slice_timeline
    decomposer.slice_fetcher.load_slice_timeline = fake_load
    try:
        eligible = decomposer._decompose_slice(None, 1, "revenue", "region", "SP", 30, 39)
        insufficient = decomposer._decompose_slice(None, 1, "active_customers_purchased_30d", "region", "AP", 30, 39)
    finally:
        decomposer.slice_fetcher.load_slice_timeline = original

    assert eligible.eligibility == "ELIGIBLE"
    assert eligible.unusualness_percentile is not None
    assert eligible.expected > 0 and eligible.observed > 0

    assert insufficient.eligibility == "INSUFFICIENT_DATA"
    assert insufficient.unusualness_percentile is None, "never fabricate a percentile for INSUFFICIENT_DATA"
    assert insufficient.expected == 0.0 and insufficient.observed == 0.0
    assert insufficient.deviation_pct is None


def test_output_schema_accepts_clean_result():
    s = SliceResult(
        kpi_name="revenue", dimension="region", slice_value="SP",
        window_start_day_offset=0, window_end_day_offset=5,
        expected=100.0, observed=110.0, deviation_pct=0.1,
        unusualness_percentile=0.9, eligibility="ELIGIBLE",
    )
    output_schema.validate(DecompositionResult(episode_id=1, cluster_id=None, slices=[s]))


def test_output_schema_rejects_injected_free_text():
    s = SliceResult(
        kpi_name="revenue", dimension="region", slice_value="SP",
        window_start_day_offset=0, window_end_day_offset=5,
        expected=100.0, observed=110.0, deviation_pct=0.1,
        unusualness_percentile=0.9, eligibility="ELIGIBLE",
    )
    s.eligibility = "some free text an upstream bug injected"  # bypasses __post_init__
    try:
        output_schema.validate(DecompositionResult(episode_id=1, cluster_id=None, slices=[s]))
        assert False, "expected an AssertionError for an injected free-text field"
    except AssertionError:
        pass


# --- live DB ---
#
# A real finding from live verification, not just the plan's a-priori assumption: the
# new sliced views deliberately scaffold every (day, slice_value) pair and COALESCE a
# no-orders slice-day to 0 rather than a missing row (views.sql's comment on this).
# eligibility.assess_eligibility counts a 0-valued observation as usable, identical to
# a large observation -- so for a given window, region SIZE turns out not to drive
# eligibility at all; window RECENCY (how many trailing days of history exist) does,
# uniformly across every slice_value. A short-trailing-history window (Stage 3's
# earliest flagged windows, close to episode day 0) makes every region/segment slice
# LIMITED_HISTORY together; a window deep enough into the episode (>=30 trailing days)
# makes every slice ELIGIBLE together, including economically-flat small regions (their
# expected/observed legitimately settle near 0, not their eligibility). Both tests
# below assert this verified behavior, not the plan's original small-region-sparsity
# framing -- see the Stage 4 completion report / README for the full note.


def test_short_trailing_history_gates_percentile_for_every_slice(cur):
    stage3_results = stage3_bridge_run_stage3(cur, day_range=range(0, 25))
    early = next(r for r in stage3_results if r.kpi_names == ["active_customers_purchased_30d"])
    assert early.window_start_day_offset < 30, "expected a window too close to day 0 for 30 trailing obs"

    result = run_stage4(cur, 1, early)
    region_slices = [s for s in result.slices if s.dimension == "region"]
    assert region_slices
    assert all(s.eligibility in ("LIMITED_HISTORY", "INSUFFICIENT_DATA") for s in region_slices)
    assert all(s.unusualness_percentile is None for s in region_slices), \
        "never fabricate a percentile for LIMITED_HISTORY/INSUFFICIENT_DATA"


def test_run_stage4_covers_every_applicable_slice_and_allows_real_percentiles(cur):
    stage3_results = stage3_bridge_run_stage3(cur, day_range=range(80, 120))
    late = next(r for r in stage3_results if r.kpi_names == ["revenue"])
    assert late.window_start_day_offset >= 30, "expected a window with a real 30-day trailing history"

    result = run_stage4(cur, 1, late)
    seen = {(s.kpi_name, s.dimension) for s in result.slices}
    expected = {(kpi, dim) for kpi in late.kpi_names for dim in dimension_config.applicable_dimensions(kpi)}
    assert expected, "expected at least one applicable (kpi, dimension) pair"
    assert expected <= seen, f"missing (kpi, dimension) pairs: {expected - seen}"

    sp = next(s for s in result.slices if s.dimension == "region" and s.slice_value == "SP")
    assert sp.eligibility == "ELIGIBLE"
    assert sp.unusualness_percentile is not None, "an ELIGIBLE slice should carry a real percentile"


def stage3_bridge_run_stage3(cur, day_range):
    import stage3_bridge

    results = stage3_bridge.run_stage3(cur, 1, day_range=day_range)
    assert results, "expected at least one Stage 3 result for episode 1 in this day range"
    return results


if __name__ == "__main__":
    test_slice_result_rejects_invalid_dimension()
    test_slice_result_rejects_invalid_eligibility()
    test_decomposition_result_holds_slices()
    test_dimension_applicability_excludes_product_for_active_customers()
    test_decompose_slice_eligible_and_insufficient()
    test_output_schema_accepts_clean_result()
    test_output_schema_rejects_injected_free_text()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            test_short_trailing_history_gates_percentile_for_every_slice(cur)
            test_run_stage4_covers_every_applicable_slice_and_allows_real_percentiles(cur)
    finally:
        conn.close()
    print("OK")
