# FastAPI Backend — Live Orchestration & Verification (first slice)

**Design report:** `docs/02-stage-design-reports/api-backend-orchestration-and-verification-design.md`
**Branch:** `feature/backend-orchestration-verification` (off `develop`)
**Consumes:** Stage 10's `stage9_bridge.py` (the full re-exported Stage 3-9 chain),
Stage 10's `stage10.py` (`run_stage10`), `demo/telemetry.py`

## Outcome

`uvicorn backend.main:app` serves `GET /episodes`, `POST /runs`, `WS /ws/runs/{run_id}`,
`GET /runs/{run_id}`. Picking any episode id and starting a run streams one real JSON
event per stage as it actually completes (including a clean early-terminate for a
declined/no-cluster episode), ending in a verification event scored against that
episode's held-out `injected_events`. `test_backend.py` proves this against episode 15
(a known "found something" run) and at least one other episode picked at test time
(exercising the declined-or-thin-evidence path honestly, whichever it turns out to be —
not pre-selected to look good).

## Files to read first

- `docs/02-stage-design-reports/api-backend-orchestration-and-verification-design.md`
- `pipeline/stage10_persona_narrative_routing/stage10.py` — the exact chain-calling
  sequence this orchestrator wraps (Stage 3 through 10/11), including its
  `--no-llm` flag pattern (reused here as a query param, so a verification-only run
  doesn't have to spend a real Gemini call)
- `pipeline/stage10_persona_narrative_routing/stage9_bridge.py` — what's already
  re-exported (`run_stage3` … `run_stage9`, `flagged_facets`) vs. what still needs its
  own lazy import (`should_fork`, `load_reference`)
- `demo/telemetry.py` — `stage()` context manager and `record_llm_call()`, reused as-is
- `demo/run_demo.py` — the prior Stages-1-4-only version of this same idea; its
  "no Stage 3 result → print and exit" branch is the pattern for this plan's
  declined/no_cluster event, generalized
- `pipeline/stage05a_fingerprint_classification/eval_against_ground_truth.py` — the
  real day-range-overlap matching against `injected_events` this plan's verification
  module reuses (`_match_event`, `_overlap_days`, the `_PERSISTING_EVENT_HORIZON`
  handling for events with no `end_day_offset`)
- `.claude/reference/database.md` — `injected_events` columns (`event_type`, `severity`,
  `onset_type`, `start_day_offset`, `end_day_offset`, `magnitude`, ...)

## Files to change/create

```
backend/
├── requirements.txt        (fastapi, uvicorn[standard], psycopg2-binary, python-dotenv,
│                             + the full stage9_bridge transitive chain: numpy,
│                             sentence-transformers, spacy, vaderSentiment, google-genai)
├── main.py                 (FastAPI app, the 4 endpoints)
├── orchestrator.py         (run_pipeline(episode_id, run_id, use_llm=True) -> generator
│                             of JSON-serializable event dicts; wraps stage10_bridge's
│                             chain calls in demo/telemetry.py's stage() context manager)
├── stage10_bridge.py       (same sys.path/sys.modules-eviction pattern, one layer past
│                             stage10_persona_narrative_routing/ -- re-exports
│                             stage9_bridge's full chain + personas.narrate_for_all_personas)
├── verification.py         (reuses eval_against_ground_truth.py's matching logic;
│                             scores one completed run's Stage 7 top hypothesis + Stage 8
│                             expected_impact against injected_events for that episode)
├── run_store.py            (in-memory dict of run_id -> {episode_id, status, events: []};
│                             no new DB table -- a run's transcript doesn't need to
│                             outlive the process for this slice, see Scope/Out)
└── test_backend.py
```

## Implementation steps

1. **`stage10_bridge.py`.** Mirror `stage10_persona_narrative_routing/stage9_bridge.py`
   exactly, one directory further. `_STAGE10_MODULE_NAMES` covers every file in
   `pipeline/stage10_persona_narrative_routing/` (`personas`, `stage11_bridge`,
   `stage9_bridge`, `stage10`) plus everything `stage9_bridge.py` itself would already
   evict (mirror its own list, don't hand-derive a shorter one — this is now the
   deepest bridge chain in the repo, backend → 10 → 9 → 8 → 7 → 6/5b/5a/4/3, and every
   shorter hand-derived list so far has eventually collided). Re-export:
   `run_stage3`...`run_stage9` (from `stage9_bridge`), `should_fork`, `load_reference`,
   `flagged_facets`, and `narrate_for_all_personas` (from `personas`, imported the same
   way `test_narrate.py`'s live test already reaches into `stage10_persona_narrative_routing/`
   via a `sys.path` insert). Test: import succeeds, every name callable.

2. **`orchestrator.py`.** `run_pipeline(cur, episode_id, use_llm=True)` is a generator
   (not a list-builder) — yields one event dict right after each stage call, so
   `main.py`'s WebSocket handler can forward each one the instant it's ready rather than
   buffering. Each stage call wrapped in `telemetry.stage(name, uses_llm=...)`; Stage
   10/11's two persona calls each get `record_llm_call()`. Early-terminate: no Stage 3
   result → yield `{stage: "stage3", status: "no_cluster"}` and stop (mirrors
   `run_demo.py`'s existing branch); Stage 7 `abstained` or Stage 8
   `abstained_upstream` are NOT early-terminates — Stage 9 already handles both
   correctly (`NO_DEFENSIBLE_ACTION`), so the chain runs to completion and that status
   is just what Stage 9's event reports. Each event's `summary` dict is hand-picked
   per stage (never `dataclasses.asdict()` the whole result — some fields aren't
   JSON-safe, e.g. `Stage9Result`'s dataclass nesting). Test offline with a fake
   cursor/monkeypatched bridge functions: early-terminate path yields exactly one
   event; a full run yields one event per stage in the right order.

3. **`verification.py`.** `score_run(cur, episode_id, stage7_result, stage8_result) ->
   dict`. Reuses `eval_against_ground_truth.py`'s `_fetch_events`/`_match_event`/
   `_overlap_days` (imported via the same bridge pattern, or copied verbatim if the
   original file's own "never imported by runtime" isolation comment makes importing
   it from a live-serving backend the wrong call — **resolve this specific question
   during implementation by reading that file's docstring reasoning first**, don't
   silently pick one). Given the matched event (or `None` — a legitimate "no real
   event in this window" outcome, which is itself the false-causality-rate signal, not
   an error), compute `top1_hit`/`top3_hit` against Stage 7's ranked
   `hypotheses[*].member_causes`, and leave `counterfactual_mae` as `None` in this
   slice (design report's stated new-math gap — do not fabricate a placeholder
   number). Test against a synthetic fixture with a known matched event and a known
   miss.

4. **`run_store.py`.** Plain module-level `dict[str, dict]`, `create_run(episode_id) ->
   run_id` (uuid4), `append_event(run_id, event)`, `get_run(run_id)`. No persistence
   beyond process lifetime — stated in Scope/Out, not a silent gap.

5. **`main.py`.** `GET /episodes`: `SELECT DISTINCT episode_id FROM episodes ORDER BY
   episode_id`. `POST /runs`: create a run, launch `orchestrator.run_pipeline` as a
   `BackgroundTasks` job that appends each yielded event to `run_store` (so `GET
   /runs/{run_id}` has data even before/without a socket ever connecting), return
   `{run_id}` immediately. `WS /ws/runs/{run_id}`: on connect, first replay any events
   already in `run_store` (handles a client connecting slightly late), then subscribe
   to new ones as they're appended (a simple `asyncio.Queue` per run, fed by the
   background task) until the run's final event, then close. `GET /runs/{run_id}`:
   return `run_store.get_run(run_id)` verbatim, 404 if unknown.

6. **`test_backend.py`.** Offline: `orchestrator`'s early-terminate and event-shape
   tests from step 2, `verification`'s hit/miss tests from step 3, `run_store`'s
   create/append/get round-trip. Live: start the app in-process (FastAPI
   `TestClient`), `POST /runs` for episode 15, drain the WebSocket to completion,
   assert the event sequence reaches a `verification` event and that Stage 10/11's
   narratives came through with real token usage (mirrors `test_stage10.py`'s live
   assertions) — then repeat against one more episode id (any id whose `GET /episodes`
   listing includes it, not hand-picked for a good outcome) and assert the run
   completes cleanly whether it declines early, finds a story with no evidence, or
   finds a full story — proving the "declining is a legitimate outcome" contract
   actually holds, not just declared in prose.

## Tests and validation gate

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_sm
.venv/bin/python test_backend.py     # must print OK
```

## Acceptance criteria

- [ ] `test_backend.py` prints `OK`
- [ ] `GET /episodes` returns all seeded episode ids, no pre-filtering
- [ ] A `POST /runs` for episode 15 streams a full 11-stage event sequence over the
      WebSocket ending in a `verification` event with a real `top1_hit`/`top3_hit`
- [ ] A `POST /runs` for an episode with no Stage 3 cluster terminates cleanly after
      one `no_cluster` event — not a hang, not an exception surfaced to the client
- [ ] A `POST /runs` for an episode other than 15 that reaches Stage 6 shows zero
      evidence retrieved without erroring (the stated Stage-6-evidence-sparsity gap
      handled, not hidden)
- [ ] `counterfactual_mae` is `None`, not a fabricated number, in this slice's
      verification event
- [ ] `GET /runs/{run_id}` after a run's socket has already closed returns the full
      transcript (proves `run_store` isn't socket-lifetime-only)
- [ ] `.claude/reference/architecture.md`'s FastAPI backend row updated off `❌`

## Risks

- **This is the deepest bridge chain in the repo** (backend → Stage 10 → 9 → 8 → 7 →
  6/5b/5a/4/3) — a ninth cross-import collision is plausible despite mirroring every
  prior eviction list exactly; budget time for one more if it happens, same category
  as the 8 already documented in `architecture.md`.
- **`counterfactual_mae` stays unscored this slice** (design report's stated new-math
  gap: no existing code re-derives Layer 1's true counterfactual with an event
  suppressed) — the verification event is honest but incomplete against
  `architecture-report.md` §9's full metric table until a follow-up adds it.
- **In-memory `run_store` means a backend restart loses all run history** — acceptable
  for a single-operator live demo, explicitly out of scope to fix with a DB table in
  this slice (would need a schema decision this plan doesn't make).
- **Heavy transitive install** (same `sentence-transformers`/`spacy` chain every
  downstream stage since 6 already needs) — first FastAPI process to carry the full
  weight of the pipeline's real dependencies, worth confirming cold-start latency is
  tolerable for a live demo (model loads happen once at import time, not per-request,
  but the first request after boot pays for it).
- **Whichever second episode `test_backend.py` picks at test time is not guaranteed
  reproducible run-to-run** if picked randomly — pin it to a fixed id (e.g. episode 1)
  once implementation confirms what that id's real behavior is, rather than leaving
  the test's outcome to chance.
