# Frontend — Live Pipeline UI (Phase 0: backend enrichment, Phase 1: Next.js + GSAP)

**Design report:** `docs/02-stage-design-reports/frontend-live-pipeline-ui-design.md`
**Design canvas:** https://claude.ai/code/artifact/0a0dc2c2-0611-4599-a9eb-a8c665acf90e
**Branch:** `feature/frontend-live-pipeline-ui` (off `develop`) — Phase 0 and Phase 1 can
land as one branch or two; Phase 0 is small enough not to need its own PR unless
review wants it isolated.
**Consumes:** `backend/orchestrator.py`, `backend/main.py`,
`pipeline/stage08_counterfactual_impact/reconstruction.py`'s `reconstruct_points`

## Outcome

Phase 0: the same live episode-15 run that already passes `test_backend.py` now emits
richer `stage7`/`stage4`/`stage8` events — a full ranked hypothesis list, real top
slices, a real per-day observed/counterfactual series — with zero change to control
flow or existing fields (purely additive, so `test_backend.py`'s existing assertions
still hold). Phase 1: `npm run dev` serves `/run/[episodeId]`, and driving a real
episode through it renders all six canvas moments in sequence, each animated by GSAP
off the real WebSocket events, ending in the verdict.

## Phase 0 — Backend payload enrichment

### Files to read first

- `docs/02-stage-design-reports/frontend-live-pipeline-ui-design.md`'s "Real gaps"
  section — the four specific enrichments, already scoped
- `backend/orchestrator.py` — every `yield` site that needs a richer `summary`
- `pipeline/stage07_hypothesis_debate_ranking/models.py` — `RankedHypothesis`'s real
  fields (`member_causes`, `confidence_bucket`, `rank`, `evidence_count`,
  `independent_source_count`)
- `pipeline/stage08_counterfactual_impact/models.py` — `CounterfactualImpact.trajectory`
  and `CounterfactualPoint`'s exact fields (already confirmed real and populated,
  built by `stage8.py`'s own `_estimate_one` via `reconstruction.reconstruct_points`) —
  this is what step 3 below serializes, not new computation
- `pipeline/stage11_narration/narrate.py`'s `build_fact_sheet()` — the existing
  top-slices selection pattern (`sorted by |deviation_pct| descending, capped`) to
  mirror for Stage 4's event

### Implementation steps

1. **Stage 7 event — full ranked list.** In `orchestrator.py`'s `stage7` yield, add
   `"hypotheses": [{"hypothesis_id": h.hypothesis_id, "member_causes": h.member_causes, "confidence_bucket": h.confidence_bucket, "rank": h.rank, "evidence_count": h.evidence_count} for h in stage7_result.hypotheses]`
   alongside the existing fields (don't remove `hypothesis_count`/`top_hypothesis_id` —
   additive only). Test: offline, a fake `Stage7Result` with 4 hypotheses yields all 4
   in the event, in whatever order `stage7_result.hypotheses` already carries (the
   frontend sorts by `rank` itself, matching `backend/verification.py`'s own existing
   sort-defensively pattern).

2. **Stage 4 event — real top slices.** Add a `top_slices` list to the `stage4` yield,
   same selection as `narrate.py`'s `build_fact_sheet` (`OBSERVED` slices only, sorted
   by `|deviation_pct|` descending, capped at 5): `{kpi_name, dimension, slice_value, deviation_pct, eligibility}`
   per slice. Test: offline fixture with mixed `OBSERVED`/`NO_DATA_IN_WINDOW` slices —
   assert the unmeasured ones are excluded and the cap holds.

3. **Stage 8 event — expose the already-computed trajectory.** `Stage8Result.estimates[i].trajectory`
   (a `List[CounterfactualPoint]`) already has exactly the real per-day series the
   counterfactual chart needs — checked directly against `models.py`, not assumed. No
   new module, no bridge extension: for each estimate with `estimation_status=="ESTIMATED"`,
   add `"trajectory": [{"day_offset": p.day_offset, "observed_value": p.observed_value, "baseline_value": p.baseline_value, "counterfactual_value": p.counterfactual_value, "estimated_impact": p.estimated_impact} for p in estimate.trajectory]`
   keyed by `hypothesis_id` in the `stage8` event's summary (all estimated hypotheses,
   not just one — Stage 8's event fires before Stage 9 decides which is primary, so
   the frontend picks the right trajectory once it sees the `stage9` event's
   `hypothesis_id`, rather than the backend guessing ahead of time which one "the"
   chart is for). `None` values in a point stay `None` — never fabricated, matching
   `reconstruct_points`'s own existing discipline. Test: offline fixture with a
   `MECHANISM_UNAVAILABLE` estimate (empty trajectory, excluded) alongside an
   `ESTIMATED` one (real trajectory, included) — assert only the estimated one appears.

