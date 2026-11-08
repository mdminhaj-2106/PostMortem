"""Stage 9 orchestrator -- (Stage7Result, Stage8Result, DecompositionResult) ->
Stage9Result. See .claude/plans/stage9-recommendation-assembly.md.

Usage:
    python stage9.py --episode-id 15
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

import output_schema
from action_builder import build_action, resolve_target_scope
from feasibility import capability_feasibility, context_feasibility
from intent_resolver import resolve_intent
from models import ActionCandidate, Recommendation, Stage9Result
from monitoring import build_monitoring_plan
from owner_resolver import resolve_owners
from selection import select_recommendations
from success_criteria import build_success_criteria

# Same _KPI_PREFERENCE pattern as stage8.py's own copy. Stage 8's output
# contract carries no kpi_name field of its own (checked against
# CounterfactualImpact/Stage8Result) -- Stage 9 re-derives the one
# investigated KPI from the decomposition it already receives, using the
# identical preference order Stage 8 used to pick it in the first place.
_KPI_PREFERENCE = ("revenue", "orders_count", "units_sold", "avg_order_value", "active_customers_purchased_30d")

_DECISION_STATUS_BY_INTENT = {
    "ACT": "RECOMMENDATION_AVAILABLE",
    "INVESTIGATE": "INVESTIGATION_RECOMMENDED",
    "MONITOR": "MONITORING_RECOMMENDED",
    # DEFER should never reach here -- selection.resolve_conflicts only defers
    # a lower-priority loser, never the chosen primary.
    "DEFER": "INVESTIGATION_RECOMMENDED",
}


def _pick_kpi(decomposition_result):
    if decomposition_result is None or not decomposition_result.slices:
        return None
    kpi_names = {s.kpi_name for s in decomposition_result.slices}
    return next((k for k in _KPI_PREFERENCE if k in kpi_names), next(iter(kpi_names)))


def _build_candidate(estimate, hypothesis, target_scope, kpi_name):
    mechanisms, lever, action_type, risk_tier = build_action(estimate.member_causes)
    primary_owner, secondary_owners = resolve_owners(estimate.member_causes)
    capability_status, capability_reasons = capability_feasibility(primary_owner)
    context_status, context_reasons = context_feasibility(target_scope)
    intent = resolve_intent(estimate.stage7_confidence, risk_tier)

    return ActionCandidate(
        action_id=f"A_{estimate.hypothesis_id}",
        hypothesis_id=estimate.hypothesis_id,
        driver=list(estimate.member_causes),
        mechanism=mechanisms,
        lever=lever,
        action_type=action_type,
        target_scope=target_scope,
        affected_kpi=kpi_name,
        primary_owner=primary_owner,
        secondary_owners=secondary_owners,
        decision_intent=intent,
        stage7_confidence=estimate.stage7_confidence,
        identifiability=estimate.identifiability,
        borrowed=estimate.borrowed,
        expected_impact=estimate.estimated_impact,
        impact_lower=estimate.impact_lower,
        impact_upper=estimate.impact_upper,
        historical_effectiveness="UNKNOWN",
        capability_feasibility=capability_status,
        context_feasibility=context_status,
        feasibility_reasons=capability_reasons + context_reasons,
        stage7_rank=hypothesis.rank if hypothesis is not None else None,
        estimation_status=estimate.estimation_status,
        monitoring_plan=build_monitoring_plan(kpi_name),
        success_criteria=build_success_criteria(estimate.estimation_status),
        provenance={
            "stage7_hypothesis_id": estimate.hypothesis_id,
            "stage8_estimation_reason_codes": ",".join(estimate.estimation_reason_codes),
            "identifiability": estimate.identifiability,
            "confidence_origin": "BORROWED" if estimate.borrowed else "NATIVE",
        },
    )


def _to_recommendation(candidate, parallel_action=False):
    return Recommendation(
        hypothesis_id=candidate.hypothesis_id,
        driver=candidate.driver,
        mechanism=candidate.mechanism,
        lever=candidate.lever,
        action_type=candidate.action_type,
        target_scope=candidate.target_scope,
        primary_owner=candidate.primary_owner,
        secondary_owners=candidate.secondary_owners,
        decision_intent=candidate.decision_intent,
        expected_impact=candidate.expected_impact,
        impact_lower=candidate.impact_lower,
        impact_upper=candidate.impact_upper,
        stage7_confidence=candidate.stage7_confidence,
        historical_effectiveness=candidate.historical_effectiveness,
        capability_feasibility=candidate.capability_feasibility,
        context_feasibility=candidate.context_feasibility,
        monitoring_plan=candidate.monitoring_plan,
        success_criteria=candidate.success_criteria,
        provenance=candidate.provenance,
        parallel_action=parallel_action,
    )


def run_stage9(stage7_result, stage8_result, decomposition_result=None, flagged_facets_fn=None):
    if stage7_result.abstained or stage8_result.abstained_upstream:
        reason = "STAGE7_ABSTAINED" if stage7_result.abstained else "STAGE8_ABSTAINED_UPSTREAM"
        result = Stage9Result(
            episode_id=stage8_result.episode_id, cluster_id=stage8_result.cluster_id,
            decision_status="NO_DEFENSIBLE_ACTION", abstention_reason_codes=[reason],
        )
        output_schema.validate(result, stage7_result)
        return result

    target_scope = resolve_target_scope(decomposition_result, flagged_facets_fn) if flagged_facets_fn else {}
    kpi_name = _pick_kpi(decomposition_result)
    hypotheses_by_id = {h.hypothesis_id: h for h in stage7_result.hypotheses}

    candidates = [
        _build_candidate(estimate, hypotheses_by_id.get(estimate.hypothesis_id), target_scope, kpi_name)
        for estimate in stage8_result.estimates
    ]

    if not candidates:
        result = Stage9Result(
            episode_id=stage8_result.episode_id, cluster_id=stage8_result.cluster_id,
            decision_status="NO_DEFENSIBLE_ACTION", abstention_reason_codes=["NO_STAGE8_ESTIMATES"],
        )
        output_schema.validate(result, stage7_result)
        return result

    primary, alternatives = select_recommendations(candidates)

    result = Stage9Result(
        episode_id=stage8_result.episode_id, cluster_id=stage8_result.cluster_id,
        decision_status=_DECISION_STATUS_BY_INTENT[primary.decision_intent],
        primary_recommendation=_to_recommendation(primary),
        alternatives=[
            _to_recommendation(alt, parallel_action=(alt.decision_intent == "ACT")) for alt in alternatives
        ],
    )
    output_schema.validate(result, stage7_result)
    return result


def main():
    import stage8_bridge

    parser = argparse.ArgumentParser(description="Run Stage 9 recommendation assembly.")
    parser.add_argument("--episode-id", type=int, required=True)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            stage3_results = stage8_bridge.run_stage3(cur, args.episode_id)
            if not stage3_results:
                print(f"no Stage 3 results for episode {args.episode_id}")
                return
            stage3_result = stage3_results[0]
            print(f"investigating: {stage3_result}")

            decomposition_result = stage8_bridge.run_stage4(cur, args.episode_id, stage3_result)
            reference = stage8_bridge.load_reference()
            fingerprint_result, cold_start_result = stage8_bridge.run_stage5a_and_5c(
                cur, args.episode_id, stage3_result, decomposition_result, reference
            )

            forked, reason = stage8_bridge.should_fork(fingerprint_result.cause_scores, decomposition_result)
            print(f"Stage 5b fork decision: {forked} ({reason})")
            stage5b_result = (
                stage8_bridge.run_stage5b(cur, args.episode_id, fingerprint_result, decomposition_result)
                if forked else None
            )

            evidence_result = stage8_bridge.run_stage6(cur, args.episode_id, decomposition_result, fingerprint_result)

            stage7_result = stage8_bridge.run_stage7(
                args.episode_id, stage3_result.cluster_id,
                fingerprint_result, stage5b_result, cold_start_result, evidence_result,
            )
            print(f"Stage 7: abstained={stage7_result.abstained}, {len(stage7_result.hypotheses)} hypothesis(es)")

            stage8_result = stage8_bridge.run_stage8(
                cur, args.episode_id, stage3_result.cluster_id,
                stage3_result.window_start_day_offset, stage3_result.window_end_day_offset,
                stage3_result.kpi_names, stage7_result, stage5b_result,
            )
            print(f"Stage 8: abstained_upstream={stage8_result.abstained_upstream}, "
                  f"{len(stage8_result.estimates)} estimate(s)")

            result = run_stage9(stage7_result, stage8_result, decomposition_result, stage8_bridge.flagged_facets)
            print(f"\nStage 9: decision_status={result.decision_status}")
            if result.primary_recommendation is not None:
                p = result.primary_recommendation
                print(
                    f"  primary: {p.hypothesis_id} intent={p.decision_intent} "
                    f"action={p.action_type} lever={p.lever} owner={p.primary_owner} "
                    f"impact={p.expected_impact} scope={p.target_scope}"
                )
                for alt in result.alternatives:
                    print(
                        f"  alternative: {alt.hypothesis_id} intent={alt.decision_intent} "
                        f"parallel={alt.parallel_action}"
                    )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
