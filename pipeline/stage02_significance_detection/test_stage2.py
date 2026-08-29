"""Stage 2 self-check -- offline invariant checks (no DB) + live-DB checks against the
real Neon dataset, mirroring Stage 1's test_reconcile.py split.

Run: .venv/bin/python test_stage2.py
"""

import os
from dataclasses import dataclass

import psycopg2
from dotenv import load_dotenv

import business_importance
import candidate_selection
import classification
import eligibility
import ingest
import relevance
import unusualness
from baseline import compute_residuals
from stage2 import run_stage2


@dataclass
class _FakeRV:
    value: float
    imputation_flag: str = "untouched"


# --- offline ---

def test_eligibility_gate():
    clean_long = [(d, _FakeRV(100.0)) for d in range(40)]
    clean_short = [(d, _FakeRV(100.0)) for d in range(15)]
    half_imputed = [(d, _FakeRV(100.0, "untouched" if d % 2 == 0 else "partially_imputed")) for d in range(40)]
    empty = [(d, None) for d in range(40)]

    assert eligibility.assess_eligibility(clean_long) == eligibility.ELIGIBLE
    assert eligibility.assess_eligibility(clean_short) == eligibility.LIMITED_HISTORY
    assert eligibility.assess_eligibility(half_imputed) == eligibility.LOW_CONFIDENCE
    assert eligibility.assess_eligibility(empty) == eligibility.INSUFFICIENT_DATA


def test_baseline_flags_a_spike():
    timeline = [(d, _FakeRV(100.0)) for d in range(20)]
    timeline[15] = (15, _FakeRV(500.0))
    res = compute_residuals(timeline, window=14, min_window_for_estimate=5)
    res_by_day = {d: r for d, _e, r in res}
    assert res_by_day[15] == 400.0
    assert all(res_by_day[d] == 0.0 for d in res_by_day if d != 15)


def test_unusualness_is_causal_and_flags_the_spike():
    timeline = [(d, _FakeRV(100.0)) for d in range(20)]
    timeline[15] = (15, _FakeRV(500.0))
    res_full = compute_residuals(timeline, window=14, min_window_for_estimate=5)
    res_prefix = compute_residuals(timeline[:16], window=14, min_window_for_estimate=5)
    scores_full = dict(unusualness.score_unusualness(res_full))
    scores_prefix = dict(unusualness.score_unusualness(res_prefix))
    assert scores_full[15] == scores_prefix[15], "a day's score must not depend on future data"
    assert scores_full[15] == 1.0


def test_candidate_selection_rate_proportional():
    import random
    rng = random.Random(42)
    scores = [(d, rng.random()) for d in range(1000)]
    for rate in (0.1, 0.2, 0.5):
        cands = candidate_selection.select_candidates(scores, target_candidate_rate=rate)
        assert abs(len(cands) / 1000 - rate) < 0.02


def test_business_importance_declared_evidence():
    level, ev = business_importance.assess_importance("revenue", [])
    assert level == "CRITICAL"
    assert any(e["type"] == "KNOWN_BUSINESS_CRITICALITY" for e in ev)

    level, ev = business_importance.assess_importance("active_customers_purchased_30d", ["revenue"])
    assert level == "HIGH"
    assert any(e["type"] == "KNOWN_RELATIONSHIP" and e["target"] == "revenue" for e in ev)


def test_relevance_matrix_rows():
    # design doc §14, one case per row
    cases = [
        (0.92, "HIGH", True, "HIGH", 1),          # High unusualness + High importance -> High
        (0.99, "MEDIUM", True, "HIGH", 2),        # Very high + Medium + strong connection -> High
        (0.99, "LOW", False, "LOW", 4),           # Very high + Low + no context -> Low
        (0.75, "CRITICAL", True, "MEDIUM", 3),    # Medium + Critical -> Medium (or High)
        (0.5, "CRITICAL", True, "NOT_RELEVANT", None),  # Low unusualness -> Not relevant
    ]
    for score, importance, ctx, expected_level, expected_tier in cases:
        level, tier = relevance.resolve_relevance(score, importance, ctx)
        assert (level, tier) == (expected_level, expected_tier), (score, importance, ctx, level, tier)