4. **Stage 9 event — the chosen hypothesis's real impact numbers.** Add
   `expected_impact`/`impact_lower`/`impact_upper` from `primary_recommendation` to the
   `stage9` event's existing summary (alongside `action_type`/`primary_owner`) — this
   is the point in the real event sequence where "the chosen hypothesis" is actually
   known, so it belongs here, not duplicated onto Stage 8's earlier event.

### Tests and validation gate

```bash
cd backend
.venv/bin/python test_backend.py   # must still print OK -- new fields only, no removed ones
```

### Acceptance criteria

- [ ] `test_backend.py` still passes (additive changes only)
- [ ] Stage 7's event carries all ranked hypotheses, not just the top one
- [ ] Stage 4's event carries real top slices, not just a count
- [ ] Stage 4 and Stage 8's events carry a real per-day series — verified against the
      live episode-15 run's printed output, not just an offline fixture
- [ ] No fabricated/interpolated data point anywhere — a day with no real observed or
      baseline value stays `None`

## Phase 1 — Next.js + GSAP frontend

### Files to read first

- `docs/02-stage-design-reports/frontend-live-pipeline-ui-design.md` — full contract
- The design canvas — six moments, exact palette/type/motion intent
- `backend/main.py` — the real `WS /ws/runs/{run_id}` event shape (post-Phase-0)
- The canvas's `.dc.html` sources (read back via the Artifact tool if not still in the
  working tree) for exact color/type/spacing values to lift, not re-guess

### Files to create

```
frontend/
├── package.json              (next, react, gsap, tailwindcss)
├── app/
│   ├── layout.tsx             (fonts: Shippori Mincho, Work Sans, IBM Plex Mono via next/font/google)
│   ├── globals.css            (design tokens as CSS custom properties, lifted from the canvas)
│   ├── page.tsx                (episode picker -- moment 1)
│   └── run/[episodeId]/
│       └── page.tsx            (the live run page -- moments 2-6)
├── components/
│   ├── EpisodePicker.tsx
│   ├── FlowRail.tsx            (moment 2's compact always-visible node strip)
│   ├── StageDetail.tsx         (swaps between live-readout / debate / counterfactual / persona-fork / verdict)
│   ├── DebateView.tsx          (moment 3)
│   ├── CounterfactualView.tsx  (moment 4 -- real series from Phase 0)
│   ├── PersonaForkView.tsx     (moment 5)
│   └── VerdictView.tsx         (moment 6)
├── lib/
│   ├── useRunSocket.ts         (WebSocket hook: connects, accumulates events via useReducer, exposes the typed event stream)
│   └── animations/             (one GSAP timeline-builder function per moment transition -- kept out of components so a component stays about structure, not motion)
└── types/
    └── events.ts                (TypeScript types mirroring the Phase-0'd WS event shapes exactly -- generate/hand-write from backend/orchestrator.py's real yields, not guessed)
```

### Implementation steps

