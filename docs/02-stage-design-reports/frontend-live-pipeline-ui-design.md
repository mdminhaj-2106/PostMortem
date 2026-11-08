# Frontend — Live Pipeline UI (design report)

Design canvas (visual language, six key moments):
https://claude.ai/code/artifact/0a0dc2c2-0611-4599-a9eb-a8c665acf90e

## Visual system (committed, not open)

Warm, Japanese-restraint-inspired minimalism — `ma` (negative space as an active
element), muted washi-paper warmth, one deliberate accent, typographic quietness. No
gradients-as-decoration, no emoji, no rounded-card-with-left-border-accent cliché.

- **Palette**: paper `#F6F1EA`, paper-deep `#EFE8DD`, ink `#2B2521`, ink-muted `#6B6156`,
  ink-faint `#A69B8C`, border `#E2D9CB`, accent (terracotta) `#B5533A`, accent-soft
  `#F1DCD2`. The accent is used ONLY for the significant thing — the active stage, the
  winning hypothesis, the verdict, a primary action. Everything else stays neutral so
  the accent still means something after ten minutes of looking at it.
- **Type**: Shippori Mincho (narrative/headlines), Work Sans (UI/body/labels), IBM Plex
  Mono (every number, every technical label — KPI ticks, confidence buckets, stage
  names). Three fonts, one job each, never mixed within a role.
- **Motion philosophy**: the six canvas artboards are captured *moments*, not the
  animation itself — GSAP owns the actual choreography between them. Each moment maps
  to a design principle, not decoration: the debate bars settle because Stage 7's
  resolution is real (not a random stagger for effect); the ghost line draws because
  the counterfactual is being *revealed*, not because drawing is pretty.

## The six moments -> real backend events

