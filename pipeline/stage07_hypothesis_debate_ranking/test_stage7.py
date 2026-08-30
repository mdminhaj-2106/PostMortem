"""Stage 7 self-check -- offline invariant checks (no DB) + one live-DB check
against episode 15's real cluster_15_93_94, mirroring Stage 5a/5b/5c/6's own
test_stage*.py split. Cross-stage input fixtures use plain SimpleNamespace
objects rather than importing the real upstream dataclasses -- Stage 7's own
code only ever reads attributes off them (never isinstance-checks), and this
avoids adding bridge plumbing purely for fixture construction.

Run: .venv/bin/python test_stage7.py
"""

import os
from types import SimpleNamespace

import psycopg2
from dotenv import load_dotenv

import abstention
import candidate_assembler
import confidence_resolver
import contradiction_resolver
import evidence_analytical
import evidence_observational
import evidence_structural
import hypothesis_builder
import output_schema
import ranker
import support_resolver
from cause_config import DEPENDENT_PAIRS
from models import (
    CAUSE_FAMILIES, AnalyticalEvidence, Hypothesis, RankedHypothesis, Stage7Result, StructuralEvidence,
)
from stage7 import run_stage7

# --- fixture builders ---


def _fingerprint(cause_scores, top_cause=None, confidence="MEDIUM"):
    return SimpleNamespace(cause_scores=cause_scores, top_cause=top_cause, confidence=confidence)


def _contribution(cause, contribution, share, identifiability="IDENTIFIED", member_causes=None,
                   basis_provenance="LEARNED"):
    return SimpleNamespace(
        cause=cause, contribution=contribution, share=share,
        identifiability=identifiability, member_causes=member_causes, basis_provenance=basis_provenance,
    )


def _stage5b(contributions):
    return SimpleNamespace(contributions=contributions)


def _cold_start(attributions):
    return SimpleNamespace(attributions=attributions)


def _evidence_item(sentiment, relevance_score, text="ticket text", day_offset=80, temporal_tag="DURING"):
    return SimpleNamespace(
        sentiment=sentiment, relevance_score=relevance_score,
        text_snippet=text, day_offset=day_offset, temporal_tag=temporal_tag,
    )


def _evidence_result(items):
    return SimpleNamespace(evidence=items)


def _ranked_hypothesis(**overrides):
    base = dict(
        hypothesis_id="H_product_outage", member_causes=["product_outage"], hypothesis_type="SINGLE",
        identifiability="IDENTIFIED", borrowed=False,
        confidence_bucket="POSSIBLE", confidence_reason_codes=[],
        analytical_evidence=AnalyticalEvidence(), supporting_evidence=[], contradicting_evidence=[],
        neutral_evidence=[], structural_evidence=StructuralEvidence(),
        contradiction_status="NONE", contradiction_reason_codes=[],
        evidence_count=0, independent_source_count=0, independent_entity_count=0,
    )
    base.update(overrides)
    return RankedHypothesis(**base)


# --- offline: models.py + cause_config.py ---


def test_cause_families_match_stage5b():
    import stage5b_bridge
    assert set(CAUSE_FAMILIES) == set(stage5b_bridge.CAUSE_FAMILIES)


def test_dependent_pairs_match_stage5b():
    import stage5b_bridge
    assert DEPENDENT_PAIRS == stage5b_bridge.DEPENDENT_PAIRS


def test_hypothesis_rejects_unknown_cause():
    try:
        Hypothesis(hypothesis_id="H1", member_causes=["pricing_change"], hypothesis_type="SINGLE")
        assert False, "expected ValueError for a cause outside the real vocabulary"
    except ValueError:
        pass


def test_hypothesis_rejects_compound_with_one_member():
    try:
        Hypothesis(hypothesis_id="H1", member_causes=["product_outage"], hypothesis_type="COMPOUND")
        assert False, "expected ValueError"
    except ValueError:
        pass


