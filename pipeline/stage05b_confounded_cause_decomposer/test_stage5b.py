"""Stage 5b self-check -- offline invariant checks (no DB) + one live-DB end-to-end run.
Run: .venv/bin/python test_stage5b.py
"""

import os

import numpy as np
import psycopg2
from dotenv import load_dotenv

import attribution
import identifiability
import output_schema
import router
import shape_features
import simulator_bridge
from cause_config import CAUSE_FAMILIES
from models import CauseContribution, ConfoundedAttributionResult

# --- offline: cause_config / models ---


def test_cause_families_match_generator_event_types():
    assert set(CAUSE_FAMILIES) == set(simulator_bridge._generate.EVENT_TYPES)


def test_cause_contribution_rejects_negative_contribution():
    try:
        CauseContribution(cause="marketing_cut", contribution=-1.0, share=0.0,
                           basis_provenance="LEARNED", basis_sample_count=5, identifiability="IDENTIFIED")
        assert False, "expected ValueError for a negative contribution"
    except ValueError:
        pass


def test_cause_contribution_requires_members_for_joint():
    try:
        CauseContribution(cause="a+b", contribution=1.0, share=1.0, basis_provenance="LEARNED",
                           basis_sample_count=5, identifiability="NON_IDENTIFIABLE_JOINT", member_causes=None)
        assert False, "expected ValueError for a joint component with no member_causes"
    except ValueError:
        pass


def test_confounded_result_requires_unexplained():
    named = CauseContribution(cause="marketing_cut", contribution=1.0, share=1.0, basis_provenance="LEARNED",
                               basis_sample_count=5, identifiability="IDENTIFIED")
    try:
        ConfoundedAttributionResult(episode_id=1, cluster_id=None, kpi_name="revenue",
                                     window_start_day_offset=0, window_end_day_offset=10,
                                     observed_deviation=100.0, contributions=[named])
        assert False, "expected ValueError when unexplained is missing"
    except ValueError:
        pass


# --- offline: shape_features ---


def test_shape_vector_length_is_pure_function_of_L_K():
    empty = shape_features.build_shape_vector({}, 10, 20)
    assert len(empty) == shape_features.VECTOR_LENGTH


def test_region_concentration_profile_isolates_one_dominant_region():
    matrix = {
        ("region", "SP"): [(d, 100.0, 50.0) for d in range(0, 21)],
        ("region", "RJ"): [(d, 100.0, 1.0) for d in range(0, 21)],
        ("region", "MG"): [(d, 100.0, 1.0) for d in range(0, 21)],
    }
    profile = shape_features._concentration_profile(matrix, "region", 10, 20, 3)
    assert profile[0] > 0.9


# --- offline: identifiability ---


def _unit(vec):
    arr = np.array(vec, dtype=float)
    return arr / np.linalg.norm(arr)


def test_identifiability_merges_near_identical_bases():
    bases = {"a": _unit([1, 0, 0]), "b": _unit([1, 0.01, 0])}
    groups, verdict = identifiability.assess(["a", "b"], bases)
    assert verdict == "FULLY_MERGED"
    assert sorted(groups[0]) == ["a", "b"]


def test_identifiability_keeps_orthogonal_bases_separate():
    bases = {"a": _unit([1, 0, 0]), "b": _unit([0, 1, 0])}
    groups, verdict = identifiability.assess(["a", "b"], bases)
    assert verdict == "CLEAN_SPLIT"
    assert sorted(len(g) for g in groups) == [1, 1]


def test_identifiability_declared_pair_merges_within_lag():
    bases = {"product_outage": _unit([1, 0, 0]), "marketing_cut": _unit([0, 1, 0])}
    onsets = {"product_outage": 10, "marketing_cut": 15}  # lag 5, inside (3, 10)
    groups, verdict = identifiability.assess(["product_outage", "marketing_cut"], bases, onsets)
    assert verdict == "FULLY_MERGED"


def test_identifiability_declared_pair_does_not_merge_outside_lag():
    bases = {"product_outage": _unit([1, 0, 0]), "marketing_cut": _unit([0, 1, 0])}
    onsets = {"product_outage": 10, "marketing_cut": 60}  # lag 50, outside (3, 10)
    groups, verdict = identifiability.assess(["product_outage", "marketing_cut"], bases, onsets)
    assert verdict == "CLEAN_SPLIT"


# --- offline: attribution ---


def test_attribution_recovers_a_known_mixture():
    rng = np.random.default_rng(0)
    b_a, b_b = _unit(rng.normal(size=20)), _unit(rng.normal(size=20))
    x_obs = _unit(0.7 * b_a + 0.3 * b_b)
    contributions, unexplained, fit_quality = attribution.fit(x_obs, {"a": b_a, "b": b_b}, magnitude=100.0)
    total = sum(contributions.values())
    assert abs(contributions["a"] / total - 0.7) < 0.05
    assert abs(contributions["b"] / total - 0.3) < 0.05
    assert unexplained < 5.0
    assert fit_quality > 0.9


def test_attribution_flags_high_unexplained_for_an_out_of_set_basis():
    rng = np.random.default_rng(1)
    b_true, b_a, b_b = _unit(rng.normal(size=20)), _unit(rng.normal(size=20)), _unit(rng.normal(size=20))
    contributions, unexplained, fit_quality = attribution.fit(b_true, {"a": b_a, "b": b_b}, magnitude=100.0)
    assert unexplained > 50.0, "an observation built from an out-of-candidate-set basis should not be force-fit"
    assert fit_quality < 0.5


