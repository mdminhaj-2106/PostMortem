"""Stage 9 self-check -- offline invariant checks (no DB) + one live-DB check
against episode 15's real chain, mirroring Stage 8's own test_stage8.py split.
Cross-stage input fixtures use plain SimpleNamespace objects rather than
importing the real upstream dataclasses -- Stage 9's own code only ever reads
attributes off them (never isinstance-checks), same reasoning as test_stage8.py.

Run: .venv/bin/python test_stage9.py
"""

import os
from types import SimpleNamespace

import psycopg2
from dotenv import load_dotenv

import action_builder
import feasibility
import intent_resolver
import lever_resolver
import mechanism_resolver
import output_schema
import selection
import success_criteria
from monitoring import build_monitoring_plan
from owner_resolver import resolve_owners
from stage9 import run_stage9

# --- fixture builders ---


def _hypothesis(hypothesis_id, member_causes, rank=1, identifiability="IDENTIFIED", borrowed=False):
    return SimpleNamespace(
        hypothesis_id=hypothesis_id, member_causes=member_causes, rank=rank,
        identifiability=identifiability, borrowed=borrowed,
    )


def _estimate(hypothesis_id, member_causes, stage7_confidence, estimated_impact, estimation_status,
              identifiability="IDENTIFIED", borrowed=False, impact_lower=None, impact_upper=None):
    return SimpleNamespace(
        hypothesis_id=hypothesis_id, member_causes=member_causes, stage7_confidence=stage7_confidence,
        estimated_impact=estimated_impact, estimation_status=estimation_status,
        identifiability=identifiability, borrowed=borrowed,
        impact_lower=impact_lower, impact_upper=impact_upper,
        estimation_reason_codes=["STAGE5B_QUANTITATIVE_CONSTRAINT"] if estimation_status == "ESTIMATED" else ["X"],
    )


def _stage7_result(hypotheses, abstained=False):
    return SimpleNamespace(hypotheses=hypotheses, abstained=abstained)


def _stage8_result(estimates, abstained_upstream=False, episode_id=1, cluster_id="cluster_1"):
    return SimpleNamespace(
        episode_id=episode_id, cluster_id=cluster_id, estimates=estimates, abstained_upstream=abstained_upstream,
    )


def _decomposition_slice(kpi_name, dimension="product"):
    return SimpleNamespace(kpi_name=kpi_name, dimension=dimension)


def _decomposition_result(slices):
    return SimpleNamespace(slices=slices)


# --- offline: mechanism_resolver.py / lever_resolver.py ---


def test_mechanism_resolver_real_causes():
    assert mechanism_resolver.resolve_mechanism("product_outage") == "reliability_degradation"
    assert mechanism_resolver.resolve_mechanism("marketing_cut") == "reduced_acquisition"
    assert mechanism_resolver.resolve_mechanism("competitor_launch") == "competitive_pressure"
    assert mechanism_resolver.resolve_mechanism("inventory_shortage") == "product_unavailability"


def test_mechanism_resolver_seasonal_is_non_actionable():
    assert mechanism_resolver.resolve_mechanism("seasonal") is None


def test_mechanism_resolver_undeclared_cause_raises():
    try:
        mechanism_resolver.resolve_mechanism("meteor_strike")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_lever_resolver_undeclared_mechanism_raises():
    try:
        lever_resolver.resolve_lever("undeclared_mechanism")
        assert False, "expected ValueError"
    except ValueError:
        pass


# --- offline: action_builder.py ---


def test_build_action_single_cause():
    mechanisms, lever, action_type, risk_tier = action_builder.build_action(["product_outage"])
    assert mechanisms == ["reliability_degradation"]
    assert lever == "restore_reliability"
    assert action_type == "REPAIR"
    assert risk_tier == "LOW_REGRET"


def test_build_action_joint_dedupes_and_never_splits():
    mechanisms, lever, action_type, risk_tier = action_builder.build_action(
        ["product_outage", "marketing_cut", "product_outage"]
    )
    assert mechanisms == ["reduced_acquisition", "reliability_degradation"]
    assert lever == "restore_marketing_spend + restore_reliability"


def test_build_action_all_non_actionable_members_yields_no_mechanism():
    mechanisms, lever, action_type, risk_tier = action_builder.build_action(["seasonal"])
    assert mechanisms == [] and lever is None and action_type is None and risk_tier is None


