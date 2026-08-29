"""Offline: scans a bounded sample of episodes and pools each slice's own MATURE
(day_offset >= 30, matching eligibility.MIN_OBSERVATIONS_FOR_ELIGIBLE) relative
deviations into one cross-episode reference distribution per (kpi_name, dimension,
slice_value) -- the user's 2026-08-30 decision in place of the design doc's declared
per-slice analogy_groups.yaml (see .claude/plans/stage5c-cold-start-analogy-handler.md's
header: real eligibility is uniform per-window, not per-slice-value, so a same-window
sibling slice is never a valid analog -- another episode's own mature history for the
SAME slice_value is).

Same offline-artifact-builder shape as Stage 5b's basis/build_bases.py: plain JSON, no
numpy/scipy/joblib needed here (just list pooling), queries live data directly (offline
use only, never on the runtime path -- CONSTITUTION.md non-negotiable #5 doesn't apply,
this reads Layer 2 views via stage4_bridge, never injected_events).

# ponytail: --n-episodes defaults to 20, not the full 150-episode corpus -- each
# episode costs one full-timeline residual pass per (kpi, dimension, slice_value).
# Widening it is the direct lever if NO_REFERENCE_AVAILABLE shows up more than expected
# live; the artifact records real sample counts either way, so downstream never has to
# guess how thin a reference is.

Usage:
    python reference_builder.py --n-episodes 20
"""

import argparse
import json
import os

import psycopg2
from dotenv import load_dotenv

import stage2_bridge
import stage4_bridge

_ARTIFACT_PATH = os.path.join(os.path.dirname(__file__), "reference", "artifacts", "reference.json")
_MIN_MATURE_DAY = 30  # matches stage02_significance_detection/eligibility.py's MIN_OBSERVATIONS_FOR_ELIGIBLE


def _episode_ids(cur, n_episodes):
    cur.execute("SELECT episode_id, n_days FROM episodes ORDER BY episode_id LIMIT %s", (n_episodes,))
    return cur.fetchall()


def _mature_relative_deviations(cur, episode_id, n_days, kpi_name, dimension, slice_value):
    timeline = stage4_bridge.slice_fetcher.load_slice_timeline(
        cur, episode_id, kpi_name, dimension, slice_value, range(0, n_days)
    )
    residuals = stage2_bridge.compute_residuals(timeline)
    return [
        r / e for d, e, r in residuals
        if d >= _MIN_MATURE_DAY and e not in (None, 0) and r is not None
    ]


def build_reference(cur, n_episodes):
    pooled = {}
    for episode_id, n_days in _episode_ids(cur, n_episodes):
        for kpi_name, dimensions in stage4_bridge.dimension_config.DIMENSION_APPLICABILITY.items():
            for dimension in dimensions:
                for slice_value in stage4_bridge.slice_fetcher.distinct_slice_values(cur, episode_id, dimension):
                    key = f"{kpi_name}|{dimension}|{slice_value}"
                    deviations = _mature_relative_deviations(
                        cur, episode_id, n_days, kpi_name, dimension, slice_value
                    )
                    pooled.setdefault(key, []).extend(deviations)
    return {key: {"samples": samples, "n": len(samples)} for key, samples in pooled.items()}


def load_reference(path=_ARTIFACT_PATH):
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Build Stage 5c's cross-episode reference distributions.")
    parser.add_argument("--n-episodes", type=int, default=20)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            reference = build_reference(cur, args.n_episodes)
    finally:
        conn.close()

    os.makedirs(os.path.dirname(_ARTIFACT_PATH), exist_ok=True)
    with open(_ARTIFACT_PATH, "w") as f:
        json.dump(reference, f)
    total_keys = len(reference)
    total_samples = sum(v["n"] for v in reference.values())
    print(f"wrote {total_keys} keys, {total_samples} pooled samples -> {_ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
