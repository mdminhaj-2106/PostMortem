"""Design report §7.2: offline basis learner -- averages the shared shape_features
vector over each cause's real single-event episodes (+ a handful of zero-event
episodes for `seasonal`). Queries injected_events (offline use only, never on the
runtime path -- CONSTITUTION.md non-negotiable #5).

# ponytail: samples --n-per-cause episodes per cause (default 5), not the design doc's
# full 56-single-event/54-zero-event training set -- each basis-learning episode costs a
# handful of live Stage 4-style queries. Full-set retrain is the upgrade path once there's
# time budget for it; the artifact records real `n` either way, so downstream code never
# has to guess how thin a basis is.

Usage:
    python basis/build_bases.py --n-per-cause 5
"""

import argparse
import json
import os
import sys

import numpy as np
import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))
import deviation_matrix
import shape_features
from cause_config import BASIS_WINDOW_DAYS, CAUSE_FAMILIES, SEASONAL

_BASIS_KPI = "revenue"  # the one KPI with all 3 dimensions -- see README's basis-KPI note
_ARTIFACT_PATH = os.path.join(os.path.dirname(__file__), "artifacts", "bases.json")


def _single_event_episodes(cur, event_type, n):
    cur.execute(
        """
        SELECT episode_id, start_day_offset FROM injected_events
        WHERE event_type=%s AND episode_id IN (
            SELECT episode_id FROM injected_events GROUP BY episode_id HAVING COUNT(*)=1
        )
        ORDER BY episode_id LIMIT %s
        """,
        (event_type, n),
    )
    return cur.fetchall()


def _zero_event_episodes(cur, n):
    cur.execute(
        """
        SELECT episode_id, n_days FROM episodes
        WHERE episode_id NOT IN (SELECT DISTINCT episode_id FROM injected_events)
        ORDER BY episode_id LIMIT %s
        """,
        (n,),
    )
    return cur.fetchall()


def _learn_one(cur, episode_id, kpi_name, window_start):
    window_end = window_start + BASIS_WINDOW_DAYS - 1
    matrix = deviation_matrix.build(cur, episode_id, kpi_name, window_start, window_end)
    return shape_features.build_shape_vector(matrix, window_start, window_end)


def build_bases(cur, n_per_cause):
    bases = {}
    for cause in CAUSE_FAMILIES:
        rows = _single_event_episodes(cur, cause, n_per_cause)
        vectors = [_learn_one(cur, ep, _BASIS_KPI, start) for ep, start in rows]
        if not vectors:
            continue
        stacked = np.stack(vectors)
        bases[cause] = {
            "basis": stacked.mean(axis=0).tolist(),
            "std": stacked.std(axis=0).tolist(),
            "n": len(vectors),
        }

    zero_rows = _zero_event_episodes(cur, n_per_cause)
    mid_window_starts = [max(15, n_days // 2 - BASIS_WINDOW_DAYS // 2) for _ep, n_days in zero_rows]
    seasonal_vectors = [
        _learn_one(cur, ep, _BASIS_KPI, start)
        for (ep, _n_days), start in zip(zero_rows, mid_window_starts)
    ]
    if seasonal_vectors:
        stacked = np.stack(seasonal_vectors)
        bases[SEASONAL] = {
            "basis": stacked.mean(axis=0).tolist(),
            "std": stacked.std(axis=0).tolist(),
            "n": len(seasonal_vectors),
        }
    return bases


def main():
    parser = argparse.ArgumentParser(description="Learn Stage 5b's cause-shape bases.")
    parser.add_argument("--n-per-cause", type=int, default=5)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            bases = build_bases(cur, args.n_per_cause)
    finally:
        conn.close()

    artifact = {"feature_version": shape_features.FEATURE_VERSION, "basis_kpi": _BASIS_KPI, "bases": bases}
    os.makedirs(os.path.dirname(_ARTIFACT_PATH), exist_ok=True)
    with open(_ARTIFACT_PATH, "w") as f:
        json.dump(artifact, f, indent=2)

    for cause, entry in bases.items():
        print(f"{cause}: n={entry['n']}")
    print(f"wrote {_ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