def test_resolve_target_scope_with_flagged_facet():
    scope = action_builder.resolve_target_scope(
        _decomposition_result([_decomposition_slice("revenue")]),
        flagged_facets_fn=lambda dr: [("product", "Auto")],
    )
    assert scope == {"product": "Auto"}


def test_resolve_target_scope_empty_facets_is_not_fabricated_global():
    scope = action_builder.resolve_target_scope(
        _decomposition_result([_decomposition_slice("revenue")]),
        flagged_facets_fn=lambda dr: [],
    )
    assert scope == {}


def test_resolve_target_scope_no_decomposition():
    assert action_builder.resolve_target_scope(None, flagged_facets_fn=lambda dr: [("product", "Auto")]) == {}


# --- offline: owner_resolver.py ---


def test_resolve_owners_single_cause_has_no_secondaries():
    primary, secondary = resolve_owners(["product_outage"])
    assert primary == "engineering"
    assert secondary == []


def test_resolve_owners_joint_has_secondary():
    primary, secondary = resolve_owners(["product_outage", "marketing_cut"])
    assert primary == "marketing"  # "marketing_cut" sorts before "product_outage"
    assert secondary == ["engineering"]


# --- offline: feasibility.py ---


def test_capability_feasibility_available_owner():
    status, reasons = feasibility.capability_feasibility("engineering")
    assert status == "AVAILABLE" and reasons == []


def test_capability_feasibility_no_owner_is_unavailable():
    status, reasons = feasibility.capability_feasibility(None)
    assert status == "UNAVAILABLE" and reasons


def test_context_feasibility_valid_scope():
    status, reasons = feasibility.context_feasibility({"product": "Auto"})
    assert status == "VALID" and reasons == []


def test_context_feasibility_contradictory_scope():
    status, reasons = feasibility.context_feasibility({"product": ""})
    assert status == "CONTEXT_INVALID" and reasons


# --- offline: intent_resolver.py ---


def test_intent_known_and_likely_act():
    assert intent_resolver.resolve_intent("KNOWN", "LOW_REGRET") == "ACT"
    assert intent_resolver.resolve_intent("LIKELY", "HIGH_COMMITMENT") == "ACT"


def test_intent_possible_low_regret_monitors():
    assert intent_resolver.resolve_intent("POSSIBLE", "LOW_REGRET") == "MONITOR"


def test_intent_possible_high_commitment_investigates():
    assert intent_resolver.resolve_intent("POSSIBLE", "HIGH_COMMITMENT") == "INVESTIGATE"


def test_intent_unknown_always_investigates():
    # finding #7: UNKNOWN-confidence hypotheses do reach Stage 9 (Stage 8 never
    # drops one) -- must never resolve to ACT, even with a low-regret action.
    assert intent_resolver.resolve_intent("UNKNOWN", "LOW_REGRET") == "INVESTIGATE"
    assert intent_resolver.resolve_intent("UNKNOWN", "HIGH_COMMITMENT") == "INVESTIGATE"


def test_intent_no_mechanism_investigates_regardless_of_confidence():
    assert intent_resolver.resolve_intent("LIKELY", None) == "INVESTIGATE"


# --- offline: monitoring.py / success_criteria.py ---


def test_monitoring_plan_single_kpi():
    plan = build_monitoring_plan("revenue")
    assert plan.affected_kpis == ["revenue"]
    assert plan.expected_direction == "UP"
    assert plan.monitoring_horizon == "NOT_SPECIFIED"


def test_success_criteria_derivable_iff_estimated():
    assert success_criteria.build_success_criteria("ESTIMATED").status == "DERIVABLE"
    assert success_criteria.build_success_criteria("MECHANISM_UNAVAILABLE").status == "NOT_DERIVABLE"
    assert success_criteria.build_success_criteria("UNAVAILABLE").status == "NOT_DERIVABLE"


# --- offline: selection.py ---


def _candidate(hypothesis_id, stage7_confidence, expected_impact, context_feasibility="VALID",
               action_type="REPAIR", stage7_rank=1, decision_intent="ACT"):
    return SimpleNamespace(
        hypothesis_id=hypothesis_id, stage7_confidence=stage7_confidence, expected_impact=expected_impact,
        context_feasibility=context_feasibility, action_type=action_type, stage7_rank=stage7_rank,
        decision_intent=decision_intent,
    )


