"""Runs the real Stage 3->4->5a/5c->[5b]->6->7->8->9->10/11 chain for one episode,
yielding one JSON-serializable event dict right after each stage actually completes
-- so a caller (main.py's WebSocket handler) can forward each event the instant it's
ready instead of buffering the whole run. See
.claude/plans/api-backend-orchestration-and-verification.md.

Reuses demo/telemetry.py's stage() context manager for per-stage timing + LLM cost,
exactly as Stage 11's narrate.py docstring already anticipated ("the caller can pass
[usage] to telemetry.record_llm_call").
"""

import os
import sys

import stage10_bridge
from verification import score_run

_DEMO_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "demo"))
sys.path.insert(0, _DEMO_DIR)
import telemetry  # noqa: E402
sys.path.remove(_DEMO_DIR)


def run_pipeline(cur, episode_id, use_llm=True):
    """Generator of event dicts. Terminates early (one event, status='no_cluster')
    if Stage 3 finds nothing -- a legitimate outcome (architecture.md's own critical
    flow #2: 'a noise episode -> Stage 2 declines -> logged, no story manufactured'),
    not an error."""
    telemetry.reset()

    with telemetry.stage("stage3"):
        stage3_results = stage10_bridge.run_stage3(cur, episode_id)
    if not stage3_results:
        yield {"stage": "stage3", "status": "no_cluster", "summary": {}}
        return
    stage3_result = stage3_results[0]
    yield {
        "stage": "stage3", "status": "completed",
        "summary": {
            "priority_score": stage3_result.priority_score,
            "priority_basis": stage3_result.priority_basis,
            "confidence": stage3_result.confidence,
            "kpi_names": list(stage3_result.kpi_names),
            "window_start_day": stage3_result.window_start_day_offset,
            "window_end_day": stage3_result.window_end_day_offset,
        },
    }

    with telemetry.stage("stage4"):
        decomposition_result = stage10_bridge.run_stage4(cur, episode_id, stage3_result)
    yield {
        "stage": "stage4", "status": "completed",
        "summary": {"slice_count": len(decomposition_result.slices)},
    }

    with telemetry.stage("stage5a_5c"):
        reference = stage10_bridge.load_reference()
        fingerprint_result, cold_start_result = stage10_bridge.run_stage5a_and_5c(
            cur, episode_id, stage3_result, decomposition_result, reference
        )
    yield {
        "stage": "stage5a_5c", "status": "completed",
        "summary": {
            "top_cause": fingerprint_result.top_cause,
            "confidence": fingerprint_result.confidence,
            "borrowed_count": sum(
                1 for a in (cold_start_result.attributions if cold_start_result else []) if a.status == "BORROWED"
            ),
        },
    }

    forked, fork_reason = stage10_bridge.should_fork(fingerprint_result.cause_scores, decomposition_result)
    stage5b_result = None
    if forked:
        with telemetry.stage("stage5b"):
            stage5b_result = stage10_bridge.run_stage5b(cur, episode_id, fingerprint_result, decomposition_result)
        yield {
            "stage": "stage5b", "status": "completed",
            "summary": {
                "fork_reason": fork_reason,
                "shares": {c.cause: c.share for c in stage5b_result.contributions},
            },
        }
    else:
        yield {"stage": "stage5b", "status": "skipped", "summary": {"fork_reason": fork_reason}}

    with telemetry.stage("stage6"):
        evidence_result = stage10_bridge.run_stage6(cur, episode_id, decomposition_result, fingerprint_result)
    yield {
        "stage": "stage6", "status": "completed",
        "summary": {"evidence_count": len(evidence_result.evidence)},
    }

    with telemetry.stage("stage7"):
        stage7_result = stage10_bridge.run_stage7(
            episode_id, stage3_result.cluster_id, fingerprint_result, stage5b_result,
            cold_start_result, evidence_result,
        )
    yield {
        "stage": "stage7", "status": "completed",
        "summary": {
            "abstained": stage7_result.abstained,
            "hypothesis_count": len(stage7_result.hypotheses),
            "top_hypothesis_id": stage7_result.hypotheses[0].hypothesis_id if stage7_result.hypotheses else None,
        },
    }

    with telemetry.stage("stage8"):
        stage8_result = stage10_bridge.run_stage8(
            cur, episode_id, stage3_result.cluster_id,
            stage3_result.window_start_day_offset, stage3_result.window_end_day_offset,
            stage3_result.kpi_names, stage7_result, stage5b_result,
        )
    yield {
        "stage": "stage8", "status": "completed",
        "summary": {
            "abstained_upstream": stage8_result.abstained_upstream,
            "estimate_count": len(stage8_result.estimates),
        },
    }

    with telemetry.stage("stage9"):
        stage9_result = stage10_bridge.run_stage9(
            stage7_result, stage8_result, decomposition_result, stage10_bridge.flagged_facets
        )
    primary = stage9_result.primary_recommendation
    yield {
        "stage": "stage9", "status": "completed",
        "summary": {
            "decision_status": stage9_result.decision_status,
            "action_type": primary.action_type if primary else None,
            "primary_owner": primary.primary_owner if primary else None,
        },
    }

    with telemetry.stage("stage10_11", uses_llm=use_llm) as record:
        narratives = stage10_bridge.narrate_for_all_personas(
            stage3_result, decomposition_result, stage9_result, use_llm=use_llm
        )
        for _fact_sheet, _narrative, usage in narratives.values():
            if usage is not None:
                telemetry.record_llm_call(record, usage["input_tokens"], usage["output_tokens"],
                                           stage10_bridge.USD_PER_MTOK_IN, stage10_bridge.USD_PER_MTOK_OUT)
    yield {
        "stage": "stage10_11", "status": "completed",
        "summary": {
            persona: {"narrative": narrative, "usage": usage}
            for persona, (_fact_sheet, narrative, usage) in narratives.items()
        },
    }

    with telemetry.stage("verification"):
        verification = score_run(cur, episode_id, stage3_result, stage7_result)
    yield {"stage": "verification", "status": "completed", "summary": verification}