| Canvas artboard | Fires on WS event | What it needs from the payload |
|---|---|---|
| 1 — Episode picker | (page load) `GET /episodes` | episode ids only, as designed |
| 2 — The living current | every stage event, `stage3` through `stage9` | stage name/status (have it) + **a live readout per stage** (partially have it — see gaps) |
| 3 — Hypothesis debate | `stage7` | **the full ranked hypothesis list** (don't have it — see gaps) |
| 4 — Counterfactual reveal | `stage8` | **a real daily observed-vs-counterfactual series** (don't have it at all — see gaps) |
| 5 — Persona fork | `stage10_11` | both personas' narratives + usage (already have this, exactly as designed) |
| 6 — Ground-truth verdict | `verification` | matched_event_type/top1_hit/top3_hit (have it), counterfactual_mae (honestly `None`) |

## Real gaps against the current backend contract (Phase 0, before any frontend code)

Cross-checking the design canvas against `backend/orchestrator.py`'s actual event
`summary` payloads (not against what would be nice — against what a stage's real
result object already contains and just isn't being serialized out yet):

1. **Stage 7's event is too thin for the debate view.** Currently
   `{abstained, hypothesis_count, top_hypothesis_id}`. `stage7_result.hypotheses` already
   carries everything the debate visualization needs per hypothesis — `member_causes`,
   `confidence_bucket`, `rank`, `evidence_count`/`independent_source_count`. This is a
   pure serialization fix, no new computation: expose the ranked list capped at 4 (the
   real cause vocabulary size, so no cap is even usually reached).
2. **The counterfactual chart's real data already exists, fully computed — it just
   isn't serialized out.** `Stage8Result.estimates[i]` (a `CounterfactualImpact`)
   already carries `trajectory: List[CounterfactualPoint]`
   (`day_offset`/`observed_value`/`baseline_value`/`counterfactual_value`/
   `estimated_impact` per day, built by `reconstruction.reconstruct_points` inside
   `stage8.py`'s own `_estimate_one`) — this was checked directly against the model,
   not assumed. So this gap is a pure serialization fix (expose `trajectory` per
   estimate in the `stage8` event), not new computation. **No stage exposes a real
   daily series before Stage 8 runs** (Stage 3/4's results are window-aggregate only,
   not day-by-day) — the pipeline-flow micro-chart (moment 2) is scoped down
   accordingly: real aggregate numbers only during Stages 1-6, no sparkline chart
   until Stage 8's real trajectory exists. Building a separate daily-series fetch just
   for the flow view would be new, unjustified work for a moment the design doesn't
   strictly need a chart in.
3. **Stage 4's event drops the actual top slices.** `decomposition_result.slices`
   already has `kpi_name`/`dimension`/`slice_value`/`deviation_pct`/`eligibility` —
   exactly what moment 2's "live readout" panel shows. Currently discarded; expose the
   top 3-5 by `|deviation_pct|`, same selection logic `narrate.py`'s `build_fact_sheet`
   already uses for `top_slices`.
4. **Stage 8's event drops the winning hypothesis's own impact numbers.** Currently
   just a count. Expose `expected_impact`/`impact_lower`/`impact_upper` for the
   hypothesis Stage 9 ends up choosing (resolvable after Stage 9 runs, or the
   orchestrator can attach it to the Stage 9 event instead — implementation's call,
   not a design constraint).

None of this changes `orchestrator.py`'s control flow — it's exclusively about what
each stage's already-yielded event carries in `summary`. Scoped as its own phase
because it's real backend work (a new timeseries-reconstruction helper, specifically)
that has to land before the frontend can render real data instead of placeholders.

## Stack

- **Next.js (App Router, TypeScript)** — already the locked tech stack
  (`CONSTITUTION.md`).
- **GSAP** over anime.js — chosen for this specifically, not by default preference:
  the choreography needed (staggered debate-bar settling, SVG path drawing for the
  ghost line and the flowing current, coordinated multi-element sequencing between
  the six moments) is exactly GSAP's strength, and GSAP's plugins (DrawSVG-equivalent
  via native `stroke-dashoffset`, `Flip` for the flow-rail-to-detail-view transitions)
  are free since 2024 — no paid-plugin tradeoff to weigh anymore. anime.js is lighter
  (~28 KB vs GSAP core's ~50 KB) and would be the right call for a simpler
  fade/slide-only site; this isn't that site.
- **Tailwind CSS v4** for layout utilities, with the canvas's palette/type ramp as CSS
  custom properties (`--ink`, `--accent`, `--paper`, ...) — GSAP owns all real motion,
  Tailwind never reaches for `animate-*`.
- **No client-side state library.** One page (`/run/[episodeId]`), one WebSocket
  connection, a small `useReducer` accumulating events as they arrive — this is a
  single-consumer event stream, not shared app state; reaching for Zustand/Redux here
  would be solving a problem this page doesn't have.

## Interaction model

Not a long scroll page. A persistent, compact **flow rail** (moment 2's node strip,
shrunk) stays visible across the whole run, showing all 9 stages' status at a glance.
Below it, one **stage detail area** swaps its content as triggering events arrive:

- Stages 1-6 (except 7): the flow rail's live-readout panel (moment 2's right-hand
  numbers, per whichever stage just completed).
- Stage 7 completes → the detail area transitions (GSAP `Flip`) into the debate view.
- Stage 8 completes → transitions into the counterfactual reveal.
- Stage 10/11 completes → transitions into the persona fork.
- The `verification` event → the detail area's final resting state is the verdict.

This mirrors the real event order the backend actually emits — the UI is a direct
transcription of `orchestrator.py`'s yield sequence, not an invented navigation
structure layered on top of it.

## Scope

**In:** the six moments above, live-driven end to end for one episode at a time, the
Phase 0 backend enrichment, the `no_cluster`/zero-evidence honest states (design
report's own stated backend constraints — the frontend must render these as real
outcomes, not loading-forever or error states).

**Out (stated):** the batch verification scoreboard (canvas moment 6's pending-state
row — genuinely needs `GET /verification/batch`, which doesn't exist, per the backend
design report's own stated Scope/Out), multi-run history/comparison, auth, mobile
layout (this is a demo/analyst tool, not a consumer app — desktop-first is the honest
choice, not an oversight).
