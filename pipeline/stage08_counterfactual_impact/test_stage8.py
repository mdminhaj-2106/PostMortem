"""Stage 8 self-check -- offline invariant checks (no DB) + one live-DB check
against episode 15's real chain, mirroring Stage 7's own test_stage7.py split.
Cross-stage input fixtures use plain SimpleNamespace objects rather than
importing the real upstream dataclasses -- Stage 8's own code only ever reads
attributes off them (never isinstance-checks), same reasoning as test_stage7.py.

Run: .venv/bin/python test_stage8.py
"""

import os
from types import SimpleNamespace

import psycopg2
from dotenv import load_dotenv

import hypothesis_eligibility
import impact
import output_schema
import reconstruction
import uncertainty
from models import CounterfactualImpact, CounterfactualPoint, Stage8Result
from stage8 import run_stage8

# --- fixture builders ---


def _hypothesis(hypothesis_id, member_causes, confidence_bucket="LIKELY", identifiability="IDENTIFIED",
                 borrowed=False, hypothesis_type=None):
    return SimpleNamespace(
        hypothesis_id=hypothesis_id, member_causes=member_causes,
        hypothesis_type=hypothesis_type or ("SINGLE" if len(member_causes) == 1 else "COMPOUND"),
        identifiability=identifiability, borrowed=borrowed, confidence_bucket=confidence_bucket,
    )


def _contribution(cause, share, identifiability="IDENTIFIED", member_causes=None):
    return SimpleNamespace(cause=cause, share=share, identifiability=identifiability, member_causes=member_causes)


def _stage5b(contributions):
    return SimpleNamespace(contributions=contributions)


def _stage7_result(hypotheses, abstained=False):
    return SimpleNamespace(hypotheses=hypotheses, abstained=abstained)


def _impact(**overrides):
    base = dict(
        hypothesis_id="H_product_outage", member_causes=["product_outage"], hypothesis_type="SINGLE",
        scenario="EVENT_NEVER_OCCURRED", intervention_day_offset=None,
        observed_aggregate=800.0, counterfactual_aggregate=1000.0, estimated_impact=200.0,
        impact_pct_of_observed=25.0, impact_direction="HIGHER_IS_BETTER",
        impact_lower=150.0, impact_upper=250.0,
        trajectory=[CounterfactualPoint(
            day_offset=20, observed_value=800.0, baseline_value=1000.0,
            counterfactual_value=1000.0, estimated_impact=200.0, data_confidence="ELIGIBLE",
        )],
        stage7_confidence="LIKELY", data_confidence="ELIGIBLE", uncertainty_status="LIMITED",
        identifiability="IDENTIFIED", borrowed=False,
        estimation_status="ESTIMATED", estimation_reason_codes=["STAGE5B_QUANTITATIVE_CONSTRAINT"],
    )
    base.update(overrides)
    return CounterfactualImpact(**base)


# --- offline: hypothesis_eligibility.py ---


def test_eligibility_unknown_bucket_excluded_by_default():
    h = _hypothesis("H_product_outage", ["product_outage"], confidence_bucket="UNKNOWN")
    eligible, contribution, codes = hypothesis_eligibility.assess(h, _stage5b([_contribution("product_outage", 0.7)]))
    assert eligible is False
    assert codes == ["STAGE7_UNKNOWN"]


def test_eligibility_no_stage5b_result_is_unavailable():
    h = _hypothesis("H_product_outage", ["product_outage"])
    eligible, contribution, codes = hypothesis_eligibility.assess(h, None)
    assert eligible is False
    assert codes == ["NO_VALIDATED_INTERVENTION_MECHANISM"]


def test_eligibility_single_matches_identified_contribution():
    h = _hypothesis("H_product_outage", ["product_outage"])
    stage5b_result = _stage5b([_contribution("product_outage", 0.7), _contribution("unexplained", 0.1)])
    eligible, contribution, codes = hypothesis_eligibility.assess(h, stage5b_result)
    assert eligible is True
    assert contribution.share == 0.7
    assert codes == ["STAGE5B_QUANTITATIVE_CONSTRAINT"]


def test_eligibility_single_absorbed_into_joint_has_no_mechanism():
    # mirrors Stage 7's own "absorbed into joint" case -- the single hypothesis
    # still exists, but has no IDENTIFIED contribution of its own, only a joint one.
    h = _hypothesis("H_product_outage", ["product_outage"])
    stage5b_result = _stage5b([_contribution(
        "product_outage+marketing_cut", 0.9, identifiability="NON_IDENTIFIABLE_JOINT",
        member_causes=["product_outage", "marketing_cut"],
    )])
    eligible, contribution, codes = hypothesis_eligibility.assess(h, stage5b_result)
    assert eligible is False
    assert codes == ["NO_VALIDATED_INTERVENTION_MECHANISM"]