# --- offline: candidate_assembler.py ---


def test_assemble_single_candidates_applies_floor():
    fr = _fingerprint({
        "product_outage": 0.5, "marketing_cut": 0.03, "competitor_launch": 0.02, "inventory_shortage": 0.45,
    })
    causes = candidate_assembler.assemble_single_candidates(fr)
    assert set(causes) == {"product_outage", "inventory_shortage"}


def test_assemble_joint_candidates_generic_over_member_count():
    # the real live Stage 5b run merged all 5 candidates (4 causes + seasonal) into
    # one FULLY_MERGED bucket -- this must not be treated as an error.
    contributions = [
        _contribution(
            "product_outage+marketing_cut+competitor_launch+inventory_shortage+seasonal", 10.0, 1.0,
            identifiability="NON_IDENTIFIABLE_JOINT",
            member_causes=["product_outage", "marketing_cut", "competitor_launch", "inventory_shortage", "seasonal"],
        ),
        _contribution("unexplained", 0.0, 0.0, identifiability="IDENTIFIED"),
    ]
    joints = candidate_assembler.assemble_joint_candidates(_stage5b(contributions))
    assert len(joints) == 1
    assert len(joints[0]) == 5


def test_assemble_joint_candidates_empty_when_5b_not_run():
    assert candidate_assembler.assemble_joint_candidates(None) == []


# --- offline: hypothesis_builder.py ---


def test_build_hypotheses_keeps_single_and_joint_for_same_cause():
    hyps = hypothesis_builder.build_hypotheses(
        single_causes=["product_outage", "marketing_cut"],
        joint_candidates=[["product_outage", "marketing_cut"]],
    )
    ids = {h.hypothesis_id for h in hyps}
    assert "H_product_outage" in ids and "H_marketing_cut" in ids
    joint = next(h for h in hyps if h.hypothesis_type == "COMPOUND")
    assert joint.member_causes == ["marketing_cut", "product_outage"]
    assert joint.identifiability == "NON_IDENTIFIABLE_JOINT"


# --- offline: evidence_analytical.py ---


def test_analytical_evidence_5a_only():
    fr = _fingerprint({
        "product_outage": 0.6, "marketing_cut": 0.1, "competitor_launch": 0.2, "inventory_shortage": 0.1,
    })
    h = Hypothesis(hypothesis_id="H_product_outage", member_causes=["product_outage"], hypothesis_type="SINGLE")
    a = evidence_analytical.build_analytical_evidence(h, fr, None, None)
    assert a.stage5a_probability == 0.6
    assert a.stage5b_share is None
    assert a.stage5c_is_borrowed is False


def test_analytical_evidence_5b_clean_split():
    fr = _fingerprint({"product_outage": 0.6, "marketing_cut": 0.1, "competitor_launch": 0.2, "inventory_shortage": 0.1})
    contributions = [_contribution("product_outage", 5.0, 0.7)]
    h = Hypothesis(hypothesis_id="H_product_outage", member_causes=["product_outage"], hypothesis_type="SINGLE")
    a = evidence_analytical.build_analytical_evidence(h, fr, _stage5b(contributions), None)
    assert a.stage5b_share == 0.7


def test_analytical_evidence_absorbed_into_joint_has_no_5b_fields():
    fr = _fingerprint({"product_outage": 0.5, "marketing_cut": 0.45, "competitor_launch": 0.03, "inventory_shortage": 0.02})
    contributions = [_contribution(
        "product_outage+marketing_cut", 8.0, 1.0,
        identifiability="NON_IDENTIFIABLE_JOINT", member_causes=["product_outage", "marketing_cut"],
    )]
    h = Hypothesis(hypothesis_id="H_product_outage", member_causes=["product_outage"], hypothesis_type="SINGLE")
    a = evidence_analytical.build_analytical_evidence(h, fr, _stage5b(contributions), None)
    assert a.stage5a_probability == 0.5
    assert a.stage5b_share is None  # absorbed into the joint -- never a fabricated split


