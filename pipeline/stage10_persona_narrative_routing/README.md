# Stage 10 — Persona Narrative Routing

**Job:** same underlying finding, reframed into a different narrative and different recommended action per role — not just more or less detail.

**Status:** Built (first slice). See `docs/02-stage-design-reports/stage10-11-persona-narrative-routing-narration.md` and `.claude/plans/stage10-11-persona-narrative-routing-narration.md`.

`personas.py` defines `EXECUTIVE`/`ANALYST` system prompts sharing a constraints block (never invent a fact, never call the KPI co-movement evidence "correlation"). `narrate_for_all_personas()` (or the `stage10.py` orchestrator's `run_stage10()`) hands both personas the identical fact sheet Stage 11 builds — only the prompt differs. `EXECUTIVE` states Stage 9's real recommended action + owner when one exists, and plainly says none is available yet (per `decision_status`) when it doesn't — never invents either way. `ANALYST` never sees the recommendation fields at all; its job is method/confidence/next-diagnostic-step, not action.

`test_stage10.py` passes offline + one live run of the full Stage 3→9 chain against episode 15, through both personas, via `stage9_bridge.py`.

**Consumes:** Stage 3 (`StageThreeResult`), Stage 4 (`DecompositionResult`), Stage 9 (`Stage9Result`) — via `stage9_bridge.py`, one bridge layer past Stage 9's own `stage8_bridge.py`.

**Out of scope, stated not hidden:** the Security & Access Filter cross-cutting service (row/column/domain-level output gating) named in the locked topology as applied at this stage's output — no such service exists anywhere in this repo yet (no user/role model, no FastAPI), same category as every other cross-cutting service this project hasn't built. Decision Rights reduces to passing Stage 9's `primary_owner`/`secondary_owners` fields through — no enforcement layer exists to enforce against. See the design report's Findings section for the full reasoning.
