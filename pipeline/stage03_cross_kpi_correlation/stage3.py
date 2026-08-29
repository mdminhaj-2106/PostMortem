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

_CONFIDENCE_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _fetch_n_days(cur, episode_id):
    cur.execute("SELECT n_days FROM episodes WHERE episode_id=%s", (episode_id,))
    return cur.fetchone()[0]


def _find(parent, node):
    while parent[node] != node:
        parent[node] = parent[parent[node]]
        node = parent[node]
    return node


def _union(parent, a, b):
    root_a, root_b = _find(parent, a), _find(parent, b)
    if root_a != root_b:
        parent[root_a] = root_b


def _score_all_kpis(cur, episode_id, kpi_names, day_range):
    """Two symmetric passes so every KPI's Layer 4/5 sees every OTHER KPI's candidate
    days (F3). Pass 1 scores each KPI cold to discover its candidates; pass 2 rescores
    each one with the union of everyone else's.

    This replaces a hardcoded three-call upstream/downstream/upstream dance that only
    worked for exactly two KPIs and made the second KPI's context depend on call order.
    Cost is bounded by ingest's per-day cache: the DB work is one reconciliation per
    (kpi, day) regardless of how many passes read it.
    """
    first_pass = {
        kpi: stage2_bridge.load_stage2_results(cur, episode_id, kpi, day_range)
        for kpi in kpi_names
    }

    candidates_by_day = {}
    for kpi, results in first_pass.items():
        for day_offset, kpis_that_day in stage2_bridge.candidate_days_by_day(results).items():
            candidates_by_day.setdefault(day_offset, set()).update(kpis_that_day)

    return {
        kpi: stage2_bridge.load_stage2_results(
            cur, episode_id, kpi, day_range,
            other_kpi_candidates={
                day: others - {kpi}
                for day, others in candidates_by_day.items()
                if others - {kpi}
            },
        )
        for kpi in kpi_names
    }


def run_stage3(cur, episode_id, day_range=None, kpi_names=None):
    """Walks the whole declared DAG rather than one hardcoded edge.

    Was pinned to exactly two KPIs and one edge, which made the design doc's multi-path
    combination (3+-member clusters) structurally unreachable rather than merely
    unimplemented. With the real DAG a chain like
    active_customers -> orders_count -> revenue can now surface as ONE incident with
    three members instead of three unrelated findings.
    """
    if day_range is None:
        day_range = range(_fetch_n_days(cur, episode_id))
    day_range = list(day_range)
    kpi_names = list(kpi_names) if kpi_names else dag.kpis()

    results = _score_all_kpis(cur, episode_id, kpi_names, day_range)
    residuals = {
        kpi: stage2_bridge.load_dollar_residuals(cur, episode_id, kpi, day_range)
        for kpi in kpi_names
    }
    windows = {kpi: grouping.find_flagged_windows(results[kpi]) for kpi in kpi_names}
    confidence_by_day = {
        kpi: {r.day_offset: r.confidence for r in results[kpi]} for kpi in kpi_names
    }

    # Every flagged window is a node; a confirmed DAG edge between two windows unions
    # them. Connected components are the incidents -- which is what lets one cause
    # showing up in three KPIs land as a single cluster rather than three.
    nodes = [(kpi, window) for kpi in kpi_names for window in windows[kpi]]
    parent = {node: node for node in nodes}
    had_adjacent = {node: False for node in nodes}

    for source, entry in dag.edges():
        target = entry["target"]
        if source not in windows or target not in windows:
            continue
        for a_window in windows[source]:
            for b_window in windows[target]:
                linked, adjacent = grouping.windows_link(
                    a_window, residuals[source], b_window, residuals[target], entry
                )
                if adjacent:
                    had_adjacent[(source, a_window)] = True
                    had_adjacent[(target, b_window)] = True
                if linked:
                    _union(parent, (source, a_window), (target, b_window))

    components = {}
    for node in nodes:
        components.setdefault(_find(parent, node), []).append(node)

    out = []
    for members in components.values():
        member_kpis = sorted({kpi for kpi, _ in members})
        w_start = min(window[0] for _, window in members)
        w_end = max(window[1] for _, window in members)
        priority_score, priority_basis = priority.score_priority(
            member_kpis, w_start, w_end, residuals
        )
        # Worst confidence among the members: a cluster is only as trustworthy as its
        # shakiest evidence, and silently reporting the best one would overstate it.
        confidence = min(
            (confidence_by_day[kpi].get(window[1], "LOW") for kpi, window in members),
            key=lambda c: _CONFIDENCE_RANK.get(c, 0),
        )

        if len(members) > 1:
            out.append(StageThreeResult(
                episode_id=episode_id, cluster_id=f"cluster_{episode_id}_{w_start}_{w_end}",
                kpi_names=member_kpis, window_start_day_offset=w_start, window_end_day_offset=w_end,
                priority_score=priority_score, priority_basis=priority_basis,
                confidence=confidence, grouping_basis="DAG_AND_CORRELATION",
            ))
            continue

        node = members[0]
        kpi, _window = node
        if not dag.related_kpis_with_lag(kpi) and not any(
            e["target"] == kpi for _s, e in dag.edges()
        ):
            basis = "SINGLE_KPI"          # no DAG neighbour exists at all
        elif had_adjacent[node]:
            basis = "SEPARATE_NO_CORRELATION"   # something was in range; evidence refuted it
        else:
            basis = "SEPARATE_NO_ADJACENT_KPI"  # no neighbour was flagged nearby
        out.append(StageThreeResult(
            episode_id=episode_id, cluster_id=None, kpi_names=[kpi],
            window_start_day_offset=w_start, window_end_day_offset=w_end,
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
