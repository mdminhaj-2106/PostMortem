"""Stage 5c self-check -- offline invariant checks (no DB) + one live-DB end-to-end run.
Run: .venv/bin/python test_stage5c.py
"""

import os

import psycopg2
from dotenv import load_dotenv

import borrowed_percentile
import output_schema
import reference_builder
from models import BorrowedAttribution, Stage5cResult

# --- offline: models.py ---


def test_borrowed_attribution_rejects_invalid_status():
    try:
        BorrowedAttribution(
            kpi_name="revenue", dimension="region", slice_value="SP", deviation_pct=-0.1,
            borrowed_percentile=0.5, reference_sample_count=10, status="MAYBE",
        )
        assert False, "expected ValueError for an undeclared status"
    except ValueError:
        pass


def test_borrowed_attribution_rejects_percentile_with_no_reference_status():
    try:
        BorrowedAttribution(
            kpi_name="revenue", dimension="region", slice_value="SP", deviation_pct=-0.1,
            borrowed_percentile=0.5, reference_sample_count=0, status="NO_REFERENCE_AVAILABLE",
        )
        assert False, "expected ValueError: NO_REFERENCE_AVAILABLE must not carry a percentile"
    except ValueError:
        pass


def test_borrowed_attribution_rejects_borrowed_status_with_no_percentile():
    try:
        BorrowedAttribution(
            kpi_name="revenue", dimension="region", slice_value="SP", deviation_pct=-0.1,
            borrowed_percentile=None, reference_sample_count=10, status="BORROWED",
        )
        assert False, "expected ValueError: BORROWED must carry a real percentile"
    except ValueError:
        pass


# --- offline: borrowed_percentile.py ---


def test_borrowed_percentile_abstains_on_empty_reference():
    assert borrowed_percentile.score(-0.21, None) is None
    assert borrowed_percentile.score(-0.21, {"samples": [], "n": 0}) is None


def test_borrowed_percentile_hand_computable_case():
    # A reference distribution that rarely swings past +-0.05 (90 tame days), plus 10
    # genuinely volatile days at +-0.30. A thin slice's own -0.21 deviation should land
    # materially high (rarer than nearly all the tame days, comparable to the volatile
    # tail) -- mirrors the design doc's worked-example intuition without depending on
    # its now-dropped Product A/B specifics.
    samples = [0.01] * 90 + [0.30] * 10
    percentile = borrowed_percentile.score(-0.21, {"samples": samples, "n": len(samples)})
    assert percentile is not None
    assert percentile >= 0.85, f"expected a materially high percentile, got {percentile}"


# --- offline: output_schema.py ---


def test_output_schema_rejects_free_text_status():
    result = Stage5cResult(episode_id=1, cluster_id=None, attributions=[])
    bad = BorrowedAttribution.__new__(BorrowedAttribution)
    bad.kpi_name, bad.dimension, bad.slice_value = "revenue", "region", "SP"
    bad.deviation_pct, bad.borrowed_percentile, bad.reference_sample_count = -0.1, 0.5, 10
    bad.status, bad.analog_source, bad.confidence_tier = "MAYBE", "CROSS_EPISODE_CORPUS", "BORROWED"
    result.attributions.append(bad)
    try:
        output_schema.validate(result)
        assert False, "expected AssertionError for a free-text status"
    except AssertionError:
        pass


def test_output_schema_accepts_a_clean_result():
    clean = BorrowedAttribution(
        kpi_name="revenue", dimension="region", slice_value="SP", deviation_pct=-0.21,
        borrowed_percentile=0.91, reference_sample_count=100, status="BORROWED",
    )
    result = Stage5cResult(episode_id=1, cluster_id=None, attributions=[clean])
    output_schema.validate(result)  # must not raise


# --- live DB ---


def test_run_stage5c_on_a_known_thin_cluster(cur):
    """episode 1, active_customers_purchased_30d, window 9-14 -- Stage 4's own
    documented live finding: every region slice lands LIMITED_HISTORY together. This
    is the realistic (only reachable) Stage 5c trigger -- see this plan's header."""
    import stage3_bridge
    import stage4_bridge
    from stage5c import run_stage5c

    stage3_results = stage3_bridge.run_stage3(cur, 1, day_range=range(0, 25))
    early = next(r for r in stage3_results if r.kpi_names == ["active_customers_purchased_30d"])
    assert early.window_start_day_offset < 30

    decomposition_result = stage4_bridge.run_stage4(cur, 1, early)
    region_slices = [s for s in decomposition_result.slices if s.dimension == "region"]
    assert region_slices and all(s.eligibility in ("LIMITED_HISTORY", "INSUFFICIENT_DATA") for s in region_slices)

    reference = reference_builder.build_reference(cur, n_episodes=5)
    result = run_stage5c(cur, 1, decomposition_result, reference)
    output_schema.validate(result)

    region_attributions = [a for a in result.attributions if a.dimension == "region"]
    assert region_attributions, "expected at least one region attribution for the thin slate"
    for a in region_attributions:
        if a.status == "BORROWED":
            assert 0.0 <= a.borrowed_percentile <= 1.0
        else:
            assert a.status == "NO_REFERENCE_AVAILABLE" and a.borrowed_percentile is None


def test_run_stage5c_abstains_on_a_key_absent_from_the_reference():
    from stage5c import run_stage5c

    class _Slice:
        def __init__(self):
            self.kpi_name, self.dimension, self.slice_value = "revenue", "region", "NOWHERE"
            self.eligibility, self.deviation_pct = "LIMITED_HISTORY", -0.5

    class _Decomp:
        cluster_id = None
        slices = [_Slice()]

    result = run_stage5c(cur=None, episode_id=1, decomposition_result=_Decomp(), reference={})
    assert len(result.attributions) == 1
    assert result.attributions[0].status == "NO_REFERENCE_AVAILABLE"
    assert result.attributions[0].borrowed_percentile is None


def test_run_stage5c_returns_empty_for_an_all_eligible_decomposition():
    from stage5c import run_stage5c

    class _Slice:
        kpi_name, dimension, slice_value = "revenue", "region", "SP"
        eligibility, deviation_pct = "ELIGIBLE", 0.1

    class _Decomp:
        cluster_id = None
        slices = [_Slice()]

    result = run_stage5c(cur=None, episode_id=1, decomposition_result=_Decomp(), reference={})
    assert result.attributions == []


if __name__ == "__main__":
    test_borrowed_attribution_rejects_invalid_status()
    test_borrowed_attribution_rejects_percentile_with_no_reference_status()
    test_borrowed_attribution_rejects_borrowed_status_with_no_percentile()

    test_borrowed_percentile_abstains_on_empty_reference()
    test_borrowed_percentile_hand_computable_case()

    test_output_schema_rejects_free_text_status()
    test_output_schema_accepts_a_clean_result()

    test_run_stage5c_abstains_on_a_key_absent_from_the_reference()
    test_run_stage5c_returns_empty_for_an_all_eligible_decomposition()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            test_run_stage5c_on_a_known_thin_cluster(cur)
    finally:
        conn.close()
    print("OK")