def test_analytical_evidence_joint_matches_joint_contribution():
    contributions = [_contribution(
        "product_outage+marketing_cut", 8.0, 0.9,
        identifiability="NON_IDENTIFIABLE_JOINT", member_causes=["product_outage", "marketing_cut"],
    )]
    h = Hypothesis(
        hypothesis_id="H_JOINT_0", member_causes=["marketing_cut", "product_outage"],
        hypothesis_type="COMPOUND", identifiability="NON_IDENTIFIABLE_JOINT",
    )
    a = evidence_analytical.build_analytical_evidence(h, _fingerprint({}), _stage5b(contributions), None)
    assert a.stage5b_share == 0.9
    assert a.stage5a_probability is None


def test_analytical_evidence_borrowed_flag_uniform():
    cs = _cold_start([SimpleNamespace(kpi_name="revenue", dimension="product", slice_value="toys", borrowed_percentile=0.9)])
    h = Hypothesis(hypothesis_id="H_product_outage", member_causes=["product_outage"], hypothesis_type="SINGLE")
    a = evidence_analytical.build_analytical_evidence(h, _fingerprint({}), None, cs)
    assert a.stage5c_is_borrowed is True


# --- offline: evidence_observational.py ---


def test_link_evidence_only_targets_top_cause():
    hyps = hypothesis_builder.build_hypotheses(["product_outage", "marketing_cut"], [])
    er = _evidence_result([_evidence_item("negative", 0.5)])
    linked = evidence_observational.link_evidence(hyps, er, top_cause="product_outage")
    assert set(linked.keys()) == {"H_product_outage"}


def test_link_evidence_negative_sentiment_supports_strong():
    hyps = hypothesis_builder.build_hypotheses(["product_outage"], [])
    er = _evidence_result([_evidence_item("negative", 0.5)])
    ref = evidence_observational.link_evidence(hyps, er, "product_outage")["H_product_outage"][0]
    assert ref.direction == "SUPPORTING"
    assert ref.strength == "STRONG"


def test_link_evidence_positive_sentiment_contradicts_moderate():
    hyps = hypothesis_builder.build_hypotheses(["product_outage"], [])
    er = _evidence_result([_evidence_item("positive", 0.4)])
    ref = evidence_observational.link_evidence(hyps, er, "product_outage")["H_product_outage"][0]
    assert ref.direction == "CONTRADICTING"
    assert ref.strength == "MODERATE"


def test_link_evidence_none_when_no_evidence():
    hyps = hypothesis_builder.build_hypotheses(["product_outage"], [])
    assert evidence_observational.link_evidence(hyps, _evidence_result([]), "product_outage") == {}


# --- offline: evidence_structural.py ---


def test_structural_dependency_consistent_true():
    h = Hypothesis(
        hypothesis_id="H_JOINT_0", member_causes=["marketing_cut", "product_outage"],
        hypothesis_type="COMPOUND", identifiability="NON_IDENTIFIABLE_JOINT",
    )
    se = evidence_structural.build_structural_evidence(h)
    assert se.dependency_consistent is True
    assert se.direction_consistent is None
    assert se.timing_consistent is None


def test_structural_dependency_consistent_false():
    h = Hypothesis(
        hypothesis_id="H_JOINT_0", member_causes=["competitor_launch", "inventory_shortage"],
        hypothesis_type="COMPOUND", identifiability="NON_IDENTIFIABLE_JOINT",
    )
    assert evidence_structural.build_structural_evidence(h).dependency_consistent is False


def test_structural_single_hypothesis_all_none():
    h = Hypothesis(hypothesis_id="H_product_outage", member_causes=["product_outage"], hypothesis_type="SINGLE")
    assert evidence_structural.build_structural_evidence(h).dependency_consistent is None


