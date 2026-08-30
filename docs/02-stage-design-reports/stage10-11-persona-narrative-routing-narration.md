# Stage 10 + 11 — Persona Narrative Routing & Narration (combined design report)

Planned together, not as two isolated cycles, per explicit direction at the end of the
Stage 9 session: Stage 10's whole job is producing the input Stage 11's LLM call
consumes, so their contracts only make sense designed against each other.

**Locked job descriptions** (`docs/00-brief-and-topology/round2-topology-and-brief.md` §4,
authoritative — later summaries must match it):

- **Stage 10 — Persona Narrative Routing.** "Same underlying finding, reframed into
  different narrative and different recommended action per role — not just more/less
  detail." Round 1 only varied depth (exec-vs-analyst); Round 2 requires genuinely
  different narratives *and* different recommended actions per role.
- **Stage 11 — Narration (LLM-only).** "Turn the final structured object into prose.
  Nothing upstream of this stage is allowed to touch narrative language." The one hard
  architectural rule (`CONSTITUTION.md` non-negotiable #4): the LLM never decides
  significance, cause, or ranking — only narrates an already-decided result.

## What already existed going into this design pass

An untracked draft (`pipeline/stage10_persona_narrative_routing/{personas.py,
stage11_bridge.py}`, `pipeline/stage11_narration/{narrate.py, stage3_bridge.py,
test_narrate.py}`) of unknown origin, never reviewed against Stages 7-9's real
contracts. Two real defects were found and fixed in the session before this design
pass:

1. `build_fact_sheet()` only pulled from `StageThreeResult` (priority/direction/
   confidence/grouping_basis) and Stage 4's `DecompositionResult` (slices) — it never
   touched Stage 9's `Stage9Result` at all, yet the `EXECUTIVE` persona prompt demanded
   "one concrete recommended action with a suggested owner." Nothing supplied that,
   so the LLM had to invent one — a direct violation of this stage's own "never invent"
   rule. **Fixed**: `build_fact_sheet()` now takes `recommendation_result`, surfaces
   `decision_status` + `recommendation` (action_type/lever/primary_owner/decision_intent/
   expected_impact bounds), and is `None`-safe. `EXECUTIVE`'s prompt now branches: state
   the real action+owner when `recommendation` is non-null, state "no defensible action
   yet" (per `decision_status`) when it's null — never propose one itself.
2. The draft called `anthropic.Anthropic()` with no key available in this environment.
   Per explicit direction, this is a **permanent switch to the Gemini API**, not a
   temporary workaround. `call_llm()` now uses `google-genai`'s
   `client.models.generate_content()`. Model verified live against a real key:
   `gemini-3.7-flash` (what the docs pointed to) 503'd twice in a row and
   `gemini-2.5-flash` 404s as retired for new users; the API's own 404 error named
   `gemini-3.6-flash` as the replacement, which responded cleanly and is what's wired
   now. Pricing re-checked for that specific model ($0.75 in / $3.75 out per MTok
   through 2026-12-31, matching 3.7-flash's published rate).

Both fixes are live-verified (`test_narrate.py` prints `OK`, including one real Gemini
call proving persona divergence and that the "never call it correlation" rule holds).

## Output contract

`narrate_for_all_personas(stage3_result, decomposition_result=None,
recommendation_result=None, use_llm=True) -> {persona_name: (fact_sheet, narrative_or_None, usage_or_None)}`

- `fact_sheet`: plain JSON-serializable dict, the complete structured diagnosis — every
  number either persona is allowed to mention lives here, nothing else reaches the model.
  Same dict handed to both personas; only the system prompt differs (design requirement:
  "same underlying finding," not two different views of the data).
- `narrative`: `None` when `use_llm=False` (the fact-sheet-only guardrail proving
  narration is decoration on an already-complete answer, not the source of it),
  otherwise the model's prose.
- `usage`: `{"input_tokens", "output_tokens"}` or `None` — returned, not recorded,
  matching every other stage's pattern of leaving telemetry recording to the caller
  (`telemetry.py`'s own docstring: nothing in `pipeline/` imports it).

## Findings this design pass settled

1. **Security & Access Filter is out of scope for this slice, stated not hidden.**
   `stage10_persona_narrative_routing/README.md` names it as a real consumed
   dependency ("row/column/domain-level gating... applied at Stage 10's output, before
   narration reaches anyone"), and the topology brief confirms it's part of Stage 10's
   locked job. But `architecture.md`'s status table has it `❌ Not yet designed` — same
   as every other cross-cutting service this project hasn't built (Decision Rights,
   Learning & Memory, Telemetry & Cost Governor). Building real row/column/domain gating
   needs a user/role model that doesn't exist anywhere in this repo (no auth, no
   FastAPI). Same category as Stage 9's `historical_effectiveness=UNKNOWN`: the gap is
   declared, not silently patched over or faked.
2. **Decision Rights reduces to "pass Stage 9's owner fields through," nothing more.**
   The topology brief is explicit these live inside Stage 9's `owner` field and Stage
   10's routing, deliberately not merged with Security. Stage 9 already emits
   `primary_owner`/`secondary_owners`; Stage 10 doesn't add enforcement (no authority
   model exists to enforce against) — it only threads those fields into the fact sheet
   that reaches the `EXECUTIVE` narrative.
3. **ANALYST does not get the recommendation/decision_status fields, by design decision,
   not oversight.** ANALYST's job is "investigate further" — method, confidence,
   unusual slices, next diagnostic step. Recommending an action is EXECUTIVE's job.
   Exposing `recommendation` unused in ANALYST's prompt would risk the model
   volunteering an action anyway; keeping the divergence deliberate (what each persona
   is asked to do, not just what data it can see) matches the "different narrative AND
   different recommended action per role" requirement more literally than "give both
   personas everything and hope the prompt alone constrains them."
4. **No live proof existed that Stage 10/11 sit on Stage 1-9's real output** — every
   check in `test_narrate.py` used hand-built fakes (`_FakeStage3Result`,
   `_FakeStage9Result`). Every prior stage's acceptance gate is a real live-DB run
   against episode 15's actual cluster, not fixtures alone. This is the one substantive
   gap this design pass adds work for — see Scope/In below.

## Scope

**In:**
- `stage9_bridge.py` in `stage10_persona_narrative_routing/` — re-exports Stage 9's
  `run_stage9` plus its full re-exported upstream chain (Stage 3 through 8),
  bridge-of-bridges one layer past Stage 9's own `stage8_bridge.py`, same
  sys.path/sys.modules-eviction discipline as every prior bridge in this repo.
- `stage10.py` orchestrator (`run_stage10()` wrapping `narrate_for_all_personas`, plus
  a CLI `main()` that replays the full Stage 3→9 chain for a given `--episode-id`,
  mirroring `stage9.py`'s own `main()` shape).
- `test_stage10.py`: one offline invariant (`narrate_for_all_personas` covers both
  personas, both narrate the identical fact sheet) + **one live full-chain run against
  episode 15** (Stage 3 → 4 → 5a/5c → [5b] → 6 → 7 → 8 → 9 → both personas), proving
  the whole pipeline's real output narrates correctly end to end — the acceptance gate
  every other stage already has.
- `requirements.txt` updates: `stage10`'s gets the same transitive chain as `stage9`'s
  (`psycopg2-binary`, `python-dotenv`, `numpy`, `sentence-transformers`, `spacy`,
  `vaderSentiment`) plus `google-genai` for the persona calls it now triggers live.

**Out (stated, not hidden):**
- Security & Access Filter row/column/domain gating (finding #1) — no user/role model
  exists anywhere in this repo to gate against.
- Decision Rights enforcement beyond passing Stage 9's owner fields through (finding #2).
- FastAPI `/story/{id}` wiring — no backend exists yet (`architecture.md`).
- Telemetry & Cost Governor's actual cost-routing logic — stays a stub via the exposed
  `MODEL`/`USD_PER_MTOK_*` constants the caller can record, same as before this pass.
- Any persona beyond `executive`/`analyst` (design doc's own two-role split; no third
  role named anywhere in the brief).

## Known real gaps carried forward (stated, not hidden)

- Everything upstream (Stages 1-9) carries its own stated gaps (Stage 3's 2-KPI-only
  DAG, Stage 8's mostly-`MECHANISM_UNAVAILABLE` estimates, Stage 9's
  `historical_effectiveness=UNKNOWN`) — Stage 10/11 inherits whatever a live run of
  episode 15 actually produces, including a `NO_DEFENSIBLE_ACTION` decision_status if
  that's what Stage 9 real-computes. The `EXECUTIVE` prompt's abstention branch (fix
  #1 above) exists specifically so this is a correct outcome, not a failure.
- `gemini-3.6-flash`'s pricing was cross-checked against the same page as `3.7-flash`'s
  (identical numbers shown), not independently re-derived from a 3.6-specific pricing
  table section — worth a second look if Google splits their pricing later.