def test_eligibility_compound_matches_joint_contribution():
    h = _hypothesis("H_JOINT_0", ["marketing_cut", "product_outage"], identifiability="NON_IDENTIFIABLE_JOINT")
    stage5b_result = _stage5b([_contribution(
        "product_outage+marketing_cut", 0.9, identifiability="NON_IDENTIFIABLE_JOINT",
        member_causes=["product_outage", "marketing_cut"],
    )])
    eligible, contribution, codes = hypothesis_eligibility.assess(h, stage5b_result)
    assert eligible is True
    assert contribution.share == 0.9


# --- offline: reconstruction.py ---


def test_reconstruct_points_event_never_occurred_full_share():
    # design doc §59: baseline=100, outage effect=-20, observed=80 -> counterfactual=100, impact=20.
    observed_by_day = {20: 80.0}
    expected_by_day = {20: 100.0}
    points = reconstruction.reconstruct_points(observed_by_day, expected_by_day, 20, 20, 1.0, "EVENT_NEVER_OCCURRED")
    assert points[0]["counterfactual_value"] == 100.0
    assert points[0]["estimated_impact"] == 20.0


def test_reconstruct_points_partial_share():
    observed_by_day = {20: 80.0}
    expected_by_day = {20: 100.0}
    points = reconstruction.reconstruct_points(observed_by_day, expected_by_day, 20, 20, 0.5, "EVENT_NEVER_OCCURRED")
    assert points[0]["counterfactual_value"] == 90.0
    assert points[0]["estimated_impact"] == 10.0


def test_reconstruct_points_time_resolved():
    # design doc §60: days 1-4 no outage, days 5-7 outage.
    observed_by_day = {1: 100.0, 2: 100.0, 3: 100.0, 4: 100.0, 5: 80.0, 6: 75.0, 7: 85.0}
    expected_by_day = {d: 100.0 for d in range(1, 8)}
    points = reconstruction.reconstruct_points(observed_by_day, expected_by_day, 1, 7, 1.0, "EVENT_NEVER_OCCURRED")
    by_day = {p["day_offset"]: p for p in points}
    for d in range(1, 5):
        assert by_day[d]["counterfactual_value"] == by_day[d]["observed_value"]
        assert by_day[d]["estimated_impact"] == 0.0
    for d in range(5, 8):
        assert by_day[d]["counterfactual_value"] == 100.0


def test_reconstruct_points_remove_from_time():
    # design doc §61: event day 5-10, intervention day 8 -> days <8 observed world, days >=8 no-event world.
    observed_by_day = {d: 80.0 for d in range(5, 11)}
    expected_by_day = {d: 100.0 for d in range(5, 11)}
    points = reconstruction.reconstruct_points(
        observed_by_day, expected_by_day, 5, 10, 1.0, "REMOVE_FROM_TIME", intervention_day_offset=8,
    )
    by_day = {p["day_offset"]: p for p in points}
    for d in range(5, 8):
        assert by_day[d]["counterfactual_value"] == 80.0  # observed world, unchanged
    for d in range(8, 11):
        assert by_day[d]["counterfactual_value"] == 100.0  # no-event world


def test_reconstruct_points_missing_data_not_fabricated():
    points = reconstruction.reconstruct_points({}, {}, 20, 20, 1.0, "EVENT_NEVER_OCCURRED")
    assert points[0]["counterfactual_value"] is None
    assert points[0]["estimated_impact"] is None


# --- offline: uncertainty.py ---


def test_residual_stdev_computes_real_value():
    observed_by_day = {1: 101.0, 2: 99.0, 3: 102.0, 4: 98.0}
    expected_by_day = {1: 100.0, 2: 100.0, 3: 100.0, 4: 100.0}
    stdev = uncertainty.residual_stdev(expected_by_day, observed_by_day, range(1, 5))
    assert stdev is not None and stdev > 0


def test_residual_stdev_none_with_insufficient_data():
    assert uncertainty.residual_stdev({1: 100.0}, {1: 101.0}, range(1, 2)) is None


def test_impact_interval_contains_point_estimate():
    lower, upper = uncertainty.impact_interval(20.0, stdev=5.0, n_days=5, share=0.7)
    assert lower is not None and upper is not None
    assert lower <= 20.0 <= upper


def test_impact_interval_none_without_stdev():
    assert uncertainty.impact_interval(20.0, None, 5, 0.7) == (None, None)


# --- offline: impact.py ---


def test_impact_aggregate_sums_usable_points():
    points = [
        {"day_offset": 1, "observed_value": 80.0, "baseline_value": 100.0, "counterfactual_value": 100.0},
        {"day_offset": 2, "observed_value": 90.0, "baseline_value": 100.0, "counterfactual_value": 100.0},
    ]
    observed_agg, cf_agg, est_impact, pct = impact.aggregate(points)
    assert observed_agg == 170.0
    assert cf_agg == 200.0
    assert est_impact == 30.0
    assert round(pct, 2) == round(30.0 / 170.0 * 100, 2)


