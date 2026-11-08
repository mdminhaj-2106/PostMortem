"""Stage 10 orchestrator -- (Stage3Result, DecompositionResult, Stage9Result) ->
{persona_name: (fact_sheet, narrative_or_None, usage_or_None)}. See
.claude/plans/stage10-11-persona-narrative-routing-narration.md.

Usage:
    python stage10.py --episode-id 15 [--no-llm]
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

from personas import narrate_for_all_personas


def run_stage10(stage3_result, decomposition_result=None, recommendation_result=None, use_llm=True):
    return narrate_for_all_personas(stage3_result, decomposition_result, recommendation_result, use_llm=use_llm)


def main():
    import stage9_bridge

    parser = argparse.ArgumentParser(description="Run Stage 10/11 persona narration.")
    parser.add_argument("--episode-id", type=int, required=True)
    parser.add_argument("--no-llm", action="store_true", help="fact sheets only, no LLM calls")
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            stage3_results = stage9_bridge.run_stage3(cur, args.episode_id)
            if not stage3_results:
                print(f"no Stage 3 results for episode {args.episode_id}")
                return
            stage3_result = stage3_results[0]
            print(f"investigating: {stage3_result}")

            decomposition_result = stage9_bridge.run_stage4(cur, args.episode_id, stage3_result)
            reference = stage9_bridge.load_reference()
            fingerprint_result, cold_start_result = stage9_bridge.run_stage5a_and_5c(
                cur, args.episode_id, stage3_result, decomposition_result, reference
            )

            forked, reason = stage9_bridge.should_fork(fingerprint_result.cause_scores, decomposition_result)
            print(f"Stage 5b fork decision: {forked} ({reason})")
            stage5b_result = (
                stage9_bridge.run_stage5b(cur, args.episode_id, fingerprint_result, decomposition_result)
                if forked else None
            )

            evidence_result = stage9_bridge.run_stage6(cur, args.episode_id, decomposition_result, fingerprint_result)

            stage7_result = stage9_bridge.run_stage7(
                args.episode_id, stage3_result.cluster_id,
                fingerprint_result, stage5b_result, cold_start_result, evidence_result,
            )
            print(f"Stage 7: abstained={stage7_result.abstained}, {len(stage7_result.hypotheses)} hypothesis(es)")

            stage8_result = stage9_bridge.run_stage8(
                cur, args.episode_id, stage3_result.cluster_id,
                stage3_result.window_start_day_offset, stage3_result.window_end_day_offset,
                stage3_result.kpi_names, stage7_result, stage5b_result,
            )
            print(f"Stage 8: abstained_upstream={stage8_result.abstained_upstream}, "
                  f"{len(stage8_result.estimates)} estimate(s)")

            stage9_result = stage9_bridge.run_stage9(
                stage7_result, stage8_result, decomposition_result, stage9_bridge.flagged_facets
            )
            print(f"Stage 9: decision_status={stage9_result.decision_status}")

            narratives = run_stage10(stage3_result, decomposition_result, stage9_result, use_llm=not args.no_llm)
            for persona, (fact_sheet, narrative, usage) in narratives.items():
                print(f"\n=== {persona} ===")
                if narrative is not None:
                    print(narrative)
                    print(f"  ({usage['input_tokens']} in / {usage['output_tokens']} out tokens)")
                else:
                    print(f"[fact sheet only] {fact_sheet}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
