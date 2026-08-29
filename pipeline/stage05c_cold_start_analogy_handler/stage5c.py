"""Stage 5c orchestrator -- DecompositionResult -> Stage5cResult. See
.claude/plans/stage5c-cold-start-analogy-handler.md.

Usage:
    python stage5c.py --episode-id 1
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

import borrowed_percentile
import output_schema
from models import BorrowedAttribution, Stage5cResult

_THIN_ELIGIBILITIES = ("LIMITED_HISTORY", "INSUFFICIENT_DATA")


def run_stage5c(cur, episode_id, decomposition_result, reference):
    attributions = []
    for s in decomposition_result.slices:
        if s.eligibility not in _THIN_ELIGIBILITIES or s.deviation_pct is None:
            continue
        key = f"{s.kpi_name}|{s.dimension}|{s.slice_value}"
        entry = reference.get(key)
        percentile = borrowed_percentile.score(s.deviation_pct, entry)
        attributions.append(BorrowedAttribution(
            kpi_name=s.kpi_name, dimension=s.dimension, slice_value=s.slice_value,
            deviation_pct=s.deviation_pct, borrowed_percentile=percentile,
            reference_sample_count=entry["n"] if entry else 0,
            status="BORROWED" if percentile is not None else "NO_REFERENCE_AVAILABLE",
        ))

    result = Stage5cResult(
        episode_id=episode_id, cluster_id=decomposition_result.cluster_id, attributions=attributions,
    )
    output_schema.validate(result)
    return result


def main():
    import reference_builder  # imported lazily -- CLI-only, same as other stages' own bridge imports
    import stage3_bridge
    import stage4_bridge

    parser = argparse.ArgumentParser(description="Run Stage 5c cold-start/analogy handler.")
    parser.add_argument("--episode-id", type=int, required=True)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            stage3_results = stage3_bridge.run_stage3(cur, args.episode_id)
            if not stage3_results:
                print(f"no Stage 3 results for episode {args.episode_id}")
                return
            stage3_result = stage3_results[0]
            decomposition_result = stage4_bridge.run_stage4(cur, args.episode_id, stage3_result)
            reference = reference_builder.load_reference()
            result = run_stage5c(cur, args.episode_id, decomposition_result, reference)
            if not result.attributions:
                print("no thin (LIMITED_HISTORY/INSUFFICIENT_DATA) slices in this decomposition")
            for a in result.attributions:
                print(a)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
