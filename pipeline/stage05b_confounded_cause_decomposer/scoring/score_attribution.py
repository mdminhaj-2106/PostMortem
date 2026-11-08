"""Design report §11.2, offline-only: scores Stage 5b against the generator's own
effect_fraction math for real episodes with an overlapping distinct-type event pair.

# ponytail: scores up to --n-episodes real overlapping-pair episodes (default 5), not
# the design doc's full 28-episode eval set -- each episode costs a live Stage 3->4->5a->5b
# run. Widen --n-episodes once there's time budget for the full sweep; the metrics
# printed are real numbers either way, never a projected/assumed accuracy.

A known approximation, stated rather than hidden (design report §11.2): magnitude x
effect_fraction measures intensity within each event's own latent channel -- comparing
across channels to form a share treats a 0.3 marketing cut and a 0.3 reliability hit as
equally impactful, which isn't exactly true. The honest upgrade path is multi-seed
ablation; not built here.

Usage:
    python scoring/score_attribution.py --n-episodes 5
"""

import argparse
import os
import sys

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))
import pipeline_bridge
import simulator_bridge
import stage5a_bridge
from stage5b import run_stage5b


def _overlapping_pair_episodes(cur, n):
    cur.execute(
        """
        SELECT episode_id, event_id, event_type, start_day_offset, end_day_offset,
               onset_type, magnitude, mitigation_day_offset, mitigation_completeness
        FROM injected_events ORDER BY episode_id, start_day_offset
        """
    )
    by_episode = {}
    for row in cur.fetchall():
        by_episode.setdefault(row[0], []).append(row)

    episodes = []
    for episode_id, rows in by_episode.items():
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if a[2] == b[2]:
                    continue
                a_end = a[4] if a[4] is not None else a[3] + 9999
                b_end = b[4] if b[4] is not None else b[3] + 9999
                if a[3] <= b_end and b[3] <= a_end:
                    episodes.append((episode_id, a, b))
                    break
            else:
                continue
            break
        if len(episodes) >= n:
            break
    return episodes


def _true_share(event_a, event_b, window_start, window_end):
    def event_dict(row):
        return {
            "start_day_offset": row[3], "end_day_offset": row[4], "onset_type": row[5],
            "magnitude": row[6], "mitigation_day_offset": row[7], "mitigation_completeness": row[8],
        }

    days = range(window_start, window_end + 1)
    intensity_a = sum(event_a[6] * simulator_bridge.effect_fraction(d, event_dict(event_a)) for d in days)
    intensity_b = sum(event_b[6] * simulator_bridge.effect_fraction(d, event_dict(event_b)) for d in days)
    total = intensity_a + intensity_b
    if total <= 0:
        return None
    return {event_a[2]: intensity_a / total, event_b[2]: intensity_b / total}


def score(cur, n_episodes):
    rows = []
    for episode_id, event_a, event_b in _overlapping_pair_episodes(cur, n_episodes):
        stage3_results = pipeline_bridge.run_stage3(cur, episode_id)
        window_start = max(event_a[3], event_b[3])
        window_end = min(
            event_a[4] if event_a[4] is not None else event_a[3] + 9999,
            event_b[4] if event_b[4] is not None else event_b[3] + 9999,
        )
        stage3_result = next(
            (r for r in stage3_results if r.window_start_day_offset <= window_end and window_start <= r.window_end_day_offset),
            None,
        )
        if stage3_result is None:
            rows.append((episode_id, event_a[2], event_b[2], "NO_STAGE3_WINDOW", None, None))
            continue

        decomposition_result = pipeline_bridge.run_stage4(cur, episode_id, stage3_result)
        stage5a_result = stage5a_bridge.run_stage5a(cur, episode_id, stage3_result, decomposition_result)
        result = run_stage5b(cur, episode_id, stage5a_result, decomposition_result)
        true_share = _true_share(event_a, event_b, stage3_result.window_start_day_offset, stage3_result.window_end_day_offset)
        rows.append((episode_id, event_a[2], event_b[2], result.identifiability_verdict, result, true_share))
    return rows


def print_report(rows):
    print(f"episodes scored: {len(rows)}")
    for episode_id, cause_a, cause_b, verdict, result, true_share in rows:
        print(f"\nepisode {episode_id}: {cause_a} x {cause_b} -- verdict={verdict}")
        if result is None:
            continue
        print(f"  true_share (ground truth, generator math): {true_share}")
        for c in result.contributions:
            print(f"  predicted: {c.cause:40s} share={c.share:.3f} identifiability={c.identifiability}")


def main():
    parser = argparse.ArgumentParser(description="Offline Stage 5b attribution scorer. Never call from a runtime path.")
    parser.add_argument("--n-episodes", type=int, default=5)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            rows = score(cur, args.n_episodes)
            print_report(rows)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
