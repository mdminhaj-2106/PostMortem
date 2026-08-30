# Stage 11 — Narration (LLM-only)

**Job:** turn the final structured object into prose. Nothing upstream of this stage is allowed to touch narrative language.

**Status:** Built (first slice). See `docs/02-stage-design-reports/stage10-11-persona-narrative-routing-narration.md` and `.claude/plans/stage10-11-persona-narrative-routing-narration.md`.

**Founding principle (applies across the whole pipeline, not just this stage):** "the LLM is never the source of quantitative truth." `build_fact_sheet()` in `narrate.py` is the guardrail: it IS the full structured diagnosis (episode/KPIs/window/direction/priority/confidence/how-linked/top-slices/Stage-9-decision-status-and-recommendation), built with zero LLM calls — `use_llm=False` proves narration is decoration on an already-complete answer, not the source of it. Every number, hypothesis rank, and confidence label already exists by the time this stage runs; its job is to turn that structured object into prose, not to decide what's true.

**LLM provider:** `google-genai`, `gemini-3.6-flash` (permanent switch from an earlier Anthropic-based draft — verified live against a real key; `gemini-3.7-flash` 503'd, `gemini-2.5-flash` 404s as retired for new users, `3.6-flash` is what Google's own API error named as the replacement). `MODEL`/`USD_PER_MTOK_*` are exposed so a caller can record cost into its own telemetry ledger — no Telemetry & Cost Governor service exists yet to do that routing itself.

`test_narrate.py` passes offline (7 checks, including the Stage 9 recommendation/abstention contract) + one live Gemini call proving persona divergence and the "never say correlation" rule. `pipeline/stage10_persona_narrative_routing/test_stage10.py` additionally proves this against the real Stage 3→9 chain, not just fixtures.

**Cost-sensitivity:** wrapped by the (not-yet-built) Telemetry & Cost Governor cross-cutting service in the target architecture; this stage does its part by returning usage counts for that service to eventually record, same as every other stage that doesn't import `telemetry.py` directly.
