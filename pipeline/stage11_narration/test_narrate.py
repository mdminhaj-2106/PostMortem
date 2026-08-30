"""Stage 11 self-check -- offline invariant checks (no DB, no LLM) + one live call
against the real Gemini API to prove the wiring (not just that the module imports).

Run: .venv/bin/python test_narrate.py
"""

import os

from dotenv import load_dotenv

from narrate import MAX_FACT_SLICES, build_fact_sheet, narrate_incident

# --- offline ---


class _FakeStage3Result:
    def __init__(self, priority_score, priority_basis="OBSERVED", confidence="HIGH",
                 grouping_basis="DAG_AND_CORRELATION"):
        self.episode_id = 1
        self.cluster_id = "c1"
        self.kpi_names = ["orders_count", "revenue", "units_sold"]
        self.window_start_day_offset = 107
        self.window_end_day_offset = 109
        self.priority_score = priority_score
        self.priority_basis = priority_basis
        self.confidence = confidence
        self.grouping_basis = grouping_basis


class _FakeSlice:
    def __init__(self, kpi_name, dimension, slice_value, deviation_pct, eligibility="ELIGIBLE",
                 observation_status="OBSERVED"):
        self.kpi_name = kpi_name
        self.dimension = dimension
        self.slice_value = slice_value
        self.deviation_pct = deviation_pct
        self.eligibility = eligibility
        self.observation_status = observation_status


class _FakeDecompositionResult:
    def __init__(self, slices):
        self.slices = slices


class _FakeRecommendation:
    def __init__(self, action_type="INCREASE", lever="marketing_spend", primary_owner="Marketing Lead",
                 decision_intent="ACT", expected_impact=5000.0, impact_lower=3000.0, impact_upper=7000.0):
        self.action_type = action_type
        self.lever = lever
        self.primary_owner = primary_owner
        self.decision_intent = decision_intent
        self.expected_impact = expected_impact
        self.impact_lower = impact_lower
        self.impact_upper = impact_upper


class _FakeStage9Result:
    def __init__(self, decision_status="RECOMMENDATION_AVAILABLE", primary_recommendation=None):
        self.decision_status = decision_status
        self.primary_recommendation = primary_recommendation


def test_fact_sheet_carries_direction_not_signed_score():
    sheet = build_fact_sheet(_FakeStage3Result(priority_score=-16975.45))
    assert sheet["direction"] == "DROP"
    assert sheet["priority_score_abs_usd"] == 16975.45
    assert sheet["priority_basis"] == "OBSERVED"


def test_fact_sheet_projected_unavailable_has_no_dollar_figure():
    sheet = build_fact_sheet(_FakeStage3Result(priority_score=None, priority_basis="PROJECTED_UNAVAILABLE"))
    assert sheet["direction"] is None
    assert sheet["priority_score_abs_usd"] is None


def test_fact_sheet_top_slices_excludes_unmeasured_and_caps_length():
    slices = [_FakeSlice("revenue", "region", f"R{i}", deviation_pct=float(i)) for i in range(10)]
    slices.append(_FakeSlice("revenue", "region", "GAP", deviation_pct=None, observation_status="NO_DATA_IN_WINDOW"))
    sheet = build_fact_sheet(_FakeStage3Result(priority_score=100.0), _FakeDecompositionResult(slices))
    assert len(sheet["top_slices"]) == MAX_FACT_SLICES
    assert all(s["slice_value"] != "GAP" for s in sheet["top_slices"])
    # sorted by |deviation_pct| descending
    assert [s["slice_value"] for s in sheet["top_slices"]] == ["R9", "R8", "R7", "R6", "R5"]


def test_fact_sheet_includes_recommendation_when_available():
    rec = _FakeRecommendation()
    sheet = build_fact_sheet(
        _FakeStage3Result(priority_score=-500.0),
        recommendation_result=_FakeStage9Result(primary_recommendation=rec),
    )
    assert sheet["decision_status"] == "RECOMMENDATION_AVAILABLE"
    assert sheet["recommendation"]["action_type"] == "INCREASE"
    assert sheet["recommendation"]["primary_owner"] == "Marketing Lead"


def test_fact_sheet_recommendation_null_on_abstention():
    sheet = build_fact_sheet(
        _FakeStage3Result(priority_score=-500.0),
        recommendation_result=_FakeStage9Result(decision_status="NO_DEFENSIBLE_ACTION", primary_recommendation=None),
    )
    assert sheet["decision_status"] == "NO_DEFENSIBLE_ACTION"
    assert sheet["recommendation"] is None


def test_fact_sheet_recommendation_absent_when_not_passed():
    sheet = build_fact_sheet(_FakeStage3Result(priority_score=-500.0))
    assert sheet["decision_status"] is None
    assert sheet["recommendation"] is None


def test_guardrail_no_llm_call_returns_fact_sheet_only():
    fact_sheet, narrative, usage = narrate_incident(
        "irrelevant system prompt", _FakeStage3Result(priority_score=-500.0), use_llm=False,
    )
    assert narrative is None and usage is None
    assert fact_sheet["direction"] == "DROP"


# --- live: one real Gemini API call ---


def test_live_narration_respects_persona_and_fact_sheet():
    import sys
    sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "stage10_persona_narrative_routing")))
    try:
        from personas import EXECUTIVE, ANALYST
    finally:
        sys.path.pop(0)

    result = _FakeStage3Result(priority_score=-16975.45)
    recommendation = _FakeStage9Result(primary_recommendation=_FakeRecommendation())
    exec_sheet, exec_text, exec_usage = narrate_incident(
        EXECUTIVE, result, recommendation_result=recommendation, use_llm=True,
    )
    analyst_sheet, analyst_text, analyst_usage = narrate_incident(ANALYST, result, use_llm=True)

    assert exec_usage["input_tokens"] > 0 and exec_usage["output_tokens"] > 0
    assert analyst_usage["input_tokens"] > 0 and analyst_usage["output_tokens"] > 0
    assert exec_text.strip() and analyst_text.strip()
    assert exec_text != analyst_text, "personas must diverge, not just vary in length"
    assert "correlation" not in exec_text.lower() and "correlation" not in analyst_text.lower()
    assert "Marketing Lead" in exec_text, "executive narrative must cite the real primary_owner, not invent one"


if __name__ == "__main__":
    test_fact_sheet_carries_direction_not_signed_score()
    test_fact_sheet_projected_unavailable_has_no_dollar_figure()
    test_fact_sheet_top_slices_excludes_unmeasured_and_caps_length()
    test_fact_sheet_includes_recommendation_when_available()
    test_fact_sheet_recommendation_null_on_abstention()
    test_fact_sheet_recommendation_absent_when_not_passed()
    test_guardrail_no_llm_call_returns_fact_sheet_only()

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise SystemExit(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) not set -- offline checks passed, but Stage 11's "
            "one live call (test_live_narration_respects_persona_and_fact_sheet) cannot run. Per "
            "this project's process rule, a stage that has never made a real call is unverified, "
            "not working. Set GEMINI_API_KEY (env or .env) and re-run."
        )
    test_live_narration_respects_persona_and_fact_sheet()
    print("OK")
