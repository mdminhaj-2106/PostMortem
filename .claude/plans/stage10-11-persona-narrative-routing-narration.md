# Stage 10 + 11 — Persona Narrative Routing & Narration (combined, first slice)

**Design report:** `docs/02-stage-design-reports/stage10-11-persona-narrative-routing-narration.md`
**Branch:** `feature/stage10-11-persona-narration` (off `develop`)
**Consumes:** Stage 3 (`StageThreeResult`), Stage 4 (`DecompositionResult`), Stage 9
(`Stage9Result`) — via a new bridge one layer past Stage 9's own `stage8_bridge.py`

## Outcome

For episode 15's real cluster, running `stage10.py --episode-id 15` replays the full
Stage 3→9 chain and produces two genuinely divergent narratives (executive, analyst)
from the identical fact sheet — the executive one stating a real action+owner from
Stage 9 or plainly saying none is available yet, the analyst one describing method,
confidence, and a next diagnostic step. `test_stage10.py` prints `OK`: one offline
invariant plus one live run against episode 15 that proves this end to end, not just
against hand-built fixtures.

## What's already done (prior session, this design pass formalizes it)

- `personas.py`: `EXECUTIVE`/`ANALYST` system prompts, `EXECUTIVE` branches on
  `recommendation` being null (finding #1 in the design report).
- `narrate.py`: `build_fact_sheet()` takes `recommendation_result` (Stage 9's
  `Stage9Result`), surfaces `decision_status`+`recommendation`, `None`-safe.
  `call_llm()` uses `google-genai` against `gemini-3.6-flash`.
- `stage11_bridge.py`, `stage3_bridge.py`: existing bridges, unchanged.
- `test_narrate.py`: 7 offline checks + 1 live Gemini call, passing.

This plan's new work is entirely the live full-chain wiring (design report's finding
#4) — nothing above needs to change.

## Files to read first

- `docs/02-stage-design-reports/stage10-11-persona-narrative-routing-narration.md`
- `pipeline/stage09_recommendation_assembly/stage9.py` — `run_stage9`'s real signature
  (`stage7_result, stage8_result, decomposition_result=None, flagged_facets_fn=None`)
  and its `main()`'s exact chain-driving shape (this plan's `stage10.py` mirrors it
  one stage further)
- `pipeline/stage09_recommendation_assembly/stage8_bridge.py` — the exact
  sys.path/sys.modules-eviction pattern and module-name list to mirror one layer
  deeper (`architecture.md`'s standing warning: hand-deriving a shorter eviction list
  risks yet another bare-module-name collision, already hit 7 times across this repo)
- `pipeline/stage09_recommendation_assembly/test_stage9.py`'s
  `test_live_stage9_episode_15` — the exact chain-calling sequence
  (Stage3→4→5a/5c→[5b]→6→7→8) to replicate one call further into Stage 9 and then
  Stage 10/11
- `pipeline/stage09_recommendation_assembly/requirements.txt` — the full transitive
  dependency list Stage 10's own requirements.txt must match (plus `google-genai`)

## Files to change/create

```
pipeline/stage10_persona_narrative_routing/
├── personas.py                (unchanged)
├── stage11_bridge.py          (unchanged)
├── stage9_bridge.py           (NEW -- re-exports run_stage9 + Stage 9's own
│                                re-exported Stage 3-8 chain, one layer deeper
│                                than stage9's own stage8_bridge.py)
├── stage10.py                 (NEW -- run_stage10() wrapping narrate_for_all_personas
│                                + CLI main() replaying the full chain)
├── test_stage10.py            (NEW -- offline invariant + live episode-15 run)
└── requirements.txt           (UPDATED -- full transitive chain + google-genai)

pipeline/stage11_narration/    (no changes -- already fixed/verified)
```

## Implementation steps

1. **`stage9_bridge.py`.** Mirror `stage09_recommendation_assembly/stage8_bridge.py`
   exactly: `_STAGE9_DIR` points at `../stage09_recommendation_assembly`;
   `_STAGE9_MODULE_NAMES` covers every file actually present in that directory
   (`models`, `config`, `mechanism_resolver`, `lever_resolver`, `action_builder`,
   `owner_resolver`, `feasibility`, `intent_resolver`, `monitoring`,
   `success_criteria`, `selection`, `output_schema`, `stage9`, `stage8_bridge`) — the
   full list, not just what `stage9.py` imports at its own top level, since its
   transitively-imported submodules (`action_builder.py` etc.) import several of
   these internally and any one left off risks a bare-name collision the same way
   Stage 7/8's `stage4_bridge` collision happened. Import both `stage9` and
   `stage8_bridge` from that one `sys.path` insertion (mirrors `stage8_bridge.py`
   importing both `stage8` and `stage7_bridge` together). Re-export: `run_stage9`,
   `run_stage8`, `run_stage7`, `run_stage3`, `run_stage4`, `run_stage5a_and_5c`,
   `load_reference`, `should_fork`, `run_stage5b`, `run_stage6`, `flagged_facets`.
   Test: import succeeds, every re-exported name is callable — no DB needed for this
   check alone.

