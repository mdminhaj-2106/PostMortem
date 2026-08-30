# FastAPI Backend — Live Orchestration & Ground-Truth Verification (design report)

First backend work in this project (`architecture.md`: FastAPI is "not yet started").
Exists to serve the live UI: run the real 11-stage pipeline for a user-picked episode,
stream stage-by-stage progress over a WebSocket as it actually happens, then score the
final diagnosis against that episode's held-out `injected_events`.

## Why live orchestration, not replay

Decided explicitly: stage execution has real wall-clock cost (embeddings in Stage 6,
DB round-trips throughout), so the UI's animation pacing can be genuinely real instead
of faked timing — a stage "takes a moment" on screen because it actually did.

## Reused, not re-derived

Every stage's real chain-calling logic already exists and is proven live: Stage 9's
`stage8_bridge.py` → Stage 10's `stage9_bridge.py` → the exact sequence
`stage10.py`'s own `main()` already drives end to end (Stage 3→4→5a/5c→[5b]→6→7→8→9→
10/11). The backend's orchestrator is a thin wrapper emitting a progress event after
each of those same calls — not a re-implementation.

`demo/telemetry.py` also already exists and is exactly the per-stage timing + LLM-cost
ledger this orchestrator needs: `telemetry.stage(name, uses_llm=)` as a context manager
around each stage call, `record_llm_call()` for Stage 11's two persona calls, stdlib
only, already has its own `demo()` self-check. Reused as-is, not rebuilt — the `ts`/
timing data in each WS event comes from wrapping the existing chain calls in this same
context manager, and the run's final summary can reuse `print_summary()`'s aggregation
logic (adapted to return JSON instead of printing). `demo/run_demo.py` is the prior,
narrower version of this same idea (Stages 1-4 only, hardcoded to episode 8,
print-based) — its "if no Stage 3 result, print no story, exit" pattern is exactly the
declined/no_cluster early-terminate path this design report already calls for,
generalized to the full chain and to JSON events instead of prints. Left in place
as-is (a useful standalone manual-debugging script), not deleted or modified by this
work.

## Endpoints

- `GET /episodes` — lists episode ids (1-150, from `episodes` table). No pre-filtering
  or "known good" labeling in this slice — see Known real constraints below for why
  picking blind is honest, not a missing feature.
- `POST /runs` — body `{episode_id}`, starts a background run, returns `{run_id}`
  immediately (HTTP, not WebSocket — the socket is for progress, not kickoff).
- `WS /ws/runs/{run_id}` — one JSON event per stage as it completes:
  `{stage: "stage3", status: "declined" | "completed" | "no_data", summary: {...}}`.
  `summary` is a small, stage-specific dict (never the full dataclass) — e.g. Stage 3's
  summary is `{priority_score, direction, confidence}`, Stage 7's is
  `{abstained, hypothesis_count, top_hypothesis_id}`. The **final** event is
  `{stage: "verification", ...scoreboard}` (see Verification below) — the socket closes
  after it.