def test_classification_trajectory():
    seq = [False, False, True, True, True, True, True, True, True, True, True, True, False]
    days = list(range(len(seq)))
    result = classification.classify_trajectory(days, seq)
    states = [s for _, s, _ in result]
    assert states[0:2] == ["NORMAL", "NORMAL"]
    assert states[2:4] == ["EMERGING", "EMERGING"]
    assert states[4] == "SIGNIFICANT"
    assert states[11] == "STRUCTURAL"
    assert states[12] == "NORMAL"


# --- live DB ---

def test_timeline_cache_reuses_days_without_refetching(cur):
    """Audit finding F13. A repeat request must not re-hit the DB, and a partially
    overlapping range must fetch only the new days -- the whole point of keying the
    cache per day rather than per (episode, kpi, day_range)."""
    ingest.clear_cache()
    days = list(range(10, 25))

    first = ingest.load_kpi_timeline(cur, 1, "revenue", days)
    after_first = len(ingest._reconciled_day_cache)
    assert after_first == len(days), "every requested day should be cached once"

    second = ingest.load_kpi_timeline(cur, 1, "revenue", days)
    assert len(ingest._reconciled_day_cache) == after_first, "repeat request refetched"
    assert ([(d, rv.value if rv else None) for d, rv in first]
            == [(d, rv.value if rv else None) for d, rv in second]), "cache changed the values"

    ingest.load_kpi_timeline(cur, 1, "revenue", range(20, 30))  # 20-24 overlap, 25-29 new
    assert len(ingest._reconciled_day_cache) == after_first + 5, "overlap was refetched"

    # a different KPI must not collide with revenue's cached days
    ingest.load_kpi_timeline(cur, 1, "active_customers_purchased_30d", days)
    assert len(ingest._reconciled_day_cache) == after_first + 5 + len(days)
    ingest.clear_cache()


def test_ingest_and_run_end_to_end(cur):
    for kpi in ingest.KPI_NAMES:
        results = run_stage2(cur, 1, kpi, day_range=range(0, 30))
        assert len(results) == 30
        assert all(r.analysis_status in ("ANALYZED", "INSUFFICIENT_DATA") for r in results)


def test_scoring_reacts_to_a_real_injected_event(cur):
    """The only place in Stage 2's codebase that touches injected_events -- offline
    scoring only (CONSTITUTION.md non-negotiable #5), never imported by stage2.py."""
    cur.execute(
        "SELECT episode_id, start_day_offset FROM injected_events "
        "WHERE event_type IN ('marketing_cut','product_outage') AND severity IN ('moderate','severe') "
        "AND onset_type = 'step' ORDER BY episode_id"
    )
    candidates = cur.fetchall()
    assert candidates, "expected at least one qualifying injected event in the live dataset"

    reacted = False
    for episode_id, start_day_offset in candidates:
        results = run_stage2(cur, episode_id, "revenue")
        window = [r for r in results if start_day_offset <= r.day_offset <= start_day_offset + 15]
        quiet_before = [r for r in results if 0 <= r.day_offset < max(0, start_day_offset - 10)]

        hit = any(r.classification_state in ("SIGNIFICANT", "STRUCTURAL") for r in window)
        if not hit:
            continue
        if quiet_before:
            normal_fraction = sum(1 for r in quiet_before if r.classification_state == "NORMAL") / len(quiet_before)
            if normal_fraction < 0.7:
                continue  # this episode's "quiet" stretch isn't actually quiet -- try another
        reacted = True
        break

    assert reacted, "Stage 2 should reach SIGNIFICANT+ within 15 days of a real event on at least one episode"


if __name__ == "__main__":
    test_eligibility_gate()
    test_baseline_flags_a_spike()
    test_unusualness_is_causal_and_flags_the_spike()
    test_candidate_selection_rate_proportional()
    test_business_importance_declared_evidence()
    test_relevance_matrix_rows()
    test_classification_trajectory()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            test_timeline_cache_reuses_days_without_refetching(cur)
            test_ingest_and_run_end_to_end(cur)
            test_scoring_reacts_to_a_real_injected_event(cur)
    finally:
        conn.close()
    print("OK")