2. **`stage10.py`.** `run_stage10(stage3_result, decomposition_result=None,
   recommendation_result=None, use_llm=True)` is a thin wrapper around
   `personas.narrate_for_all_personas` (same signature, same return shape) — exists
   as its own named entrypoint only so this stage has the same `stageN.py`-as-
   orchestrator shape every other stage has, not because the wrapping logic is
   nontrivial. `main()`: argparse `--episode-id` (+ `--no-llm` to run the fact-sheet-
   only guardrail path against a real episode, useful for a cheap smoke check), lazily
   `import stage9_bridge` inside `main()` (matching Stage 9's own lazy import of
   `stage8_bridge` inside its `main()` — this project's established pattern for a
   CLI-only bridge import that never needs to survive being called from another
   process context), replay the exact chain from `test_stage9.py`'s
   `test_live_stage9_episode_15` one call further (add the `run_stage9` call using
   `stage3_result`/`decomposition_result`/`stage7_result`/`stage8_result` already in
   hand), then call `run_stage10(...)` and print both personas' narratives (or fact
   sheets, if `--no-llm`) plus token usage.

3. **`test_stage10.py`.** Offline: `narrate_for_all_personas` against a small fake
   `StageThreeResult`-shaped object with `use_llm=False` — assert the result dict's
   keys are exactly `{"executive", "analyst"}` and both personas received the
   identical `fact_sheet` (design report's stated requirement: same underlying
   finding, only the prompt differs). Live: `test_live_stage10_11_episode_15()`
   replicates `test_stage9.py`'s `test_live_stage9_episode_15` chain verbatim through
   Stage 9, then calls `narrate_for_all_personas(stage3_result, decomposition_result,
   stage9_result, use_llm=True)` — assert both narratives are non-empty, both have
   real token usage, and `exec_text != analyst_text` (this is the real test: on real
   pipeline output, not the hand-built fixture already covered in
   `stage11_narration/test_narrate.py`). Print `decision_status` and both narratives
   for visual sanity, same as every other stage's live test.

4. **`requirements.txt`.** Copy Stage 9's full list (`psycopg2-binary`,
   `python-dotenv`, `numpy`, `sentence-transformers`, `spacy`, `vaderSentiment` — all
   needed transitively through `stage9_bridge.py`'s own chain into Stage 6's
   `embedding_index.py`) plus `google-genai` (Stage 11's own dependency, now
   triggered live from Stage 10's process). Keep the `python -m spacy download
   en_core_web_sm` post-install comment Stage 9's file already has.

## Tests and validation gate

```bash
cd pipeline/stage10_persona_narrative_routing
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_sm
.venv/bin/python test_stage10.py     # must print OK: offline invariant +
                                      # one live Stage 3->4->5a/5c->[5b]->6->7->8->9->10/11
                                      # run, episode 15
```

## Acceptance criteria

- [ ] `test_stage10.py` prints `OK`
- [ ] `narrate_for_all_personas` returns exactly `{"executive", "analyst"}` and both
      receive the identical fact sheet
- [ ] The live episode-15 run's two narratives are non-empty and different from each
      other (not just different in length)
- [ ] Neither narrative says "correlation" for the KPI co-movement evidence (already
      enforced by the shared constraints block, re-verified against real Stage 3
      output here, not just a fixture)
- [ ] The executive narrative states the real Stage 9 `primary_owner`/`action_type`
      when `decision_status=="RECOMMENDATION_AVAILABLE"`, and plainly states no
      action is available otherwise — never a fabricated one either way
- [ ] `stage10_persona_narrative_routing/README.md` updated off its stale "Not yet
      designed / no code yet" text
- [ ] `.claude/reference/architecture.md`'s Stage 10-11 row updated from `❌ / ❌`

## Risks

- **Whatever episode 15's real Stage 9 run currently returns drives what this stage
  can prove.** If it lands on `NO_DEFENSIBLE_ACTION` (plausible — Stage 8's README
  states most hypotheses are `MECHANISM_UNAVAILABLE`), the live test proves the
  abstention branch works but not the "real action + owner" branch. Not a blocker —
  both branches already have dedicated offline coverage in
  `stage11_narration/test_narrate.py`; the live run's job is proving the *real* chain
  reaches Stage 10/11 correctly, whichever branch it lands on.
- **A ninth cross-import wrinkle is plausible.** Eight bridge-related collisions are
  already documented in `architecture.md`'s Known Architectural Risks; a bridge one
  layer past Stage 9 is the deepest chain yet (Stage 10 → 9 → 8 → 7 → 6/5b/5a/4/3).
  Mirror the eviction-list discipline exactly (step 1) rather than hand-deriving a
  shorter list.
- **Heavy transitive install** (`sentence-transformers`, `spacy` + model download) for
  a stage whose own code needs none of it directly — inherent to reusing the existing
  bridge chain rather than re-deriving a lighter-weight path into Stage 3/4 data
  directly. Accepted: matches how every downstream stage since Stage 6 has grown its
  own venv.
- **Security & Access Filter and Decision Rights enforcement are explicitly out of
  scope** (design report findings #1-2) — if a reviewer expects Stage 10's README's
  stated dependency on Security & Access Filter to mean real gating logic exists, this
  plan does not deliver that; it's declared, not hidden.