1. **Scaffold.** `npx create-next-app` (TypeScript, App Router, Tailwind, no `src/`
   dir to match this repo's flat convention). Add `gsap`. No state library (design
   report's stated choice).

2. **Design tokens.** `globals.css` custom properties lifted exactly from the canvas's
   authored hex values (`--paper`, `--paper-deep`, `--ink`, `--ink-muted`,
   `--ink-faint`, `--border`, `--accent`, `--accent-soft`) and the three font families
   via `next/font/google` (Shippori Mincho, Work Sans, IBM Plex Mono). Test: a
   throwaway page rendering all seven tokens as swatches, visually matches the canvas
   side by side, then delete the throwaway page.

3. **`useRunSocket.ts`.** Connects to `WS /ws/runs/{run_id}` (after a `POST /runs` on
   mount), accumulates events into an ordered array via `useReducer`, exposes
   `{events, latestByStage, isFinished}`. Pure data hook, no GSAP inside it — components
   read `events`/`latestByStage` and trigger their own animations off changes via
   `useEffect`. Test: a small mock WebSocket server (or MSW) feeding a canned event
   sequence, assert the reducer's accumulated state matches.

4. **`FlowRail.tsx` + `StageDetail.tsx`.** The persistent node strip (moment 2, GSAP
   pulse on the active node, flowing dash-offset on the completed line — same technique
   as the canvas's CSS keyframes, ported to GSAP for real control over timing relative
   to actual event arrival, not a fixed CSS loop). `StageDetail` swaps its child
   component based on `latestByStage`, using GSAP (or the free `Flip` plugin) for the
   transition between whichever view is showing.

5. **`DebateView.tsx`.** Renders the Stage 7 event's real hypothesis list (post
   Phase-0), sorted by `rank`, bar width proportional to rank position (not a
   fabricated "confidence score" — the design canvas already avoids implying a numeric
   confidence the backend doesn't have), GSAP stagger-settle on mount matching the
   canvas's `settle` keyframe intent.

6. **`CounterfactualView.tsx`.** Renders the real per-day series (Phase 0) as an SVG
   path pair (observed solid, counterfactual dashed-ghost), GSAP draws the ghost path
   via `stroke-dashoffset` on mount. A day with `null` values breaks the line rather
   than interpolating through it — the same "measured or not" honesty
   `reconstruct_points` already enforces has to survive into the chart, not get
   smoothed away by a naive SVG path.

7. **`PersonaForkView.tsx`.** Two cards from the real `stage10_11` event's narratives
   (already real text, no Phase-0 change needed), fork-line SVG draws in, text reveals
   line-by-line (GSAP `SplitText`-equivalent via a simple line-splitting utility, or
   the free `SplitText` plugin if bundle size allows).

8. **`VerdictView.tsx`.** The `verification` event's real result. `top1_hit`/
   `top3_hit === null` (no matching event in this window) renders as an honest
   "no real event overlapped this window" state, not a red X — that's a legitimate
   outcome (false-causality-rate signal), not a failure, matching the design report's
   own framing. The batch scorecard row stays the pending `—` state from the canvas —
   do not fabricate numbers to fill it before `GET /verification/batch` exists.

9. **`EpisodePicker.tsx`.** `GET /episodes`, renders the grid, `POST /runs` on
   selection, routes to `/run/[episodeId]`.

### Tests and validation gate

```bash
cd frontend
npm install
npm run dev   # manual: pick episode 15, watch the full run animate end to end
npm run build # must succeed with no type errors
```

No automated visual-regression suite in this slice (matches this project's established
"plain assert scripts, no heavy frameworks" testing philosophy — `useRunSocket`'s
reducer gets a unit test per step 3; the rest is verified by actually running it
against the real backend, the same "one live run at the end, not a diagnostic per
line" discipline every backend/pipeline stage in this repo already follows).

### Acceptance criteria

- [ ] `npm run build` succeeds
- [ ] A full live run of episode 15 renders all six moments in the real event order,
      driven entirely by real WebSocket data (no mocked/hardcoded stage content)
- [ ] The `no_cluster` early-terminate and zero-Stage-6-evidence states both render as
      honest, designed states — not a stuck spinner or a console error
- [ ] Every number on screen traces to a real backend field — no placeholder/sample
      data left in from the mockup phase

## Risks

- **GSAP's free-plugin status (DrawSVG-equivalent, Flip, SplitText) was true as of this
  session's research** (`shared/live-sources.md`-style caveat) — confirm current
  licensing at implementation time; a paid-plugin fallback (native `stroke-dashoffset`
  animation, which achieves the same visual result without the plugin) is documented
  in step 6 either way, so this risk has no hard blocker.
- **The batch verification scorecard stays visibly incomplete** (canvas moment 6's `—`
  row) until `GET /verification/batch` is built — stated scope, not silently dropped;
  worth a follow-up plan once someone wants to replay enough episodes to make that
  screen real.