def test_impact_aggregate_none_when_no_usable_points():
    points = [{"day_offset": 1, "observed_value": None, "baseline_value": None, "counterfactual_value": None}]
    assert impact.aggregate(points) == (None, None, None, None)


# --- offline: output_schema.py ---


def test_output_schema_rejects_estimates_when_abstained():
    result = Stage8Result(episode_id=1, cluster_id=None, window_start_day_offset=1, window_end_day_offset=10,
                           estimates=[_impact()], abstained_upstream=True)
    try:
        output_schema.validate(result)
        assert False, "expected AssertionError"
    except AssertionError:
        pass


def test_output_schema_accepts_valid_result():
    result = Stage8Result(episode_id=1, cluster_id=None, window_start_day_offset=20, window_end_day_offset=20,
                           estimates=[_impact()])
    output_schema.validate(result)  # must not raise


def test_output_schema_rejects_trajectory_mismatch():
    bad = _impact(estimated_impact=999.0)  # trajectory still sums to 200.0
    result = Stage8Result(episode_id=1, cluster_id=None, window_start_day_offset=20, window_end_day_offset=20,
                           estimates=[bad])
    try:
        output_schema.validate(result)
        assert False, "expected AssertionError"
    except AssertionError:
        pass


def test_output_schema_rejects_interval_not_containing_point():
    bad = _impact(impact_lower=300.0, impact_upper=400.0)  # point estimate 200.0 falls outside
    result = Stage8Result(episode_id=1, cluster_id=None, window_start_day_offset=20, window_end_day_offset=20,
                           estimates=[bad])
    try:
        output_schema.validate(result)
        assert False, "expected AssertionError"
    except AssertionError:
        pass


# --- offline: run_stage8() orchestration (paths that need no DB) ---


def test_run_stage8_does_not_run_when_abstained():
    result = run_stage8(None, 1, None, 1, 10, ("revenue",), _stage7_result([], abstained=True), None)
    assert result.abstained_upstream is True
    assert result.estimates == []


def test_run_stage8_skips_every_hypothesis_without_stage5b():
    hyps = [_hypothesis("H_product_outage", ["product_outage"]), _hypothesis("H_marketing_cut", ["marketing_cut"])]
    result = run_stage8(None, 1, "cluster_1", 1, 10, ("revenue",), _stage7_result(hyps), None)
    assert result.abstained_upstream is False
    assert len(result.estimates) == 2
    assert all(e.estimation_status == "MECHANISM_UNAVAILABLE" for e in result.estimates)
    assert len(result.skipped_hypotheses) == 2


# --- live: episode 15's real chain (one run, not one per module) ---


def test_live_stage8_episode_15():
    import stage7_bridge

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            stage3_results = stage7_bridge.run_stage3(cur, 15)
            assert stage3_results, "expected at least one Stage 3 cluster for episode 15"
            stage3_result = stage3_results[0]

            decomposition_result = stage7_bridge.run_stage4(cur, 15, stage3_result)
            reference = stage7_bridge.load_reference()
            fingerprint_result, cold_start_result = stage7_bridge.run_stage5a_and_5c(
                cur, 15, stage3_result, decomposition_result, reference
            )
            forked, reason = stage7_bridge.should_fork(fingerprint_result.cause_scores, decomposition_result)
            print(f"Stage 5b fork decision: {forked} ({reason})")
            stage5b_result = (
                stage7_bridge.run_stage5b(cur, 15, fingerprint_result, decomposition_result) if forked else None
            )
            evidence_result = stage7_bridge.run_stage6(cur, 15, decomposition_result, fingerprint_result)

            stage7_result = stage7_bridge.run_stage7(
                15, stage3_result.cluster_id, fingerprint_result, stage5b_result, cold_start_result, evidence_result,
            )
            print(f"Stage 7: abstained={stage7_result.abstained}, {len(stage7_result.hypotheses)} hypothesis(es)")

            result = run_stage8(
                cur, 15, stage3_result.cluster_id,
                stage3_result.window_start_day_offset, stage3_result.window_end_day_offset,
                stage3_result.kpi_names, stage7_result, stage5b_result,
            )
            print(f"\nlive run: episode 15, {len(result.estimates)} estimate(s), abstained_upstream={result.abstained_upstream}")
            for est in result.estimates:
                print(f"  {est.hypothesis_id} [{est.estimation_status}] impact={est.estimated_impact}")
                if stage5b_result is not None and est.estimation_status == "ESTIMATED":
                    matching = [
                        c for c in stage5b_result.contributions
                        if set(c.member_causes or [c.cause]) == set(est.member_causes)
                    ]
                    if matching:
                        print(f"    (Stage 5b's own reported contribution: {matching[0].contribution})")

            if not stage7_result.abstained:
                assert len(result.estimates) == len(stage7_result.hypotheses)
    finally:
        conn.close()


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    for t in tests:
        t()
        print(f"  {t.__name__} OK")
    print("OK")
