"""Stage 6 self-check -- offline invariant checks (no DB) + one live-DB end-to-end
run against the seeded demo corpus, mirroring Stage 4/5a/5c's
test_stage4.py/test_stage5a.py/test_stage5c.py split.

Run: .venv/bin/python test_stage6.py
"""

import os

import psycopg2
from dotenv import load_dotenv

import embedding_index
import entity_scope_filter
import output_schema
import temporal_tagger
from models import EvidenceItem, EvidenceResult

DEMO_EPISODE_ID = 15
DEMO_CLUSTER_ID = "cluster_15_93_94"


class _FakeSlice:
    def __init__(self, kpi_name, dimension, slice_value, deviation_pct,
                 eligibility="ELIGIBLE", observation_status="OBSERVED"):
        self.kpi_name = kpi_name
        self.dimension = dimension
        self.slice_value = slice_value
        self.deviation_pct = deviation_pct
        self.eligibility = eligibility
        self.observation_status = observation_status
        self.window_start_day_offset = 93
        self.window_end_day_offset = 94


class _FakeDecomposition:
    def __init__(self, slices):
        self.slices = slices


# --- offline: models.py / output_schema.py ---


def test_evidence_item_rejects_unknown_temporal_tag():
    try:
        EvidenceItem(
            source_type="support_ticket", text_snippet="x", day_offset=1, temporal_tag="SOMETIME",
            entity_link_confidence="HIGH", segment_scope=None, region_scope=None, product_scope=None,
            relevance_score=0.5, sentiment="neutral",
        )
        assert False, "expected ValueError for an undeclared temporal_tag"
    except ValueError:
        pass


def test_evidence_item_rejects_empty_text():
    try:
        EvidenceItem(
            source_type="support_ticket", text_snippet="", day_offset=1, temporal_tag="BEFORE",
            entity_link_confidence="HIGH", segment_scope=None, region_scope=None, product_scope=None,
            relevance_score=0.5, sentiment="neutral",
        )
        assert False, "expected ValueError for empty text_snippet"
    except ValueError:
        pass


def test_output_schema_accepts_clean_result():
    item = EvidenceItem(
        source_type="support_ticket", text_snippet="It crashed again.", day_offset=80, temporal_tag="BEFORE",
        entity_link_confidence="HIGH", segment_scope="VIP", region_scope="SP", product_scope=None,
        relevance_score=0.42, sentiment="negative",
    )
    output_schema.validate(EvidenceResult(episode_id=1, cluster_id=None, evidence=[item]))


def test_output_schema_rejects_relevance_score_out_of_range():
    item = EvidenceItem(
        source_type="support_ticket", text_snippet="It crashed again.", day_offset=80, temporal_tag="BEFORE",
        entity_link_confidence="HIGH", segment_scope=None, region_scope=None, product_scope=None,
        relevance_score=1.5, sentiment="negative",
    )
    try:
        output_schema.validate(EvidenceResult(episode_id=1, cluster_id=None, evidence=[item]))
        assert False, "expected an assertion error for an out-of-range relevance_score"
    except AssertionError:
        pass


# --- offline: entity_scope_filter.py ---


def test_flagged_facets_fires_on_one_dominant_product_slice():
    slices = [
        _FakeSlice("orders_count", "product", "auto", -0.2),
        _FakeSlice("orders_count", "product", "bed_bath_table", -0.08),
    ]
    facets = entity_scope_filter.flagged_facets(_FakeDecomposition(slices))
    assert facets == [("product", "auto")]


def test_flagged_facets_returns_empty_when_nothing_concentrates():
    slices = [
        _FakeSlice("revenue", "segment", "New", 0.8),
        _FakeSlice("revenue", "segment", "Returning", 0.6),
        _FakeSlice("revenue", "segment", "VIP", 0.6),
    ]
    assert entity_scope_filter.flagged_facets(_FakeDecomposition(slices)) == []


def test_flagged_facets_excludes_thin_slices():
    slices = [
        _FakeSlice("orders_count", "product", "auto", -0.2),
        _FakeSlice("orders_count", "product", "bed_bath_table", -0.08, eligibility="LIMITED_HISTORY"),
    ]
    # only one non-thin slice_value -- can't compute a real concentration share
    assert entity_scope_filter.flagged_facets(_FakeDecomposition(slices)) == []


def test_filter_by_matches_keeps_matching_excludes_wrong_scope():
    facets = [("product", "auto")]
    matches_by_facet = {("product", "auto"): {1, 2}}
    tickets = [
        (10, 80, 1, "auto stuff is out of stock"),   # matches
        (11, 80, 3, "unrelated wrong-scope customer"),  # excluded
    ]
    kept = entity_scope_filter._filter_by_matches(facets, matches_by_facet, tickets)
    assert [t[0] for t, _dims in kept] == [10]


