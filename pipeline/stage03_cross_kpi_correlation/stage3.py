"""Stage 3 orchestrator -- grouping + prioritization for the 2-KPI universe Stage
1/2 actually support (plan Scope). See
docs/02-stage-design-reports/stage3-cross-kpi-correlation-prioritization.md and
.claude/plans/stage3-cross-kpi-correlation.md.

Usage:
    python stage3.py --episode-id 1
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

import dag
import grouping
import priority
import stage2_bridge
from models import StageThreeResult

_UPSTREAM_KPI = "active_customers_purchased_30d"
_DOWNSTREAM_KPI = "revenue"


def _fetch_n_days(cur, episode_id):
    cur.execute("SELECT n_days FROM episodes WHERE episode_id=%s", (episode_id,))
    return cur.fetchone()[0]


def run_stage3(cur, episode_id, day_range=None):
    if day_range is None:
        day_range = range(_fetch_n_days(cur, episode_id))
    day_range = list(day_range)

    results = {}
    residuals = {}
    for kpi in (_UPSTREAM_KPI, _DOWNSTREAM_KPI):
        results[kpi] = stage2_bridge.load_stage2_results(cur, episode_id, kpi, day_range)
        residuals[kpi] = stage2_bridge.load_dollar_residuals(cur, episode_id, kpi, day_range)

    windows = {kpi: grouping.find_flagged_windows(results[kpi]) for kpi in results}
    confidence_by_day = {kpi: {r.day_offset: r.confidence for r in results[kpi]} for kpi in results}
    dag_entry = dag.related_kpis_with_lag(_UPSTREAM_KPI)[0]

    clustered = {_UPSTREAM_KPI: set(), _DOWNSTREAM_KPI: set()}
    leftover_reason = {}
    out = []

    for a_window in windows[_UPSTREAM_KPI]:
        window, reason = grouping.attempt_cluster(
            [a_window], residuals[_UPSTREAM_KPI], windows[_DOWNSTREAM_KPI], residuals[_DOWNSTREAM_KPI], dag_entry
        )
        if window is None:
            leftover_reason[(_UPSTREAM_KPI, a_window)] = reason
            continue
        w_start, w_end = window
        clustered[_UPSTREAM_KPI].add(a_window)
        b_window = next((b for b in windows[_DOWNSTREAM_KPI] if b[0] <= w_end and b[1] >= w_start), None)
        if b_window:
            clustered[_DOWNSTREAM_KPI].add(b_window)

        kpi_names = [_UPSTREAM_KPI, _DOWNSTREAM_KPI]
        priority_score, priority_basis = priority.score_priority(kpi_names, w_start, w_end, residuals)
        confidence = confidence_by_day[_DOWNSTREAM_KPI].get(w_end, confidence_by_day[_UPSTREAM_KPI].get(a_window[1], "LOW"))
        out.append(StageThreeResult(
            episode_id=episode_id, cluster_id=f"cluster_{episode_id}_{w_start}_{w_end}",
            kpi_names=kpi_names, window_start_day_offset=w_start, window_end_day_offset=w_end,
            priority_score=priority_score, priority_basis=priority_basis,
            confidence=confidence, grouping_basis="DAG_AND_CORRELATION",
        ))

    for kpi in (_UPSTREAM_KPI, _DOWNSTREAM_KPI):
        other = _DOWNSTREAM_KPI if kpi == _UPSTREAM_KPI else _UPSTREAM_KPI
        for start, end in windows[kpi]:
            if (start, end) in clustered[kpi]:
                continue
            confidence = confidence_by_day[kpi].get(end, "LOW")
            priority_score, priority_basis = priority.score_priority([kpi], start, end, residuals)
            basis = leftover_reason.get((kpi, (start, end)))
            if basis is None:
                basis = "SINGLE_KPI" if not windows[other] else "SEPARATE_NO_CORRELATION"
            out.append(StageThreeResult(
                episode_id=episode_id, cluster_id=None, kpi_names=[kpi],
                window_start_day_offset=start, window_end_day_offset=end,
                priority_score=priority_score, priority_basis=priority_basis,
                confidence=confidence, grouping_basis=basis,
            ))

    return out


def main():
    parser = argparse.ArgumentParser(description="Run Stage 3 cross-KPI correlation & prioritization.")
    parser.add_argument("--episode-id", type=int, required=True)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            for r in run_stage3(cur, args.episode_id):
                print(r)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
