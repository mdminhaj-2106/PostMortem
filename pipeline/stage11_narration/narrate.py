"""Stage 11 -- Narration. The only stage allowed to call an LLM (CONSTITUTION.md
non-negotiable #4). Everything it says must trace back to a field already present
in the fact sheet built here -- it is never handed raw KPI values or asked to judge
significance, cause, or ranking; those are already decided by the time this runs.

build_fact_sheet() is the guardrail the audit plan calls for: it IS the full
structured diagnosis, with zero LLM calls. Printing it alone (use_llm=False) proves
narration is decoration on top of an already-complete answer, not the source of it.
"""

import json

from stage3_bridge import direction

# gemini-3.6-flash: verified live against this project's real key (2026-08-30) --
# gemini-3.7-flash (what the docs currently point to) 503'd twice in a row and
# gemini-2.5-flash 404s as retired for new users; the API's own 404 error message
# named gemini-3.6-flash as the replacement, and it responded cleanly. Rates re-checked
# against ai.google.dev/gemini-api/docs/pricing for gemini-3.6-flash specifically (same
# as 3.7-flash: $0.75/$3.75 per MTok through 2026-12-31, then $1.50/$7.50).
# Exposed so the caller (demo/run_demo.py) can pass them to telemetry.record_llm_call --
# telemetry.py's own docstring is explicit that nothing in pipeline/ imports it, so this
# stage returns usage counts and lets the demo script do the recording, same as every
# other stage.
MODEL = "gemini-3.6-flash"
USD_PER_MTOK_IN = 0.75
USD_PER_MTOK_OUT = 3.75

MAX_FACT_SLICES = 5


def build_fact_sheet(stage3_result, decomposition_result=None, recommendation_result=None):
    """A plain, JSON-serializable dict -- the complete structured diagnosis. Every
    number Stage 11 is allowed to mention lives here; nothing else is passed to the model.

    recommendation_result is Stage 9's Stage9Result. Its primary_recommendation is often
    None (Stage 9 abstains on most hypotheses -- see stage09's README); decision_status is
    surfaced either way so a persona prompt can report "no defensible action yet" instead
    of being asked to state an action that doesn't exist.
    """
    sheet = {
        "episode_id": stage3_result.episode_id,
        "kpis_involved": list(stage3_result.kpi_names),
        "window_start_day": stage3_result.window_start_day_offset,
        "window_end_day": stage3_result.window_end_day_offset,
        "direction": direction(stage3_result.priority_score),
        "priority_score_abs_usd": abs(stage3_result.priority_score) if stage3_result.priority_score is not None else None,
        "priority_basis": stage3_result.priority_basis,
        "confidence": stage3_result.confidence,
        "how_kpis_were_linked": stage3_result.grouping_basis,
    }

    if decomposition_result is not None:
        measured = [s for s in decomposition_result.slices if s.observation_status == "OBSERVED"]
        top = sorted(measured, key=lambda s: abs(s.deviation_pct or 0), reverse=True)[:MAX_FACT_SLICES]
        sheet["top_slices"] = [
            {
                "kpi_name": s.kpi_name, "dimension": s.dimension, "slice_value": s.slice_value,
                "deviation_pct": s.deviation_pct, "eligibility": s.eligibility,
            }
            for s in top
        ]
    else:
        sheet["top_slices"] = []

    if recommendation_result is not None:
        sheet["decision_status"] = recommendation_result.decision_status
        rec = recommendation_result.primary_recommendation
        sheet["recommendation"] = None if rec is None else {
            "action_type": rec.action_type,
            "lever": rec.lever,
            "primary_owner": rec.primary_owner,
            "decision_intent": rec.decision_intent,
            "expected_impact": rec.expected_impact,
            "impact_lower": rec.impact_lower,
            "impact_upper": rec.impact_upper,
        }
    else:
        sheet["decision_status"] = None
        sheet["recommendation"] = None

    return sheet


def call_llm(system_prompt, fact_sheet):
    """One call against the flash tier: this is prose-from-a-compact-JSON-fact-sheet,
    not open-ended reasoning -- exactly the case the Stage 11 README's Telemetry &
    Cost Governor exists to route cheaply.

    Returns (narrative_text, usage) where usage = {"input_tokens", "output_tokens"} --
    the caller records this into its own telemetry ledger."""
    from google import genai
    from google.genai import types

    client = genai.Client()
    response = client.models.generate_content(
        model=MODEL,
        contents=json.dumps(fact_sheet, indent=2),
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    usage = {
        "input_tokens": response.usage_metadata.prompt_token_count,
        "output_tokens": response.usage_metadata.candidates_token_count,
    }
    return response.text, usage


def narrate_incident(system_prompt, stage3_result, decomposition_result=None, recommendation_result=None, use_llm=True):
    """Returns (fact_sheet, narrative_or_None, usage_or_None). narrative/usage are
    None when use_llm=False -- the fact sheet alone is the complete diagnosis; see
    module docstring."""
    fact_sheet = build_fact_sheet(stage3_result, decomposition_result, recommendation_result)
    if not use_llm:
        return fact_sheet, None, None
    text, usage = call_llm(system_prompt, fact_sheet)
    return fact_sheet, text, usage