def test_selection_diagnosis_authority_golden_path():
    # design doc §87: a higher-impact POSSIBLE hypothesis must not displace a
    # lower-impact LIKELY one as primary -- Stage 7 stays authoritative.
    weaker_but_bigger = _candidate("H2", "POSSIBLE", 3000000.0, stage7_rank=2)
    stronger = _candidate("H1", "LIKELY", 2200000.0, stage7_rank=1)
    primary, alternatives = selection.select_recommendations([stronger, weaker_but_bigger])
    assert primary.hypothesis_id == "H1"
    assert [a.hypothesis_id for a in alternatives] == ["H2"]


def test_selection_dominance_drops_strictly_worse_candidate():
    a = _candidate("H1", "LIKELY", 3000000.0, stage7_rank=1)
    dominated = _candidate("H2", "POSSIBLE", 2000000.0, context_feasibility="CONTEXT_INVALID", stage7_rank=2)
    primary, alternatives = selection.select_recommendations([a, dominated])
    assert primary.hypothesis_id == "H1"
    assert alternatives == []


def test_selection_conflict_defers_lower_priority_action():
    winner = _candidate("H1", "LIKELY", 3000000.0, action_type="PRICE_INCREASE", stage7_rank=1)
    loser = _candidate("H2", "POSSIBLE", 2000000.0, action_type="PRICE_DECREASE", stage7_rank=2)
    conflicts = {"PRICE_INCREASE": ("PRICE_DECREASE",), "PRICE_DECREASE": ("PRICE_INCREASE",)}
    ordered = sorted([winner, loser], key=selection._sort_key)
    selection.resolve_conflicts(ordered, conflicts=conflicts)
    assert winner.decision_intent == "ACT"
    assert loser.decision_intent == "DEFER"


# --- offline: run_stage9() orchestration ---


def test_run_stage9_no_action_when_stage7_abstained():
    result = run_stage9(_stage7_result([], abstained=True), _stage8_result([], abstained_upstream=True))
    assert result.decision_status == "NO_DEFENSIBLE_ACTION"
    assert result.primary_recommendation is None


def test_run_stage9_unknown_confidence_never_acts():
    h = _hypothesis("H1", ["inventory_shortage"])
    e = _estimate("H1", ["inventory_shortage"], "UNKNOWN", None, "UNAVAILABLE")
    result = run_stage9(_stage7_result([h]), _stage8_result([e]))
    assert result.primary_recommendation.decision_intent == "INVESTIGATE"
    assert result.decision_status == "INVESTIGATION_RECOMMENDED"


def test_run_stage9_joint_hypothesis_never_splits():
    h = _hypothesis("H_JOINT_0", ["product_outage", "marketing_cut"], identifiability="NON_IDENTIFIABLE_JOINT")
    e = _estimate(
        "H_JOINT_0", ["product_outage", "marketing_cut"], "LIKELY", 2400000.0, "ESTIMATED",
        identifiability="NON_IDENTIFIABLE_JOINT",
    )
    result = run_stage9(_stage7_result([h]), _stage8_result([e]))
    primary = result.primary_recommendation
    assert set(primary.driver) == {"product_outage", "marketing_cut"}
    assert primary.expected_impact == 2400000.0
    assert primary.primary_owner is not None and primary.secondary_owners
    assert not hasattr(primary, "member_impact_split")


def test_run_stage9_borrowed_confidence_survives_into_provenance():
    h = _hypothesis("H1", ["inventory_shortage"], borrowed=True)
    e = _estimate("H1", ["inventory_shortage"], "POSSIBLE", None, "UNAVAILABLE", borrowed=True)
    result = run_stage9(_stage7_result([h]), _stage8_result([e]))
    assert result.primary_recommendation.provenance["confidence_origin"] == "BORROWED"


def test_run_stage9_expected_impact_passed_through_unchanged():
    h = _hypothesis("H1", ["product_outage"])
    e = _estimate(
        "H1", ["product_outage"], "LIKELY", 2200000.0, "ESTIMATED", impact_lower=1700000.0, impact_upper=2800000.0,
    )
    result = run_stage9(_stage7_result([h]), _stage8_result([e]))
    p = result.primary_recommendation
    assert p.expected_impact == 2200000.0
    assert p.impact_lower == 1700000.0 and p.impact_upper == 2800000.0