# --- offline: support_resolver.py / contradiction_resolver.py ---


def test_support_direct_plus_analytical_is_strong():
    h = Hypothesis(hypothesis_id="H_product_outage", member_causes=["product_outage"], hypothesis_type="SINGLE")
    a = AnalyticalEvidence(stage5a_probability=0.7)
    refs = evidence_observational.link_evidence(
        hypothesis_builder.build_hypotheses(["product_outage"], []),
        _evidence_result([_evidence_item("negative", 0.5)]), "product_outage",
    )["H_product_outage"]
    level, codes = support_resolver.resolve_support(h, a, refs, StructuralEvidence())
    assert level == "STRONG"
    assert "DIRECT_OBSERVATIONAL_SUPPORT" in codes and "HIGH_CLASSIFIER_SUPPORT" in codes


def test_contradiction_present_on_contradicting_evidence():
    refs = evidence_observational.link_evidence(
        hypothesis_builder.build_hypotheses(["product_outage"], []),
        _evidence_result([_evidence_item("positive", 0.5)]), "product_outage",
    )["H_product_outage"]
    status, codes = contradiction_resolver.resolve_contradiction(refs)
    assert status == "PRESENT"
    assert "CONTRADICTED_BY_OBSERVATIONAL_EVIDENCE" in codes


def test_contradiction_none_without_contradicting_evidence():
    status, codes = contradiction_resolver.resolve_contradiction([])
    assert status == "NONE"
    assert codes == []


# --- offline: confidence_resolver.py ---


def test_confidence_known_requires_direct_plus_analytical():
    bucket, _ = confidence_resolver.resolve_confidence(
        "STRONG", ["HIGH_CLASSIFIER_SUPPORT", "DIRECT_OBSERVATIONAL_SUPPORT"], "NONE",
        AnalyticalEvidence(stage5a_probability=0.7), StructuralEvidence(),
    )
    assert bucket == "KNOWN"


def test_confidence_likely_from_multiple_independent_meaningful():
    bucket, _ = confidence_resolver.resolve_confidence(
        "MEANINGFUL", ["OBSERVATIONAL_SUPPORT", "MULTIPLE_INDEPENDENT_SOURCES"], "NONE",
        AnalyticalEvidence(), StructuralEvidence(),
    )
    assert bucket == "LIKELY"


def test_confidence_possible_from_meaningful_alone():
    bucket, _ = confidence_resolver.resolve_confidence(
        "MEANINGFUL", ["HIGH_CLASSIFIER_SUPPORT"], "NONE", AnalyticalEvidence(), StructuralEvidence(),
    )
    assert bucket == "POSSIBLE"


def test_confidence_unknown_when_no_evidence():
    bucket, codes = confidence_resolver.resolve_confidence("NONE", [], "NONE", AnalyticalEvidence(), StructuralEvidence())
    assert bucket == "UNKNOWN"
    assert "NO_EVIDENCE" in codes


def test_confidence_borrowed_cap_downgrades_known_to_possible():
    bucket, codes = confidence_resolver.resolve_confidence(
        "STRONG", ["HIGH_CLASSIFIER_SUPPORT", "DIRECT_OBSERVATIONAL_SUPPORT"], "NONE",
        AnalyticalEvidence(stage5a_probability=0.7, stage5c_is_borrowed=True), StructuralEvidence(),
    )
    assert bucket == "POSSIBLE"
    assert "BORROWED_CAP_APPLIED" in codes


def test_confidence_borrowed_only_resolves_possible_not_unknown():
    bucket, _ = confidence_resolver.resolve_confidence(
        "NONE", ["BORROWED_ANALOG_SUPPORT"], "NONE", AnalyticalEvidence(stage5c_is_borrowed=True), StructuralEvidence(),
    )
    assert bucket == "POSSIBLE"


