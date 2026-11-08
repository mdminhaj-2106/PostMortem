"""Stage 8 orchestrator -- (Stage7Result, Optional[ConfoundedAttributionResult]) ->
Stage8Result. See .claude/plans/stage8-counterfactual-impact-engine.md.

Usage:
    python stage8.py --episode-id 15
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

import hypothesis_eligibility
import impact
import output_schema
import reconstruction
import uncertainty
from canonical_bridge import compute_residuals, load_kpi_timeline
from config import PRE_WINDOW_HISTORY_DAYS
from models import CounterfactualImpact, CounterfactualPoint, InterventionSpec, Stage8Result

# Same _KPI_PREFERENCE pattern as stage5a.py/stage5b.py -- pick one primary KPI
# to build the time-resolved trajectory for out of whichever ones this cluster
# actually spans.
_KPI_PREFERENCE = ("revenue", "orders_count", "units_sold", "avg_order_value", "active_customers_purchased_30d")


def _pick_kpi(kpi_names):
    return next((k for k in _KPI_PREFERENCE if k in kpi_names), next(iter(kpi_names)))


def _fetch_series(cur, episode_id, kpi_name, window_start, window_end):
    day_range = range(window_start - PRE_WINDOW_HISTORY_DAYS, window_end + 1)
    timeline = load_kpi_timeline(cur, episode_id, kpi_name, day_range)
    expected_by_day = {day_offset: expected for day_offset, expected, _residual in compute_residuals(timeline)}
    observed_by_day = {day_offset: (rv.value if rv is not None else None) for day_offset, rv in timeline}
    return timeline, observed_by_day, expected_by_day


def _skipped_impact(hypothesis, reason_codes):
    status = "MECHANISM_UNAVAILABLE" if "NO_VALIDATED_INTERVENTION_MECHANISM" in reason_codes else "UNAVAILABLE"
    return CounterfactualImpact(
        hypothesis_id=hypothesis.hypothesis_id, member_causes=hypothesis.member_causes,
        hypothesis_type=hypothesis.hypothesis_type,
        scenario="EVENT_NEVER_OCCURRED", intervention_day_offset=None,
        observed_aggregate=None, counterfactual_aggregate=None, estimated_impact=None,
        impact_pct_of_observed=None, impact_direction=None, impact_lower=None, impact_upper=None,
        trajectory=[],
        stage7_confidence=hypothesis.confidence_bucket, data_confidence="INSUFFICIENT_DATA",
        uncertainty_status="LIMITED",
        identifiability=hypothesis.identifiability, borrowed=hypothesis.borrowed,
        estimation_status=status, estimation_reason_codes=reason_codes,
    )


def _estimate_one(cur, episode_id, kpi_name, hypothesis, contribution, window_start, window_end, reason_codes):
    timeline, observed_by_day, expected_by_day = _fetch_series(cur, episode_id, kpi_name, window_start, window_end)

    spec = InterventionSpec(
        hypothesis_id=hypothesis.hypothesis_id, member_causes=hypothesis.member_causes,
        mode="EVENT_NEVER_OCCURRED",
    )
    raw_points = reconstruction.reconstruct_points(
        observed_by_day, expected_by_day, window_start, window_end,
        contribution.share, spec.mode, spec.intervention_day_offset,
    )

    conf = uncertainty.data_confidence(timeline)
    pre_window_days = range(window_start - PRE_WINDOW_HISTORY_DAYS, window_start)
    stdev = uncertainty.residual_stdev(expected_by_day, observed_by_day, pre_window_days)

    observed_agg, cf_agg, est_impact, impact_pct = impact.aggregate(raw_points)
    impact_lower, impact_upper = uncertainty.impact_interval(
        est_impact, stdev, window_end - window_start + 1, contribution.share
    )

    points = [
        CounterfactualPoint(
            day_offset=p["day_offset"], observed_value=p["observed_value"], baseline_value=p["baseline_value"],
            counterfactual_value=p["counterfactual_value"], estimated_impact=p["estimated_impact"],
            data_confidence=conf,
        )
        for p in raw_points
    ]

    return CounterfactualImpact(
        hypothesis_id=hypothesis.hypothesis_id, member_causes=hypothesis.member_causes,
        hypothesis_type=hypothesis.hypothesis_type,
        scenario=spec.mode, intervention_day_offset=spec.intervention_day_offset,
        observed_aggregate=observed_agg, counterfactual_aggregate=cf_agg, estimated_impact=est_impact,
        impact_pct_of_observed=impact_pct,
        impact_direction=impact.KPI_DIRECTION if est_impact is not None else None,
        impact_lower=impact_lower, impact_upper=impact_upper,
        trajectory=points,
        stage7_confidence=hypothesis.confidence_bucket, data_confidence=conf, uncertainty_status="LIMITED",
        identifiability=hypothesis.identifiability, borrowed=hypothesis.borrowed,
        estimation_status="ESTIMATED", estimation_reason_codes=list(reason_codes) + ["BASELINE_RECONSTRUCTION"],
    )


def run_stage8(cur, episode_id, cluster_id, window_start, window_end, kpi_names, stage7_result, stage5b_result):
    if stage7_result.abstained:
        return Stage8Result(
            episode_id=episode_id, cluster_id=cluster_id,
            window_start_day_offset=window_start, window_end_day_offset=window_end,
            estimates=[], skipped_hypotheses=[], abstained_upstream=True,
        )

    kpi_name = _pick_kpi(kpi_names)
    estimates, skipped = [], []
    for h in stage7_result.hypotheses:
        eligible, contribution, reason_codes = hypothesis_eligibility.assess(h, stage5b_result)
        if not eligible:
            skipped.append({"hypothesis_id": h.hypothesis_id, "reason_codes": reason_codes})
            estimates.append(_skipped_impact(h, reason_codes))
            continue
        estimates.append(
            _estimate_one(cur, episode_id, kpi_name, h, contribution, window_start, window_end, reason_codes)
        )

    result = Stage8Result(
        episode_id=episode_id, cluster_id=cluster_id,
        window_start_day_offset=window_start, window_end_day_offset=window_end,
        estimates=estimates, skipped_hypotheses=skipped, abstained_upstream=False,
    )
    output_schema.validate(result)
    return result


def main():
    import stage7_bridge

    parser = argparse.ArgumentParser(description="Run Stage 8 counterfactual impact engine.")
    parser.add_argument("--episode-id", type=int, required=True)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            stage3_results = stage7_bridge.run_stage3(cur, args.episode_id)
            if not stage3_results:
                print(f"no Stage 3 results for episode {args.episode_id}")
                return
            stage3_result = stage3_results[0]
            print(f"investigating: {stage3_result}")

            decomposition_result = stage7_bridge.run_stage4(cur, args.episode_id, stage3_result)
            reference = stage7_bridge.load_reference()
            fingerprint_result, cold_start_result = stage7_bridge.run_stage5a_and_5c(
                cur, args.episode_id, stage3_result, decomposition_result, reference
            )

            forked, reason = stage7_bridge.should_fork(fingerprint_result.cause_scores, decomposition_result)
            print(f"Stage 5b fork decision: {forked} ({reason})")
            stage5b_result = (
                stage7_bridge.run_stage5b(cur, args.episode_id, fingerprint_result, decomposition_result)
                if forked else None
            )

            evidence_result = stage7_bridge.run_stage6(cur, args.episode_id, decomposition_result, fingerprint_result)

            stage7_result = stage7_bridge.run_stage7(
                args.episode_id, stage3_result.cluster_id,
                fingerprint_result, stage5b_result, cold_start_result, evidence_result,
            )
            print(f"Stage 7: abstained={stage7_result.abstained}, {len(stage7_result.hypotheses)} hypothesis(es)")

            result = run_stage8(
                cur, args.episode_id, stage3_result.cluster_id,
                stage3_result.window_start_day_offset, stage3_result.window_end_day_offset,
                stage3_result.kpi_names, stage7_result, stage5b_result,
            )
            print(f"\nabstained_upstream={result.abstained_upstream}, {len(result.estimates)} estimate(s)")
            for est in result.estimates:
                print(
                    f"  {est.hypothesis_id} [{est.estimation_status}] "
                    f"impact={est.estimated_impact} {est.estimation_reason_codes}"
                )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
