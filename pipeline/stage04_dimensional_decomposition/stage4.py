"""Stage 4 orchestrator -- StageThreeResult -> DecompositionResult. See
docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md
and .claude/plans/stage4-dimensional-decomposition.md.

Usage:
    python stage4.py --episode-id 1
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

import decomposer
import output_schema


def run_stage4(cur, episode_id, stage3_result):
    result = decomposer.decompose_cluster(cur, episode_id, stage3_result)
    output_schema.validate(result)
    return result


def main():
    import stage3_bridge  # imported lazily -- its sys.path/sys.modules dance only
                           # needs to run for the CLI path, not every library caller

    parser = argparse.ArgumentParser(description="Run Stage 4 dimensional decomposition.")
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
            print(f"decomposing: {stage3_result}")
            result = run_stage4(cur, args.episode_id, stage3_result)
            for s in result.slices:
                print(s)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