def test_confidence_conflict_overrides_high_stage5a_probability():
    # design doc §42: Stage 5a=0.85 but Stage 6 directly contradicts -> UNKNOWN,
    # never a preserved raw classifier probability.
    bucket, codes = confidence_resolver.resolve_confidence(
        "MEANINGFUL", ["HIGH_CLASSIFIER_SUPPORT"], "PRESENT",
        AnalyticalEvidence(stage5a_probability=0.85), StructuralEvidence(),
    )
    assert bucket == "UNKNOWN"
    assert "CONFLICTING_EVIDENCE" in codes


def test_confidence_strong_support_survives_contradiction():
    bucket, _ = confidence_resolver.resolve_confidence(
        "STRONG", ["HIGH_CLASSIFIER_SUPPORT", "DIRECT_OBSERVATIONAL_SUPPORT"], "PRESENT",
        AnalyticalEvidence(stage5a_probability=0.9), StructuralEvidence(),
    )
    assert bucket != "UNKNOWN"


# --- offline: ranker.py ---


def test_ranker_ties_share_rank_and_group():
    rh1 = _ranked_hypothesis(hypothesis_id="H_a", member_causes=["product_outage"], confidence_bucket="POSSIBLE")
    rh2 = _ranked_hypothesis(hypothesis_id="H_b", member_causes=["marketing_cut"], confidence_bucket="POSSIBLE")
    ordered = ranker.rank([rh1, rh2])
    assert ordered[0].rank == ordered[1].rank
    assert ordered[0].rank_group == ordered[1].rank_group


def test_ranker_orders_known_before_possible():
    rh1 = _ranked_hypothesis(hypothesis_id="H_a", confidence_bucket="POSSIBLE")
    rh2 = _ranked_hypothesis(hypothesis_id="H_b", member_causes=["marketing_cut"], confidence_bucket="KNOWN")
    ordered = ranker.rank([rh1, rh2])
    assert ordered[0].hypothesis_id == "H_b"
    assert ordered[0].rank == 1
    assert ordered[1].rank == 2


# --- offline: abstention.py ---


def test_abstention_empty_candidates():
    abstained, _ = abstention.determine_abstention([])
    assert abstained is True


def test_abstention_all_unknown():
    rh = _ranked_hypothesis(confidence_bucket="UNKNOWN", rank=1, rank_group="A")
    abstained, _ = abstention.determine_abstention([rh])
    assert abstained is True


def test_abstention_tied_possible_at_top():
    rh1 = _ranked_hypothesis(hypothesis_id="H_a", confidence_bucket="POSSIBLE", rank=1, rank_group="A")
    rh2 = _ranked_hypothesis(hypothesis_id="H_b", member_causes=["marketing_cut"], confidence_bucket="POSSIBLE",
                              rank=1, rank_group="A")
    abstained, codes = abstention.determine_abstention([rh1, rh2])
    assert abstained is True
    assert "UNRESOLVED_TIE_AT_TOP" in codes


def test_abstention_clean_known_does_not_abstain():
    rh = _ranked_hypothesis(confidence_bucket="KNOWN", rank=1, rank_group="A")
    abstained, _ = abstention.determine_abstention([rh])
    assert abstained is False


# --- offline: output_schema.py ---


def test_output_schema_rejects_joint_with_fabricated_split():
    rh = _ranked_hypothesis(
        hypothesis_id="H_JOINT_0", member_causes=["marketing_cut", "product_outage"], hypothesis_type="COMPOUND",
        identifiability="NON_IDENTIFIABLE_JOINT", analytical_evidence=AnalyticalEvidence(stage5a_probability=0.4),
    )
    try:
        output_schema.validate(Stage7Result(episode_id=1, cluster_id=None, hypotheses=[rh]))
        assert False, "expected AssertionError for a fabricated joint-member split"
    except AssertionError:
        pass


