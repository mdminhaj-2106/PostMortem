"""Stage 5a self-check -- offline invariant checks (no DB) + one live-DB check against
the real Neon dataset, mirroring Stage 2/3/4's test_stage2.py/test_stage3.py/test_stage4.py
split.

Run: .venv/bin/python test_stage5a.py
"""

import os

import psycopg2
from dotenv import load_dotenv

import classifier
import signatures
from models import EVENT_TYPES, FingerprintResult
from stage4_bridge import run_stage4
from stage3_bridge import run_stage3
from stage5a import run_stage5a

# --- offline: models.py ---


def test_fingerprint_result_rejects_bad_confidence():
    try:
        FingerprintResult(episode_id=1, cluster_id=None, confidence="SURE")
        assert False, "expected ValueError for an undeclared confidence"
    except ValueError:
        pass


def test_fingerprint_result_rejects_unknown_event_type():
    try:
        FingerprintResult(episode_id=1, cluster_id=None, cause_scores={"pricing_change": 1.0})
        assert False, "expected ValueError for a cause outside the real 4-class taxonomy"
    except ValueError:
        pass


def test_fingerprint_result_rejects_scores_not_summing_to_one():
    try:
        FingerprintResult(episode_id=1, cluster_id=None, cause_scores={"marketing_cut": 0.5})
        assert False, "expected ValueError for cause_scores not summing to 1.0"
    except ValueError:
        pass


def test_fingerprint_result_accepts_a_clean_ranked_dict():
    scores = {"inventory_shortage": 0.7, "marketing_cut": 0.1, "competitor_launch": 0.1, "product_outage": 0.1}
    r = FingerprintResult(episode_id=1, cluster_id="c1", cause_scores=scores, top_cause="inventory_shortage",
                           confidence="HIGH", signals_used=["product_concentration"])
    assert r.top_cause == "inventory_shortage"


# --- offline: signatures.py ---


class _FakeSlice:
    def __init__(self, kpi_name, dimension, slice_value, deviation_pct, observation_status="OBSERVED"):
        self.kpi_name = kpi_name
        self.dimension = dimension
        self.slice_value = slice_value
        self.deviation_pct = deviation_pct
        self.observation_status = observation_status


class _FakeDecomposition:
    def __init__(self, slices):
        self.slices = slices


def test_product_concentration_fires_on_one_dominant_slice():
    slices = [
        _FakeSlice("revenue", "product", "electronics", 0.9),
        _FakeSlice("revenue", "product", "toys", 0.03),
        _FakeSlice("revenue", "product", "books", 0.02),
        _FakeSlice("revenue", "product", "sports", 0.01),
    ]
    slice_value, score = signatures.product_concentration(_FakeDecomposition(slices))
    assert slice_value == "electronics"
    assert score > signatures.PRODUCT_CONCENTRATION_THRESHOLD


def test_product_concentration_returns_none_on_flat_slices():
    slices = [
        _FakeSlice("revenue", "product", "electronics", 0.24),
        _FakeSlice("revenue", "product", "toys", 0.26),
        _FakeSlice("revenue", "product", "books", 0.25),
        _FakeSlice("revenue", "product", "sports", 0.25),
    ]
    slice_value, score = signatures.product_concentration(_FakeDecomposition(slices))
    assert slice_value is None
    assert score == 0.0


def test_product_concentration_ignores_unmeasured_slices():
    slices = [
        _FakeSlice("revenue", "product", "electronics", 0.9),
        _FakeSlice("revenue", "product", "toys", None, observation_status="NO_DATA_IN_WINDOW"),
        _FakeSlice("revenue", "region", "SP", 0.9),  # wrong dimension, must be ignored
    ]
    slice_value, _score = signatures.product_concentration(_FakeDecomposition(slices))
    assert slice_value is None, "one real slice alone can't demonstrate concentration over a runner-up"


def test_dominant_kpi_shift_customers_first():
    customers = [(d, 100.0, -40.0) for d in range(10, 21)]  # -40% relative deviation
    orders = [(d, 1000.0, -5.0) for d in range(10, 21)]  # -0.5%, effectively flat
    revenue = [(d, 5000.0, -10.0) for d in range(10, 21)]
    assert signatures.dominant_kpi_shift(customers, orders, revenue, 10, 20) == "customers_first"


def test_dominant_kpi_shift_orders_first():
    customers = [(d, 100.0, 0.5) for d in range(10, 21)]  # flat
    orders = [(d, 1000.0, -300.0) for d in range(10, 21)]  # -30%
    revenue = [(d, 5000.0, -1500.0) for d in range(10, 21)]
    assert signatures.dominant_kpi_shift(customers, orders, revenue, 10, 20) == "orders_first"


def test_dominant_kpi_shift_none_when_everything_flat():
    customers = [(d, 100.0, 0.1) for d in range(10, 21)]
    orders = [(d, 1000.0, 0.5) for d in range(10, 21)]
    revenue = [(d, 5000.0, 1.0) for d in range(10, 21)]
    assert signatures.dominant_kpi_shift(customers, orders, revenue, 10, 20) is None


def test_onset_lean_step_vs_ramp():
    step_series = [(d, 1000.0, -300.0) for d in range(0, 21)]  # full magnitude from day 1
    ramp_series = [(d, 1000.0, -300.0 * min(1.0, (d - 10) / 10)) for d in range(0, 21)]
    assert signatures.onset_lean(step_series, 10) == "step"
    assert signatures.onset_lean(ramp_series, 10) == "ramp"