# --- offline: router ---


class _FakeSlice:
    def __init__(self, dimension, deviation_pct):
        self.dimension = dimension
        self.deviation_pct = deviation_pct
        self.observation_status = "OBSERVED"


class _FakeDecomposition:
    def __init__(self, slices):
        self.slices = slices


def test_router_does_not_fork_on_a_clear_margin():
    should, reason = router.should_fork({"marketing_cut": 0.8, "product_outage": 0.1,
                                          "competitor_launch": 0.05, "inventory_shortage": 0.05},
                                         _FakeDecomposition([]))
    assert should is False


def test_router_forks_on_narrow_margin_plus_multi_dimension_concentration():
    scores = {"product_outage": 0.4, "marketing_cut": 0.35, "competitor_launch": 0.15, "inventory_shortage": 0.1}
    slices = [_FakeSlice("region", 0.5), _FakeSlice("product", 0.6)]
    should, reason = router.should_fork(scores, _FakeDecomposition(slices))
    assert should is True
    assert "dimensions concentrating" in reason


def test_router_does_not_fork_on_narrow_margin_with_no_evidence():
    scores = {"marketing_cut": 0.3, "competitor_launch": 0.28, "product_outage": 0.22, "inventory_shortage": 0.2}
    should, reason = router.should_fork(scores, _FakeDecomposition([]))
    assert should is False


# --- offline: output_schema ---


def test_output_schema_rejects_free_text_cause():
    good = CauseContribution(cause=" made_up_cause", contribution=1.0, share=1.0, basis_provenance="LEARNED",
                              basis_sample_count=5, identifiability="IDENTIFIED")
    unexplained = CauseContribution(cause="unexplained", contribution=0.0, share=0.0, basis_provenance="RESIDUAL",
                                     basis_sample_count=None, identifiability="IDENTIFIED")
    result = ConfoundedAttributionResult(episode_id=1, cluster_id=None, kpi_name="revenue",
                                          window_start_day_offset=0, window_end_day_offset=10,
                                          observed_deviation=1.0, contributions=[good, unexplained])
    try:
        output_schema.validate(result)
        assert False, "expected AssertionError for a free-text cause"
    except AssertionError:
        pass


def test_output_schema_rejects_joint_with_separate_member_entry():
    joint = CauseContribution(cause="marketing_cut+product_outage", contribution=1.0, share=0.5,
                               basis_provenance="LEARNED", basis_sample_count=5,
                               identifiability="NON_IDENTIFIABLE_JOINT",
                               member_causes=["marketing_cut", "product_outage"])
    member = CauseContribution(cause="marketing_cut", contribution=0.5, share=0.5, basis_provenance="LEARNED",
                                basis_sample_count=5, identifiability="IDENTIFIED")
    unexplained = CauseContribution(cause="unexplained", contribution=0.0, share=0.0, basis_provenance="RESIDUAL",
                                     basis_sample_count=None, identifiability="IDENTIFIED")
    result = ConfoundedAttributionResult(episode_id=1, cluster_id=None, kpi_name="revenue",
                                          window_start_day_offset=0, window_end_day_offset=10,
                                          observed_deviation=1.0, contributions=[joint, member, unexplained])
    try:
        output_schema.validate(result)
        assert False, "expected AssertionError for a joint + separate-member conflict"
    except AssertionError:
        pass


# --- live DB: one end-to-end run ---


def test_run_stage5b_end_to_end_on_a_real_episode(cur):
    """Reuses episode 15 (already the live fixture picked for Stage 5a's own test) --
    just proves the whole wiring runs and validates against the output contract, not a
    claim about this specific episode's real confounded-pair status."""
    import pipeline_bridge
    import stage5a_bridge
    from stage5b import run_stage5b

    stage3_results = pipeline_bridge.run_stage3(cur, 15)
    stage3_result = next(r for r in stage3_results if r.cluster_id == "cluster_15_93_94")
    decomposition_result = pipeline_bridge.run_stage4(cur, 15, stage3_result)
    stage5a_result = stage5a_bridge.run_stage5a(cur, 15, stage3_result, decomposition_result)

    result = run_stage5b(cur, 15, stage5a_result, decomposition_result)
    output_schema.validate(result)
    assert any(c.cause == "unexplained" for c in result.contributions)
    assert abs(sum(c.share for c in result.contributions) - 1.0) < 1e-6


if __name__ == "__main__":
    test_cause_families_match_generator_event_types()
    test_cause_contribution_rejects_negative_contribution()
    test_cause_contribution_requires_members_for_joint()
    test_confounded_result_requires_unexplained()

    test_shape_vector_length_is_pure_function_of_L_K()
    test_region_concentration_profile_isolates_one_dominant_region()

    test_identifiability_merges_near_identical_bases()
    test_identifiability_keeps_orthogonal_bases_separate()
    test_identifiability_declared_pair_merges_within_lag()
    test_identifiability_declared_pair_does_not_merge_outside_lag()

    test_attribution_recovers_a_known_mixture()
    test_attribution_flags_high_unexplained_for_an_out_of_set_basis()

    test_router_does_not_fork_on_a_clear_margin()
    test_router_forks_on_narrow_margin_plus_multi_dimension_concentration()
    test_router_does_not_fork_on_narrow_margin_with_no_evidence()

    test_output_schema_rejects_free_text_cause()
    test_output_schema_rejects_joint_with_separate_member_entry()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            test_run_stage5b_end_to_end_on_a_real_episode(cur)
    finally:
        conn.close()
    print("OK")
