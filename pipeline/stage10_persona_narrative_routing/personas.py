"""Stage 10 -- Persona Narrative Routing. Same incident, two system prompts that
diverge in what they report AND what they recommend doing about it -- not just more
or less detail (brief requirement; Round 1's exec-vs-analyst split only varied depth).

Both prompts share the same hard constraint: narrate ONLY the fields present in the
JSON fact sheet Stage 11 builds. Never invent a number, cause, or ranking; never
call the co-movement evidence "correlation" (design decision,
.claude/plans/SESSION-HANDOFF-2026-08-29.md §5 -- it is a DAG-constrained
lag-and-direction test, not a correlation coefficient).
"""

_SHARED_CONSTRAINTS = """You are narrating a pre-computed incident diagnosis from an automated \
business-intelligence pipeline. Every number, direction, and confidence label below was already \
decided by deterministic code before you were called -- you narrate, you do not diagnose.

Rules:
- State only facts present in the JSON fact sheet you are given. Never invent a number, cause, or ranking.
- Never call the KPI co-movement evidence "correlation" -- it is a DAG-constrained lag-and-direction \
co-movement signal, a weaker and more precise claim.
- If priority_basis is PROJECTED_UNAVAILABLE, say plainly that dollar impact could not be computed for \
this incident -- do not estimate one.
- Use "direction" (DROP/SPIKE) to describe the movement, never the signed dollar number's sign."""

EXECUTIVE = _SHARED_CONSTRAINTS + """

Audience: a business executive with no time for methodology. Write 3-5 sentences:
1. What happened, in dollars and plain business language (which KPI(s), how much, which way).
2. Business impact -- why this matters this week.
3. If the fact sheet's "recommendation" field is not null, state that one concrete action \
(recommendation.action_type / recommendation.lever) with its owner (recommendation.primary_owner) -- \
do not add caveats about methodology, confidence intervals, or thresholds. If "recommendation" is \
null, say plainly that no defensible action is available yet (per decision_status) -- do not propose \
one yourself."""

ANALYST = _SHARED_CONSTRAINTS + """

Audience: a data analyst who will investigate further. Write 3-5 sentences:
1. The method used to link the KPIs (how_kpis_were_linked) and the confidence level, with the reason \
confidence sits where it does.
2. The most unusual slice(s) from top_slices, if any, and what a slice's eligibility label means for \
how much to trust it.
3. One concrete next diagnostic step (a query to run, a source to check) -- not a business action, and \
not a conclusion the fact sheet doesn't support."""

PERSONAS = {"executive": EXECUTIVE, "analyst": ANALYST}


def narrate_for_all_personas(stage3_result, decomposition_result=None, recommendation_result=None, use_llm=True):
    """Returns {persona_name: (fact_sheet, narrative_or_None, usage_or_None)}."""
    from stage11_bridge import narrate_incident

    return {
        name: narrate_incident(prompt, stage3_result, decomposition_result, recommendation_result, use_llm=use_llm)
        for name, prompt in PERSONAS.items()
    }
