"""Stage 10 self-check -- one offline invariant (narrate_for_all_personas covers
both personas, threads the identical fact sheet to each) + one live full-chain run
against episode 15 (Stage 3 -> 4 -> 5a/5c -> [5b] -> 6 -> 7 -> 8 -> 9 -> both
personas), proving Stage 10/11 sit on real pipeline output, not only the fakes in
stage11_narration/test_narrate.py.

Run: .venv/bin/python test_stage10.py
"""

import os

import psycopg2
from dotenv import load_dotenv

from personas import PERSONAS, narrate_for_all_personas

# --- offline ---


class _FakeStage3Result:
    def __init__(self):
        self.episode_id = 1
        self.cluster_id = "c1"
        self.kpi_names = ["revenue"]
        self.window_start_day_offset = 1
        self.window_end_day_offset = 3
        self.priority_score = -500.0
        self.priority_basis = "OBSERVED"
        self.confidence = "HIGH"
        self.grouping_basis = "SINGLE_KPI"


def test_narrate_for_all_personas_covers_both_and_shares_fact_sheet():
    result = narrate_for_all_personas(_FakeStage3Result(), use_llm=False)
    assert set(result.keys()) == set(PERSONAS.keys()) == {"executive", "analyst"}
    exec_sheet, exec_narrative, exec_usage = result["executive"]
    analyst_sheet, analyst_narrative, analyst_usage = result["analyst"]
    assert exec_sheet == analyst_sheet, "both personas narrate the same fact sheet, only the prompt differs"
    assert exec_narrative is None and analyst_narrative is None


# --- live: episode 15's real chain, all the way through Stage 9, into both personas ---


def test_live_stage10_11_episode_15():
    import stage9_bridge

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            stage3_results = stage9_bridge.run_stage3(cur, 15)
            assert stage3_results, "expected at least one Stage 3 cluster for episode 15"
            stage3_result = stage3_results[0]

            decomposition_result = stage9_bridge.run_stage4(cur, 15, stage3_result)
            reference = stage9_bridge.load_reference()
            fingerprint_result, cold_start_result = stage9_bridge.run_stage5a_and_5c(
                cur, 15, stage3_result, decomposition_result, reference
            )
            forked, reason = stage9_bridge.should_fork(fingerprint_result.cause_scores, decomposition_result)
            print(f"Stage 5b fork decision: {forked} ({reason})")
            stage5b_result = (
                stage9_bridge.run_stage5b(cur, 15, fingerprint_result, decomposition_result) if forked else None
            )
            evidence_result = stage9_bridge.run_stage6(cur, 15, decomposition_result, fingerprint_result)

            stage7_result = stage9_bridge.run_stage7(
                15, stage3_result.cluster_id, fingerprint_result, stage5b_result, cold_start_result, evidence_result,
            )
            print(f"Stage 7: abstained={stage7_result.abstained}, {len(stage7_result.hypotheses)} hypothesis(es)")

            stage8_result = stage9_bridge.run_stage8(
                cur, 15, stage3_result.cluster_id,
                stage3_result.window_start_day_offset, stage3_result.window_end_day_offset,
                stage3_result.kpi_names, stage7_result, stage5b_result,
            )
            print(f"Stage 8: abstained_upstream={stage8_result.abstained_upstream}, "
                  f"{len(stage8_result.estimates)} estimate(s)")

            stage9_result = stage9_bridge.run_stage9(
                stage7_result, stage8_result, decomposition_result, stage9_bridge.flagged_facets
            )
            print(f"Stage 9: decision_status={stage9_result.decision_status}")

            narratives = narrate_for_all_personas(stage3_result, decomposition_result, stage9_result, use_llm=True)
            for persona, (fact_sheet, narrative, usage) in narratives.items():
                print(f"\n=== {persona} ===\n{narrative}")
                assert narrative.strip()
                assert usage["input_tokens"] > 0 and usage["output_tokens"] > 0

            exec_narrative = narratives["executive"][1]
            analyst_narrative = narratives["analyst"][1]
            assert exec_narrative != analyst_narrative, "personas must diverge on the real pipeline's own output"
            assert "correlation" not in exec_narrative.lower() and "correlation" not in analyst_narrative.lower()
    finally:
        conn.close()


if __name__ == "__main__":
    test_narrate_for_all_personas_covers_both_and_shares_fact_sheet()

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit(
            "DATABASE_URL not set -- offline check passed, but the live full-chain run "
            "(test_live_stage10_11_episode_15) needs it."
        )
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise SystemExit(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) not set -- offline check passed, but the "
            "live full-chain run (test_live_stage10_11_episode_15) needs it."
        )
    test_live_stage10_11_episode_15()
    print("OK")