- `GET /runs/{run_id}` — polls the same data the socket streamed, for a client that
  reconnects mid-run or wants the full transcript after the fact (also doubles as the
  "replay a finished run" read path — a UI revisit doesn't need a new pipeline run).

## Verification — the Act 4 scoreboard

Reuses `stage05a_fingerprint_classification/eval_against_ground_truth.py`'s real
day-range-overlap matching against `injected_events` (`CONSTITUTION.md` non-negotiable:
`injected_events` is held out, never fed to the running pipeline — this endpoint is the
one place in the whole system allowed to query it, and only after a run is complete).
Metrics are exactly the five `architecture-report.md` §9 already locked — no new
metrics invented here:

| Metric | Computed from |
|---|---|
| Anomaly detection precision/recall | Stage 2's SIGNIFICANT/EMERGING/STRUCTURAL classification vs. whether a real event actually overlapped the window |
| Root-cause top-1/top-3 accuracy | Stage 7's ranked hypotheses' `member_causes` vs. the matched `injected_events.event_type` |
| False-causality rate | episodes/windows with **no** real overlapping event where the pipeline still produced a non-abstained hypothesis |
| Counterfactual MAE | Stage 8's `expected_impact` vs. the simulator's own true counterfactual (requires re-deriving what Layer 1 would have looked like with the injected event removed — see Risks, this is the one genuinely new piece of math) |
| Confidence calibration | Stage 7's `stage7_confidence` bucket vs. observed top-1 accuracy within that bucket, across a batch of runs, not just one |

Confidence calibration and precision/recall need a **batch** of episodes to mean
anything (a curve needs points) — for a single live run, `GET /runs/{run_id}`'s
scoreboard only returns the two per-episode-meaningful metrics (top-1/3 accuracy hit or
miss, counterfactual MAE for this episode's number). A separate `GET /verification/batch`
(reusing the same scoring function looped over N episodes) produces the full
precision/recall/calibration picture — out of scope for the live-run UI's first version,
in scope as a second screen once the single-episode story works (see Scope).

## Known real constraints (stated, not hidden)

- **Stage 6 evidence is real for episode 15 only.** Every other episode's
  `support_tickets.text` is `NULL` (764,537 pre-existing rows, per the DB migration
  note) — Stage 6 will legitimately retrieve zero evidence for any other episode. The
  UI must render "no evidence retrieved" as a normal state, not a spinner-stuck-forever
  or error state.
- **Not every episode produces a story.** Stage 2 may decline (normal variation), or
  Stage 3 may find no cross-KPI cluster worth prioritizing — both real, both already
  handled by the pipeline (`architecture.md`'s critical flow #2: "a noise episode →
  Stage 2 declines → logged, no LLM call spent, no story manufactured"). The run
  contract must carry a clean early-terminate event (`status: "declined"` /
  `"no_cluster"`) rather than forcing every run through all 11 stages.
- **Counterfactual MAE needs new math.** Nothing in this repo currently re-derives
  "what would Layer 1 have looked like without this injected event" — Stage 8's own
  counterfactual is computed against Stage 1/2's *observed* baseline, not Layer 1's
  true generative process. Scoring this metric means writing a small offline-only
  script that reruns the relevant slice of `generate.py`'s logic with the event
  suppressed — real new work, isolated the same way `eval_against_ground_truth.py`
  already is (never imported by any runtime module).
- **LangGraph is deferred for this slice.** `CONSTITUTION.md` names it as the intended
  orchestration layer ("planned"), but the actual conditional-skip logic it exists for
  (skip to log after Stage 2 declines) is a two-branch `if`, not a graph-shaped
  problem yet — every stage's chain-calling code in this repo today is already plain
  sequential Python (`stage10.py`'s `main()`). Adopting LangGraph here would be
  building infrastructure before there's a second conditional edge to justify it.
  Reconsider once Stage 3's real multi-KPI DAG iteration (a stated `architecture.md`
  gap) makes the graph shape real.

## Scope

**In:** `GET /episodes`, `POST /runs`, `WS /ws/runs/{run_id}`, `GET /runs/{run_id}`,
single-episode verification (top-1/3 hit, counterfactual MAE) as the run's final event,
the declined/no-cluster early-terminate path, reuse of every existing bridge chain.

**Out (stated, not hidden):** `GET /verification/batch` (precision/recall/calibration
curves — needs a UI screen of its own, second version), LangGraph, auth/multi-user
(single-operator demo), the `/detect`/`/investigate`/`/story` REST shape from the older
architecture-report (superseded by the run/WebSocket contract this design report
locks — CLAUDE.md's quick-reference list of those endpoint names is now stale against
this document).

## Output contract

```
GET /episodes -> [{episode_id: int}]
POST /runs {episode_id: int} -> {run_id: str}
WS /ws/runs/{run_id} -> stream of:
  {stage: str, status: "completed"|"declined"|"no_cluster"|"no_data", summary: dict, ts: float}
  ... last event ...
  {stage: "verification", top1_hit: bool|None, top3_hit: bool|None,
   counterfactual_mae: float|None, matched_event_type: str|None, ts: float}
GET /runs/{run_id} -> {episode_id, status, events: [...same shape as the stream...]}
```
