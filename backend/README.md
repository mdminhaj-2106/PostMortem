# FastAPI Backend — Live Orchestration & Verification

**Job:** serve the live UI. Run the real 11-stage pipeline for a user-picked episode,
stream stage-by-stage progress over a WebSocket as it actually happens (real wall-clock
pacing, not faked), then score the final diagnosis against that episode's held-out
`injected_events`.

**Status:** Built (first slice). See
`docs/02-stage-design-reports/api-backend-orchestration-and-verification-design.md` and
`.claude/plans/api-backend-orchestration-and-verification.md`.

## Endpoints

- `GET /episodes` — every episode id, no pre-filtering
- `POST /runs?episode_id=&use_llm=` — starts a background run, returns `{run_id}`
- `WS /ws/runs/{run_id}` — one JSON event per stage as it completes, ending in a
  `verification` event
- `GET /runs/{run_id}` — the full transcript, works after the socket has closed

Full contract in the design report.

## Known real constraints (stated, not hidden)

- Stage 6 evidence is real for episode 15 only — every other episode legitimately
  retrieves zero evidence (764,537 other `support_tickets.text` rows are `NULL`).
- Not every episode produces a story — Stage 2 may decline, or Stage 3 may find no
  cross-KPI cluster. The run terminates cleanly after one `no_cluster` event; this is a
  correct outcome, not a failure (see `orchestrator.py`).
- `counterfactual_mae` is always `None` in this slice — no code anywhere in this repo
  re-derives Layer 1's true counterfactual with an injected event suppressed. A stated
  gap against `docs/01-architecture/architecture-report.md` §9's full metric table, not
  a fabricated placeholder.
- `run_store.py` is in-memory only — a backend restart loses all run history.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_sm
.venv/bin/python test_backend.py     # must print OK
.venv/bin/uvicorn main:app --reload  # serve it
```