def test_onset_lean_none_when_data_missing():
    assert signatures.onset_lean([(10, 1000.0, -50.0)], 10) is None  # no day+7 point


# --- offline: classifier.py (table-driven, one row per signal combination) ---


def test_classify_product_signal_dominates():
    scores, confidence, top_cause, signals_used = classifier.classify(("electronics", 0.9), "orders_first", "step")
    assert top_cause == "inventory_shortage"
    assert confidence == "HIGH"
    assert abs(sum(scores.values()) - 1.0) < 1e-9
    assert signals_used == ["product_concentration"]


def test_classify_customers_first_alone_is_low_confidence():
    scores, confidence, top_cause, signals_used = classifier.classify((None, 0.0), "customers_first", None)
    assert top_cause == "competitor_launch"
    assert confidence == "LOW"
    assert "dominant_kpi_shift" in signals_used
    assert abs(sum(scores.values()) - 1.0) < 1e-9


def test_classify_orders_first_and_step_onset_agree():
    scores, confidence, top_cause, signals_used = classifier.classify((None, 0.0), "orders_first", "step")
    assert top_cause == "marketing_cut"
    assert confidence == "MEDIUM"
    assert set(signals_used) == {"dominant_kpi_shift", "onset_lean"}


def test_classify_orders_first_and_ramp_onset_agree():
    scores, confidence, top_cause, _ = classifier.classify((None, 0.0), "orders_first", "ramp")
    assert top_cause == "product_outage"
    assert confidence == "MEDIUM"


def test_classify_orders_first_without_onset_is_ambiguous():
    scores, confidence, top_cause, signals_used = classifier.classify((None, 0.0), "orders_first", None)
    assert confidence == "LOW"
    assert signals_used == ["dominant_kpi_shift"]
    # ambiguous between marketing_cut/product_outage -- must not fabricate a pick between them
    assert scores["marketing_cut"] == scores["product_outage"]


def test_classify_no_signals_is_honest_abstention():
    scores, confidence, top_cause, signals_used = classifier.classify((None, 0.0), None, None)
    assert confidence == "LOW"
    assert signals_used == []
    assert abs(sum(scores.values()) - 1.0) < 1e-9
    assert all(s > 0 for s in scores.values()), "every real cause stays plausible, never zeroed by silence"


def test_classify_never_uses_geo_or_segment_entropy():
    """Regression guard for the plan's ceiling analysis: no event type ever touches
    `region`, and affected_segment is orthogonal to cause -- these must never become
    inputs to classify()."""
    import inspect

    sig = inspect.signature(classifier.classify)
    names = set(sig.parameters)
    assert "geo_spread_entropy" not in names and "segment_spread_entropy" not in names


# --- live DB ---


def test_run_stage5a_detects_inventory_shortage_on_a_real_episode(cur):
    """Episode 15: a real inventory_shortage event (day 78-109, severe, step onset,
    product_id 42) that Stage 3 actually flags as a cluster (cluster_15_93_94,
    orders_count/units_sold, day 93-94) -- found by live search, verified against
    injected_events once, offline, to pick this fixture; run_stage5a itself never queries
    it. Episode 15 genuinely has only 2 distinct product categories (auto, bed_bath_table)
    -- also confirmed live -- so `auto`'s share of total |deviation_pct| clears the
    concentration threshold cleanly (0.76) once this specific window isolates the
    shortage's effect from the episode's earlier, unrelated product_outage. (Most real
    inventory_shortage windows never clear Stage 2/3's company-wide significance bar at
    all -- a single product's weight cut is too small a fraction of total revenue -- so
    this episode/window had to be found, not assumed.)"""
    stage3_results = run_stage3(cur, 15)
    target = next(r for r in stage3_results if r.cluster_id == "cluster_15_93_94")
    decomposition_result = run_stage4(cur, 15, target)
    result = run_stage5a(cur, 15, target, decomposition_result)

    assert result.top_cause == "inventory_shortage"
    assert result.confidence == "HIGH"
    assert abs(sum(result.cause_scores.values()) - 1.0) < 1e-9


if __name__ == "__main__":
    test_fingerprint_result_rejects_bad_confidence()
    test_fingerprint_result_rejects_unknown_event_type()
    test_fingerprint_result_rejects_scores_not_summing_to_one()
    test_fingerprint_result_accepts_a_clean_ranked_dict()

    test_product_concentration_fires_on_one_dominant_slice()
    test_product_concentration_returns_none_on_flat_slices()
    test_product_concentration_ignores_unmeasured_slices()
    test_dominant_kpi_shift_customers_first()
    test_dominant_kpi_shift_orders_first()
    test_dominant_kpi_shift_none_when_everything_flat()
    test_onset_lean_step_vs_ramp()
    test_onset_lean_none_when_data_missing()

    test_classify_product_signal_dominates()
    test_classify_customers_first_alone_is_low_confidence()
    test_classify_orders_first_and_step_onset_agree()
    test_classify_orders_first_and_ramp_onset_agree()
    test_classify_orders_first_without_onset_is_ambiguous()
    test_classify_no_signals_is_honest_abstention()
    test_classify_never_uses_geo_or_segment_entropy()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            test_run_stage5a_detects_inventory_shortage_on_a_real_episode(cur)
    finally:
        conn.close()
    print("OK")
