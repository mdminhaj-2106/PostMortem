"""Offline-only: runs Stage 3->4->5a against real episodes and scores top_cause against
injected_events (the answer key). NEVER imported by stage5a.py or any runtime module --
same isolation as this project's existing offline threshold-calibration work
(CONSTITUTION.md non-negotiable #5: injected_events is held out from the running pipeline).

Usage:
    python eval_against_ground_truth.py --n-episodes 30
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

import stage3_bridge
import stage4_bridge
import stage5a
from models import EVENT_TYPES

_PERSISTING_EVENT_HORIZON = 9999  # end_day_offset is None for a marketing_cut that never recovers


def _fetch_episodes_with_events(cur, n_episodes):
    cur.execute("SELECT DISTINCT episode_id FROM injected_events ORDER BY episode_id LIMIT %s", (n_episodes,))
    return [r[0] for r in cur.fetchall()]


def _fetch_events(cur, episode_id):
    cur.execute(
        "SELECT event_type, start_day_offset, end_day_offset FROM injected_events WHERE episode_id=%s",
        (episode_id,),
    )
    return [
        (event_type, start, end if end is not None else start + _PERSISTING_EVENT_HORIZON)
        for event_type, start, end in cur.fetchall()
    ]


def _overlap_days(a_start, a_end, b_start, b_end):
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def _match_event(window_start, window_end, events):
    """The injected event whose day range overlaps this Stage 3 window the most --
    None if no real event ever touched this window (a noise cluster, not scoreable)."""
    best_type, best_overlap = None, 0
    for event_type, e_start, e_end in events:
        ov = _overlap_days(window_start, window_end, e_start, e_end)
        if ov > best_overlap:
            best_type, best_overlap = event_type, ov
    return best_type


def run_eval(cur, episode_ids):
    rows = []  # (episode_id, true_type, predicted_type, confidence)
    for episode_id in episode_ids:
        events = _fetch_events(cur, episode_id)
        if not events:
            continue
        for stage3_result in stage3_bridge.run_stage3(cur, episode_id):
            true_type = _match_event(
                stage3_result.window_start_day_offset, stage3_result.window_end_day_offset, events
            )
            if true_type is None:
                continue
            decomposition_result = stage4_bridge.run_stage4(cur, episode_id, stage3_result)
            result = stage5a.run_stage5a(cur, episode_id, stage3_result, decomposition_result)
            rows.append((episode_id, true_type, result.top_cause, result.confidence))
    return rows


def print_report(rows):
    total = len(rows)
    if total == 0:
        print("no scoreable (window, event) pairs found")
        return
    correct = sum(1 for _, t, p, _ in rows if t == p)
    print(f"episode-windows scored: {total}")
    print(f"top-1 accuracy: {correct}/{total} = {correct / total:.3f}")

    counts = {t: {p: 0 for p in EVENT_TYPES} for t in EVENT_TYPES}
    for _, t, p, _ in rows:
        counts[t][p] += 1
    col = 18
    print("\nconfusion (rows=true, cols=predicted):")
    print("true\\pred".ljust(col) + "".join(p.ljust(col) for p in EVENT_TYPES))
    for t in EVENT_TYPES:
        print(t.ljust(col) + "".join(str(counts[t][p]).ljust(col) for p in EVENT_TYPES))


def main():
    parser = argparse.ArgumentParser(
        description="Offline Stage 5a accuracy vs injected_events. Never call from a runtime path."
    )
    parser.add_argument("--n-episodes", type=int, default=30)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            episode_ids = _fetch_episodes_with_events(cur, args.n_episodes)
            rows = run_eval(cur, episode_ids)
            print_report(rows)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