def test_run_stage9_historical_effectiveness_always_unknown():
    h = _hypothesis("H1", ["product_outage"])
    e = _estimate("H1", ["product_outage"], "LIKELY", 2200000.0, "ESTIMATED")
    result = run_stage9(_stage7_result([h]), _stage8_result([e]))
    assert result.primary_recommendation.historical_effectiveness == "UNKNOWN"


# --- offline: output_schema.py ---


def test_output_schema_no_llm_import_anywhere_in_package():
    output_schema.assert_no_llm_import()


def test_output_schema_rejects_unknown_hypothesis_id():
    from models import MonitoringPlan, Recommendation, Stage9Result, SuccessCriteria

    bogus = Recommendation(
        hypothesis_id="H_NOT_IN_STAGE7", driver=["product_outage"], mechanism=["reliability_degradation"],
        lever="restore_reliability", action_type="REPAIR", target_scope={}, primary_owner="engineering",
        secondary_owners=[], decision_intent="ACT", expected_impact=100.0, impact_lower=None, impact_upper=None,
        stage7_confidence="LIKELY", historical_effectiveness="UNKNOWN", capability_feasibility="AVAILABLE",
        context_feasibility="VALID", monitoring_plan=MonitoringPlan(affected_kpis=["revenue"], expected_direction="UP"),
        success_criteria=SuccessCriteria(status="DERIVABLE", basis="COUNTERFACTUAL_TRAJECTORY"), provenance={},
    )
    result = Stage9Result(episode_id=1, cluster_id="c1", decision_status="RECOMMENDATION_AVAILABLE",
                           primary_recommendation=bogus)
    h = _hypothesis("H1", ["product_outage"])
    try:
        output_schema.validate(result, _stage7_result([h]))
        assert False, "expected AssertionError"
    except AssertionError:
        pass


# --- live: episode 15's real chain (one run, not one per module) ---


def test_live_stage9_episode_15():
    import stage8_bridge

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            stage3_results = stage8_bridge.run_stage3(cur, 15)
            assert stage3_results, "expected at least one Stage 3 cluster for episode 15"
            stage3_result = stage3_results[0]

            decomposition_result = stage8_bridge.run_stage4(cur, 15, stage3_result)
            reference = stage8_bridge.load_reference()
            fingerprint_result, cold_start_result = stage8_bridge.run_stage5a_and_5c(
                cur, 15, stage3_result, decomposition_result, reference
            )
            forked, reason = stage8_bridge.should_fork(fingerprint_result.cause_scores, decomposition_result)
            print(f"Stage 5b fork decision: {forked} ({reason})")
            stage5b_result = (
                stage8_bridge.run_stage5b(cur, 15, fingerprint_result, decomposition_result) if forked else None
            )
            evidence_result = stage8_bridge.run_stage6(cur, 15, decomposition_result, fingerprint_result)

            stage7_result = stage8_bridge.run_stage7(
                15, stage3_result.cluster_id, fingerprint_result, stage5b_result, cold_start_result, evidence_result,
            )
            print(f"Stage 7: abstained={stage7_result.abstained}, {len(stage7_result.hypotheses)} hypothesis(es)")

            stage8_result = stage8_bridge.run_stage8(
                cur, 15, stage3_result.cluster_id,
                stage3_result.window_start_day_offset, stage3_result.window_end_day_offset,
                stage3_result.kpi_names, stage7_result, stage5b_result,
            )
            print(f"Stage 8: abstained_upstream={stage8_result.abstained_upstream}, "
                  f"{len(stage8_result.estimates)} estimate(s)")

            result = run_stage9(stage7_result, stage8_result, decomposition_result, stage8_bridge.flagged_facets)
            print(f"\nlive run: episode 15, decision_status={result.decision_status}")
            if result.primary_recommendation is not None:
                p = result.primary_recommendation
                print(
                    f"  primary: {p.hypothesis_id} intent={p.decision_intent} action={p.action_type} "
                    f"lever={p.lever} owner={p.primary_owner}/{p.secondary_owners} "
                    f"impact={p.expected_impact} scope={p.target_scope} "
                    f"confidence_origin={p.provenance.get('confidence_origin')}"
                )
                for alt in result.alternatives:
                    print(f"  alternative: {alt.hypothesis_id} intent={alt.decision_intent} parallel={alt.parallel_action}")

            if not stage7_result.abstained:
                assert len(stage8_result.estimates) == len(stage7_result.hypotheses)
    finally:
        conn.close()


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    for t in tests:
        t()
        print(f"  {t.__name__} OK")
    print("OK")
