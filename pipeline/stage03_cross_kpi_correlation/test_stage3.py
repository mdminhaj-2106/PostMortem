"""Stage 3 self-check -- offline invariant checks (no DB) + live-DB checks against
the real Neon dataset, mirroring Stage 2's test_stage2.py split.

Run: .venv/bin/python test_stage3.py
"""

import os
from dataclasses import dataclass

import psycopg2
from dotenv import load_dotenv

import grouping
import priority
import stage2_bridge
from models import StageThreeResult
from stage3 import run_stage3

_DAG_ENTRY = {"target": "revenue", "relationship": "UPSTREAM_DRIVER",
              "expected_lag_days": (0, 3), "expected_direction": "SAME_SIGN"}


@dataclass
class _FakeS2Result:
    day_offset: int
    classification_state: str
    confidence: str = "HIGH"


def _make_results(flagged_days, all_days):
    return [_FakeS2Result(d, "SIGNIFICANT" if d in flagged_days else "NORMAL") for d in all_days]


# --- offline ---

def test_find_flagged_windows():
    results = _make_results({3, 4, 5, 10}, range(15))
    assert grouping.find_flagged_windows(results) == [(3, 5), (10, 10)]


def test_attempt_cluster_adjacent_and_correlated():
    residuals_a = [(d, 10.0) for d in range(3, 6)]
    residuals_b = [(d, 100.0) for d in range(4, 7)]
    window, reason = grouping.attempt_cluster([(3, 5)], residuals_a, [(4, 6)], residuals_b, _DAG_ENTRY)
    assert window == (3, 6)
    assert reason is None


def test_attempt_cluster_wrong_direction():
    residuals_a = [(d, 10.0) for d in range(3, 6)]
    residuals_b = [(d, -100.0) for d in range(4, 7)]
    window, reason = grouping.attempt_cluster([(3, 5)], residuals_a, [(4, 6)], residuals_b, _DAG_ENTRY)
    assert window is None
    assert reason == "SEPARATE_NO_CORRELATION"


def test_attempt_cluster_out_of_lag():
    residuals_a = [(d, 10.0) for d in range(3, 6)]
    residuals_b = [(d, 100.0) for d in range(20, 23)]
    window, reason = grouping.attempt_cluster([(3, 5)], residuals_a, [(20, 22)], residuals_b, _DAG_ENTRY)
    assert window is None
    assert reason == "SEPARATE_NO_ADJACENT_KPI"


def test_attempt_cluster_no_second_kpi():
    residuals_a = [(d, 10.0) for d in range(3, 6)]
    window, reason = grouping.attempt_cluster([(3, 5)], residuals_a, [], [], _DAG_ENTRY)
    assert window is None
    assert reason == "SEPARATE_NO_ADJACENT_KPI"


def test_priority_case1_observed():
    residuals = {"revenue": [(d, 50.0) for d in range(3, 6)], "active_customers_purchased_30d": []}
    score, basis = priority.score_priority(["active_customers_purchased_30d", "revenue"], 3, 5, residuals)
    assert basis == "OBSERVED"
    assert score == 150.0


def test_priority_case2_unavailable():
    residuals = {"active_customers_purchased_30d": [(d, 5.0) for d in range(3, 6)]}
    score, basis = priority.score_priority(["active_customers_purchased_30d"], 3, 5, residuals)
    assert score is None
    assert basis == "PROJECTED_UNAVAILABLE"


def test_confidence_gate_ranks_without_discarding():
    low = StageThreeResult(episode_id=1, cluster_id="a", kpi_names=["revenue"], priority_score=999.0,
                            priority_basis="OBSERVED", confidence="LOW", grouping_basis="SINGLE_KPI")
    high = StageThreeResult(episode_id=1, cluster_id="b", kpi_names=["revenue"], priority_score=50.0,
                             priority_basis="OBSERVED", confidence="HIGH", grouping_basis="SINGLE_KPI")
    ranked = priority.rank([low, high])
    assert ranked == [high], "LOW confidence must be excluded from ranking"
    assert priority.gate_by_confidence("MEDIUM") is True
    assert priority.gate_by_confidence("LOW") is False


def test_rank_puts_biggest_dollar_impact_first_regardless_of_sign():
    """Audit finding F1: priority_score is a SIGNED residual sum, so ranking on the
    raw value buried the worst incidents at the bottom. A -$500k collapse must
    outrank a +$900 blip."""
    collapse = StageThreeResult(episode_id=1, cluster_id="collapse", kpi_names=["revenue"],
                                 priority_score=-500000.0, priority_basis="OBSERVED",
                                 confidence="HIGH", grouping_basis="SINGLE_KPI")
    blip = StageThreeResult(episode_id=1, cluster_id="blip", kpi_names=["revenue"],
                             priority_score=900.0, priority_basis="OBSERVED",
                             confidence="HIGH", grouping_basis="SINGLE_KPI")
    assert priority.rank([blip, collapse]) == [collapse, blip]
    assert priority.direction(-500000.0) == "DROP"
    assert priority.direction(900.0) == "SPIKE"
    assert priority.direction(None) is None