# --- offline: temporal_tagger.py ---


def test_temporal_tagger_before_during_after_and_same_day_boundary():
    assert temporal_tagger.tag(5, 10, 20) == "BEFORE"
    assert temporal_tagger.tag(10, 10, 20) == "DURING"  # same-day boundary -- declared DURING, not BEFORE
    assert temporal_tagger.tag(15, 10, 20) == "DURING"
    assert temporal_tagger.tag(21, 10, 20) == "AFTER"


def test_temporal_tagger_excludes_missing_timestamp():
    assert temporal_tagger.tag(None, 10, 20) is None


# --- offline: embedding_index.py (real MiniLM model, no DB) ---


def test_embedding_index_ranks_real_evidence_above_decoy():
    survivors = [
        ((1, 80, 1, "Auto parts I need are all backordered indefinitely, no ETA given by support."),
         ["product"], "BEFORE"),
        ((2, 80, 2, "Quick question about my last statement, the total looks off."),
         ["product"], "BEFORE"),
    ]
    query = embedding_index.build_query("inventory_shortage")
    ranked = embedding_index.rank(survivors, query)
    assert ranked, "expected the real-evidence item to clear the relevance threshold"
    assert ranked[0][0][0] == 1, "the real inventory complaint should outrank the unrelated billing question"


# --- live DB ---


def test_run_stage6_narrows_the_seeded_corpus_to_real_evidence(cur):
    """Episode 15, cluster_15_93_94 (window day 93-94) -- the same live-verified
    inventory_shortage fixture Stage 5a's own test suite already found
    (test_run_stage5a_detects_inventory_shortage_on_a_real_episode): `auto` (product
    42) clears the product-concentration bar cleanly, no segment/region facet fires
    (this event's affected_segment is unset -- verified live, see
    pipeline/simulator/layer1_ground_truth/seed_stage6_evidence.py's module
    docstring). Requires seed_stage6_evidence.py --episode-id 15 to have been run
    first.
    """
    import stage4_bridge
    import stage5a_bridge
    from run_stage6 import run_stage6

    stage3_results = stage4_bridge.run_stage3(cur, DEMO_EPISODE_ID)
    stage3_result = next(r for r in stage3_results if r.cluster_id == DEMO_CLUSTER_ID)
    decomposition_result = stage4_bridge.run_stage4(cur, DEMO_EPISODE_ID, stage3_result)

    reference = stage5a_bridge.load_reference()
    fingerprint_result, _cold_start_result = stage5a_bridge.run_stage5a_and_5c(
        cur, DEMO_EPISODE_ID, stage3_result, decomposition_result, reference
    )
    assert fingerprint_result.top_cause == "inventory_shortage"

    cur.execute(
        "SELECT count(*) FROM support_tickets WHERE episode_id=%s AND text IS NOT NULL", (DEMO_EPISODE_ID,)
    )
    total_seeded = cur.fetchone()[0]
    assert total_seeded >= 150, "expected the seed_stage6_evidence.py corpus to already be loaded"

    result = run_stage6(cur, DEMO_EPISODE_ID, decomposition_result, fingerprint_result)

    assert 1 <= len(result.evidence) <= embedding_index.MAX_EVIDENCE_ITEMS
    assert len(result.evidence) < total_seeded, "the funnel must narrow, not pass the corpus through untouched"
    for item in result.evidence:
        assert item.entity_link_confidence == "HIGH"
        assert item.relevance_score >= embedding_index.RELEVANCE_THRESHOLD
        # the seeded wrong-product decoys never bought 'auto' -- if any leaked through,
        # Filter 1 (entity_scope_filter) failed, not Filter 3.
        assert "bath towel" not in item.text_snippet and "shower curtain" not in item.text_snippet \
            and "bedding set" not in item.text_snippet


if __name__ == "__main__":
    test_evidence_item_rejects_unknown_temporal_tag()
    test_evidence_item_rejects_empty_text()
    test_output_schema_accepts_clean_result()
    test_output_schema_rejects_relevance_score_out_of_range()

    test_flagged_facets_fires_on_one_dominant_product_slice()
    test_flagged_facets_returns_empty_when_nothing_concentrates()
    test_flagged_facets_excludes_thin_slices()
    test_filter_by_matches_keeps_matching_excludes_wrong_scope()

    test_temporal_tagger_before_during_after_and_same_day_boundary()
    test_temporal_tagger_excludes_missing_timestamp()

    test_embedding_index_ranks_real_evidence_above_decoy()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            test_run_stage6_narrows_the_seeded_corpus_to_real_evidence(cur)
    finally:
        conn.close()
    print("OK")