def test_output_schema_rejects_borrowed_above_cap():
    rh = _ranked_hypothesis(borrowed=True, confidence_bucket="KNOWN")
    try:
        output_schema.validate(Stage7Result(episode_id=1, cluster_id=None, hypotheses=[rh]))
        assert False, "expected AssertionError for a borrowed hypothesis exceeding POSSIBLE"
    except AssertionError:
        pass


def test_output_schema_accepts_valid_result():
    output_schema.validate(Stage7Result(episode_id=1, cluster_id=None, hypotheses=[_ranked_hypothesis()]))


# --- offline: full run_stage7() orchestration on synthetic fixtures ---


def test_run_stage7_end_to_end_synthetic():
    fr = _fingerprint(
        {"product_outage": 0.55, "marketing_cut": 0.30, "competitor_launch": 0.10, "inventory_shortage": 0.05},
        top_cause="product_outage",
    )
    stage5b_result = _stage5b([
        _contribution(
            "product_outage+marketing_cut", 6.0, 0.8,
            identifiability="NON_IDENTIFIABLE_JOINT", member_causes=["product_outage", "marketing_cut"],
        ),
        _contribution("unexplained", 1.0, 0.2, identifiability="IDENTIFIED"),
    ])
    evidence_result = _evidence_result([_evidence_item("negative", 0.5), _evidence_item("negative", 0.4)])

    result = run_stage7(1, "cluster_1_1_2", fr, stage5b_result, None, evidence_result)
    assert result.hypotheses, "expected at least one ranked hypothesis"
    assert all(rh.rank is not None for rh in result.hypotheses)
    joint = next(rh for rh in result.hypotheses if rh.hypothesis_type == "COMPOUND")
    assert joint.analytical_evidence.stage5a_probability is None  # never a fabricated joint split


def test_run_stage7_abstains_with_no_signal():
    fr = _fingerprint({"product_outage": 0.02, "marketing_cut": 0.01, "competitor_launch": 0.01, "inventory_shortage": 0.01})
    result = run_stage7(1, None, fr, None, None, _evidence_result([]))
    assert result.abstained is True
    assert result.hypotheses == []  # nothing cleared the candidate floor at all


# --- live: episode 15's real cluster_15_93_94 (one run, not one per module) ---


def test_live_stage7_episode_15():
    import stage4_bridge as s4b
    import stage5a_bridge as s5ab
    import stage5b_bridge as s5bb
    import stage6_bridge as s6b

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            stage3_results = s4b.run_stage3(cur, 15)
            assert stage3_results, "expected at least one Stage 3 cluster for episode 15"
            stage3_result = stage3_results[0]

            decomposition_result = s4b.run_stage4(cur, 15, stage3_result)
            reference = s5ab.load_reference()
            fingerprint_result, cold_start_result = s5ab.run_stage5a_and_5c(
                cur, 15, stage3_result, decomposition_result, reference
            )
            forked, reason = s5bb.should_fork(fingerprint_result.cause_scores, decomposition_result)
            print(f"Stage 5b fork decision: {forked} ({reason})")
            stage5b_result = (
                s5bb.run_stage5b(cur, 15, fingerprint_result, decomposition_result) if forked else None
            )
            evidence_result = s6b.run_stage6(cur, 15, decomposition_result, fingerprint_result)

            result = run_stage7(
                15, stage3_result.cluster_id, fingerprint_result, stage5b_result, cold_start_result, evidence_result,
            )
            print(
                f"\nlive run: episode 15, cluster {result.cluster_id}, "
                f"{len(result.hypotheses)} hypothesis(es), abstained={result.abstained}"
            )
            for rh in result.hypotheses:
                print(f"  rank {rh.rank} ({rh.rank_group}) [{rh.confidence_bucket}] {rh.member_causes}")

            assert result.hypotheses, "expected at least one hypothesis for a real investigated cluster"
            assert all(rh.rank is not None for rh in result.hypotheses)
    finally:
        conn.close()


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    for t in tests:
        t()
        print(f"  {t.__name__} OK")
    print("OK")