# --- live DB ---

def test_run_stage3_end_to_end(cur):
    results = run_stage3(cur, 1, day_range=range(0, 30))
    assert results, "expected at least one result over 30 days for episode 1"
    assert all(r.grouping_basis in
               ("SINGLE_KPI", "DAG_AND_CORRELATION", "SEPARATE_NO_ADJACENT_KPI", "SEPARATE_NO_CORRELATION")
               for r in results)


def test_clusters_a_real_injected_event(cur):
    """The only live-scoring check here -- reuses the same real episodes Stage 2's
    own live check already validated. Query is offline scoring only, never touched
    by stage3.py itself (CONSTITUTION.md non-negotiable #5).

    Bounded to a window around each candidate's start_day_offset and capped to a
    handful of episodes -- Stage 3 pulls each KPI's timeline twice per episode
    (once via run_stage2, once via load_dollar_residuals; plan Risk #2/#3), and at
    ~0.25s/round-trip against real Neon a full 120-day sweep across every
    qualifying episode is minutes, not seconds, for no extra signal."""
    cur.execute(
        "SELECT episode_id, start_day_offset FROM injected_events "
        "WHERE event_type IN ('marketing_cut','product_outage') AND severity IN ('moderate','severe') "
        "AND onset_type = 'step' ORDER BY episode_id LIMIT 5"
    )
    candidates = cur.fetchall()
    assert candidates, "expected at least one qualifying injected event in the live dataset"

    clustered = False
    for episode_id, start_day_offset in candidates:
        day_range = range(max(0, start_day_offset - 15), start_day_offset + 20)
        results = run_stage3(cur, episode_id, day_range=day_range)
        hit = any(
            r.grouping_basis == "DAG_AND_CORRELATION"
            and r.priority_basis == "OBSERVED"
            and r.priority_score is not None
            and r.window_start_day_offset <= start_day_offset + 15
            and r.window_end_day_offset >= start_day_offset
            for r in results
        )
        if hit:
            clustered = True
            break

    assert clustered, "Stage 3 should cluster revenue + active_customers with an observed priority score on at least one real event episode"


def test_relationship_evidence_is_live_not_dead(cur):
    """Audit finding F3's permanent regression guard. KNOWN_RELATIONSHIP evidence was
    structurally unreachable -- verified live at 0 occurrences across 32 days -- for two
    independent reasons, and BOTH have to stay fixed for this to pass:

      1. no caller ever passed run_stage2's other_kpi_candidates, so a KPI never saw
         that another KPI was also a candidate that day (fixed in stage2_bridge/stage3);
      2. relationship_graph.RELATIONSHIPS declares only the forward driver -> driven
         edge, so related_kpis('revenue') returned [] and the downstream KPI could
         never match (fixed by deriving the reverse edge in related_kpis).

    Asserting an output that only appears when the wiring is real is exactly the
    acceptance-criterion shape §11 of the remediation plan makes mandatory: a passing
    unit test is not evidence that a stage runs.

    Episode 8, days 40-72 is the same window the audit used to reproduce the bug, so a
    regression here reads directly against the recorded before/after."""
    day_range = list(range(40, 72))
    upstream = "active_customers_purchased_30d"

    first_pass = stage2_bridge.load_stage2_results(cur, 8, upstream, day_range)
    candidates = stage2_bridge.candidate_days_by_day(first_pass)
    assert candidates, "expected the upstream KPI to have candidate days to thread through"

    downstream = stage2_bridge.load_stage2_results(
        cur, 8, "revenue", day_range, other_kpi_candidates=candidates
    )
    evidence_types = {e["type"] for r in downstream for e in r.business_importance_evidence}
    assert "KNOWN_RELATIONSHIP" in evidence_types, (
        "KNOWN_RELATIONSHIP evidence is dead again -- Stage 2's Layer 5 relationship "
        f"graph is not reachable. Saw only: {evidence_types}"
    )
    assert any(r.cluster_id for r in downstream), "relationship evidence must produce a cluster_id"


if __name__ == "__main__":
    test_find_flagged_windows()
    test_attempt_cluster_adjacent_and_correlated()
    test_attempt_cluster_wrong_direction()
    test_attempt_cluster_out_of_lag()
    test_attempt_cluster_no_second_kpi()
    test_priority_case1_observed()
    test_priority_case2_unavailable()
    test_confidence_gate_ranks_without_discarding()
    test_rank_puts_biggest_dollar_impact_first_regardless_of_sign()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            test_run_stage3_end_to_end(cur)
            test_relationship_evidence_is_live_not_dead(cur)
            test_clusters_a_real_injected_event(cur)
    finally:
        conn.close()
    print("OK")
