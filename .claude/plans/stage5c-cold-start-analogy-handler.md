# Plan: Stage 5c — Cold-Start / Analogy Handler

**Design report:** `docs/02-stage-design-reports/stage5c-implementation-plan.md` — **superseded on its central mechanism, not just style; read this plan's Risk #1 before that doc.** That doc's golden example (Product A thin, Product B/North/Enterprise solid, all in one cluster, borrowing via a declared `analogy_groups.yaml` pairing) assumes per-slice-value eligibility variation within one decomposition run. Tracing the real code (`stage04_dimensional_decomposition/eligibility.py` + `decomposer.py` + `slice_fetcher.py`) shows this is structurally unreachable: `eligibility` depends only on `day_range = range(max(0, window_start-30), window_end+1)` — a property of the cluster's window alone — so every `slice_value` of a given `(kpi_name, dimension)` in one decomposition run lands the *same* eligibility tier together (Stage 4's own README already found this live for region slices; this plan confirms it's not incidental, it's how `assess_eligibility`'s `n_usable` count is computed). What's still correct and worth keeping from the design doc: borrowing a *relative* (%) deviation distribution and scoring the thin slice's own deviation against it via the reused percentile mechanism (§4), never merging `BORROWED` results into Stage 5a/5b's native-confidence numbers (§6), and abstaining rather than guessing when no reference exists (§9's edge case, generalized here). **User decision (2026-08-30, in place of the doc's declared Product-A→B pairing):** the analog is the *same* slice, sourced from other episodes' mature history — a cross-episode corpus reference distribution per `(kpi_name, dimension, slice_value)`, built offline once, same pattern as Stage 5b's `basis/build_bases.py`. No declared YAML, no per-slice team decision required to ship the MVP.

**Priority:** parallel to Stage 6+ (not on Stage 5a→5b's critical path — Stage 5c is Stage 4's *other* consumer, alongside 5a). Depends only on Stage 4 (merged, PR history: 76813cf/746db70) and Stage 2's reused layers.
**Branch:** `feature/stage5c-cold-start-analogy-handler` off `develop`.
**Track:** `stage5c-cold-start-analogy-handler`.

## A finding this plan surfaces (verified against real code + live data, not assumed)

`eligibility.py`'s `assess_eligibility` computes `n_usable` from the timeline's `day_range`, which `decomposer.py` sets identically (`window_start - 30 → window_end`) for *every* `(kpi_name, dimension, slice_value)` combination in a single `decompose_cluster` call — the same window bounds come from one `stage3_result`. Live-confirmed instance (from Stage 4's README, re-derivable): episode 1, `active_customers_purchased_30d`, window `day_offset` 9–14 — **every** region slice (`SP`, the near-empty `AP`, everything) lands `LIMITED_HISTORY` together, `unusualness_percentile: None`. All 150 live episodes are `n_days=120` (confirmed via `SELECT MIN(n_days), MAX(n_days), COUNT(*) FROM episodes` → `120, 120, 150`), so a slice's own history matures (crosses `MIN_OBSERVATIONS_FOR_ELIGIBLE=30`) at the same in-episode day regardless of which slice_value it is.

**Consequence for scope:** the design doc's "mixed cluster" invocation mode (some slices solid, one thin, both routed in parallel) does not correspond to anything Stage 4 can actually produce. Stage 5c's real trigger is cluster-level: an early-window cluster makes the *whole* relevant `(kpi, dimension)` slate `LIMITED_HISTORY`/`INSUFFICIENT_DATA` together. The implementation below doesn't hardcode that as a branch, though — it just filters `DecompositionResult.slices` by each slice's own `eligibility` field, so it stays correct even if this uniformity ever stops holding (e.g. a future Layer 2 change reintroduces genuine per-slice sparsity) without needing a rewrite.

## Outcome (testable)

Given Stage 4's real episode-1 `active_customers_purchased_30d` window-9–14 decomposition (every region slice `LIMITED_HISTORY`, `deviation_pct` present, `unusualness_percentile: None`), Stage 5c emits one `BorrowedAttribution` per thin slice: a `borrowed_percentile` computed by scoring that slice's own `deviation_pct` against a corpus-wide reference distribution of the *same* slice_value's mature (`day_offset >= 30`) relative deviations pooled across other episodes, `confidence_tier="BORROWED"`, and `analog_source="CROSS_EPISODE_CORPUS"` — or, when no episode in the reference corpus ever observed that exact `(kpi_name, dimension, slice_value)` maturely, an honest `NO_REFERENCE_AVAILABLE` status instead of a fabricated number. Reuses Stage 2's real `score_unusualness` for the percentile, never reimplements it.

## Scope

**In (first implementation slice):**
- **Offline reference builder** (`reference_builder.py`): scans a bounded sample of episodes (`--n-episodes`, default 20 — same time-budget reasoning as Stage 5b's `--n-per-cause 5`), and for each `(kpi_name, dimension, slice_value)` reachable via Stage 4's own `dimension_config.DIMENSION_APPLICABILITY` + `slice_fetcher.distinct_slice_values`, computes that slice's full-episode residual series (`stage2_bridge.compute_residuals` over `day_range(0, n_days)`) and collects `residual/expected` for every `day_offset >= MIN_OBSERVATIONS_FOR_ELIGIBLE` (30) where `expected != 0` — i.e. exactly the days that would independently land `ELIGIBLE` if that day were itself a window end. Pools these samples across all sampled episodes into one artifact.
- **Artifact:** `reference/artifacts/reference.json` — plain JSON (no `joblib`/`scipy`, same as Stage 5b), `{"revenue|region|SP": {"samples": [...], "n": 743}, ...}`. Committed to git (matches Stage 5b's `basis/artifacts/bases.json` precedent).
- **`borrowed_percentile.py`** — the core function: given a thin slice's `deviation_pct` and its reference sample list, builds a synthetic `residuals`-shaped list (`[(0, None, s) for s in reference_samples] + [(1, None, deviation_pct)]`, order only matters for the final entry) and calls `stage2_bridge.score_unusualness` on it, returning the last entry's score — the exact function Stage 2/4/5a all already reuse, just handed a borrowed reference list instead of the slice's own causal history. Returns `None` if `reference_samples` is empty (no fabrication).
- **`models.py`** — `BorrowedAttribution` (`kpi_name`, `dimension`, `slice_value`, `deviation_pct`, `borrowed_percentile: Optional[float]`, `reference_sample_count: int`, `analog_source` fixed to `"CROSS_EPISODE_CORPUS"`, `confidence_tier` fixed to `"BORROWED"`, `status` — `"BORROWED"` or `"NO_REFERENCE_AVAILABLE"`) with `__post_init__` enums, matching this project's established flattened-dataclass style (Stage 4/5a/5b's `models.py`). `Stage5cResult` (`episode_id`, `cluster_id`, `attributions: List[BorrowedAttribution]`).
- **`stage4_bridge.py`** — re-exports Stage 4's `run_stage4`, `dimension_config`, `slice_fetcher`, `models` (same `sys.path`/`sys.modules`-eviction pattern as Stage 5a/5b's own `stage4_bridge.py`).
- **`stage2_bridge.py`** — re-exports Stage 2's `compute_residuals`, `score_unusualness` directly (same pattern as Stage 4's own `stage2_bridge.py`, one level over — bridges straight to Stage 2, not through Stage 4, matching every other stage's "bridge to what you actually need" convention).
- **`output_schema.py`** — rejects free text outside `{"BORROWED", "NO_REFERENCE_AVAILABLE"}` / `"CROSS_EPISODE_CORPUS"`, asserts `borrowed_percentile is None` iff `status == "NO_REFERENCE_AVAILABLE"`.
- **`stage5c.py`** — `run_stage5c(cur, episode_id, decomposition_result, reference) -> Stage5cResult`: filters `decomposition_result.slices` to `eligibility in ("LIMITED_HISTORY", "INSUFFICIENT_DATA")` and `deviation_pct is not None`, looks up each in `reference`, emits one `BorrowedAttribution` per thin slice (never merged with Stage 5a's `FingerprintResult` — separate output, forwarded alongside it per the design doc's still-valid §6 rule). CLI entrypoint loads `reference.json`, re-derives a `DecompositionResult` via `stage4_bridge.run_stage4` for a given `--episode-id`.
- **Output contract (→ Stage 6/7):** `models.Stage5cResult` — kept structurally separate from Stage 5a's `FingerprintResult`/Stage 5b's `ConfoundedAttributionResult`; a `confidence_tier="BORROWED"` value that Stage 7 (not yet built) will need to cap below `Known`/`Likely` when it exists — stated as a downstream contract note, not built here (design doc §6's note, carried forward).

**Out (this slice — explicit non-goals):**
- **Declared `analogy_groups.yaml` / per-slice-value analog pairing** — dropped per the user's 2026-08-30 decision above; the cross-episode corpus mechanism covers the real (only reachable) cold-start pattern without it. Not deferred-for-later — actively wrong given how eligibility actually works, so not scaffolded "for a future team decision" either.
- **Cause-prior borrowing (design doc §5)** — stretch goal per the doc, unchanged: depends on the Learning & Memory cross-cutting service, which has zero code (`pipeline/cross_cutting/learning_memory/` is a README only). Not attempted.
- **"Mixed cluster, both 5a and 5c run on different slices of the same decomposition" as a special code path** — not needed; `run_stage5c`'s per-slice `eligibility` filter already produces the right output whether the real data ever actually mixes or not (see the finding above). No mode flag, no router change.
- **Any change to Stage 5a's own router/README claims about a live `BRANCH_5C_COLD_START` destination** — out of scope for this branch; Stage 5a is already merged. If Stage 5a's own maintainers want to wire an explicit dispatch to Stage 5c, that's a Stage 5a change, noted here only as a cross-stage FYI.
- **Weighting/decaying older episodes in the reference corpus, outlier trimming, or any non-trivial statistics beyond a pooled percentile rank** — `score_unusualness`'s existing rank-based percentile is the same mechanism used everywhere else in this project; a fancier reference-distribution model is real over-engineering for a hackathon prototype's borrowed-signal use case.
- FastAPI wiring — same phased-build reasoning as Stages 1–5b.

## Files to read first

1. `docs/02-stage-design-reports/stage5c-implementation-plan.md` — still useful for the percentile-borrowing mechanism (§4) and the output-contract rules (§6, §9); **do not trust §3's declared-analog mechanism or the "mixed cluster" framing in §1** (this plan's header explains why).
2. `pipeline/stage04_dimensional_decomposition/eligibility.py` (actually `stage02_significance_detection/eligibility.py`, re-exported) — `MIN_OBSERVATIONS_FOR_ELIGIBLE=30`/`MIN_OBSERVATIONS_FOR_LIMITED=10`/`MAX_DEGRADED_FRACTION=0.3`, the real thresholds driving the uniformity finding.
3. `pipeline/stage04_dimensional_decomposition/decomposer.py` — confirms `day_range` is window-derived only, not slice-derived; also where `deviation_pct` is computed even for `LIMITED_HISTORY` slices (only `unusualness_percentile` is nulled) — this plan's `borrowed_percentile.py` fills exactly that gap.
4. `pipeline/stage02_significance_detection/unusualness.py` — `score_unusualness`, the function this plan reuses via the synthetic-residuals-list trick (§4 below).
5. `pipeline/stage05b_confounded_cause_decomposer/basis/build_bases.py` and its `models.py`/`output_schema.py` — the direct structural precedent (offline JSON artifact builder + flattened dataclass + free-text-rejection validator) this plan's `reference_builder.py`/`models.py`/`output_schema.py` mirror.
6. `pipeline/stage04_dimensional_decomposition/dimension_config.py`, `slice_fetcher.py` — the real `DIMENSION_APPLICABILITY` dict and `distinct_slice_values`/`load_slice_timeline` signatures `reference_builder.py` and `stage5c.py` both call through `stage4_bridge.py`.
7. `.claude/reference/architecture.md`'s Known Risks — the stacked-cross-stage-import pattern (`sys.path`/`sys.modules`-eviction); Stage 5c adds a seventh.

## Files to create

```
pipeline/stage05c_cold_start_analogy_handler/
  README.md                — update from "no code yet" to real status
  requirements.txt         — psycopg2-binary, python-dotenv (no numpy needed — plain list/rank math)
  models.py                — BorrowedAttribution + Stage5cResult dataclasses
  stage2_bridge.py         — re-exports Stage 2's compute_residuals, score_unusualness
  stage4_bridge.py         — re-exports Stage 4's run_stage4, dimension_config, slice_fetcher, models
  borrowed_percentile.py   — the core borrow-and-score function (§4 of the design doc, corpus-sourced)
  reference_builder.py     — offline: scans episodes, writes reference/artifacts/reference.json
  reference/artifacts/reference.json   — committed corpus artifact (like Stage 5b's bases.json)
  output_schema.py         — free-text-field rejection + status/percentile consistency check
  stage5c.py               — orchestrator (run_stage5c) + CLI entrypoint
  test_stage5c.py           — offline + live-DB checks
```

## Implementation steps

1. **`stage2_bridge.py`** — mirror Stage 4's own bridge exactly (`sys.path` insert + `sys.modules`-eviction over `models`/`ingest`/`baseline`/`eligibility`/`unusualness`/... ), re-export `compute_residuals` and `score_unusualness`. *Validation:* import in isolation, confirm no collision with this stage's own `models.py`.

2. **`stage4_bridge.py`** — mirror Stage 5a/5b's own `stage4_bridge.py` exactly, re-export `run_stage4`, `dimension_config`, `slice_fetcher`, `models`. *Validation:* same isolated-import check.

3. **`models.py`** — `BorrowedAttribution` per the Scope section's field list, `__post_init__` validating `status in ("BORROWED", "NO_REFERENCE_AVAILABLE")`, `analog_source == "CROSS_EPISODE_CORPUS"`, and the `borrowed_percentile is None ⟺ status == "NO_REFERENCE_AVAILABLE"` invariant (same pattern as Stage 4's `SliceResult.__post_init__` coupling `observation_status` to `expected`/`observed` nullness). `Stage5cResult` as a flat list wrapper. *Validation:* instantiate both valid and invalid combinations by hand, confirm `ValueError` on the mismatched cases.

4. **`reference_builder.py`** — `build_reference(cur, n_episodes) -> dict`: pick `n_episodes` real episode_ids (`SELECT episode_id FROM episodes ORDER BY episode_id LIMIT %s` — no need for injected-event filtering here, unlike Stage 5b's basis-builder, since this isn't learning a cause fingerprint, just a background volatility distribution); for each episode, for each `kpi_name` in `stage4_bridge.dimension_config.DIMENSION_APPLICABILITY`, for each `dimension` in `applicable_dimensions(kpi_name)`, for each `slice_value` in `distinct_slice_values(cur, episode_id, dimension)`: fetch `load_slice_timeline(cur, episode_id, kpi_name, dimension, slice_value, range(0, n_days))`, run `compute_residuals`, collect `residual/expected` for `day_offset >= 30` where `expected not in (None, 0)` and `residual is not None`. Pool into `{f"{kpi}|{dimension}|{slice_value}": {"samples": [...], "n": count}}`, write to `reference/artifacts/reference.json`. CLI: `python reference_builder.py --n-episodes 20`. *Validation:* run it live, confirm the artifact has a non-trivial sample count for at least `revenue|region|SP` (the known-dense case from Stage 4's README) and a real key exists for `active_customers_purchased_30d|region|AP` (the known-thin one) — this directly cross-checks against Stage 4's already-documented live findings instead of guessing.

5. **`borrowed_percentile.py`** — `score(deviation_pct, reference_entry) -> Optional[float]`: if `reference_entry` is `None` or its `samples` list is empty, return `None`. Else build `synthetic = [(i, None, s) for i, s in enumerate(reference_entry["samples"])] + [(len(reference_entry["samples"]), None, deviation_pct)]`, call `stage2_bridge.score_unusualness(synthetic)`, return the last tuple's score. *Validation:* hand-computable offline case — a reference list of `[0.01]*90 + [0.30]*10` (i.e. a distribution that rarely swings past 30%), fed a `deviation_pct=-0.21`; confirm the returned percentile lands materially high (matches the design doc's worked-example intuition, ≥0.85, without needing the specific Product A/B numbers since those no longer apply).

6. **`output_schema.py`** — `validate(stage5c_result)`: walks `attributions`, asserts `status`/`analog_source`/`confidence_tier` are declared enum members, and the percentile/status coupling from step 3 (belt-and-suspenders with `__post_init__`, matching Stage 4/5b's own dual validation). *Validation:* one clean case, one deliberately-broken case (mismatched status/percentile) rejected.

7. **`stage5c.py`** — `run_stage5c(cur, episode_id, decomposition_result, reference) -> Stage5cResult`: filter slices per the Outcome section, build one `BorrowedAttribution` per thin slice via `borrowed_percentile.score`, wrap in `Stage5cResult`. CLI: `--episode-id`, loads `reference.json`, calls `stage4_bridge.run_stage4` to get a real `DecompositionResult`, prints the result. *Validation:* live run against episode 1 (the README's `active_customers_purchased_30d`, window 9–14 case) — confirm at least one `BorrowedAttribution` comes back with `status="BORROWED"` and a real percentile, not just abstentions.

## Tests and validation gate

`test_stage5c.py` (offline + one live-DB end-to-end run, matching this project's `test_<name>.py` convention — no pytest):

- **Offline:** `BorrowedAttribution.__post_init__` rejects an invalid `status`, rejects `borrowed_percentile` set alongside `status="NO_REFERENCE_AVAILABLE"`, and rejects a missing `borrowed_percentile` alongside `status="BORROWED"`.
- **Offline:** `borrowed_percentile.score` returns `None` for an empty reference list (abstention, not a fabricated 0.5).
- **Offline:** `borrowed_percentile.score`'s hand-computable case (step 5's validation) — assert the returned float is within a known range.
- **Offline:** `output_schema.validate` rejects a free-text `status`/`analog_source` and the percentile/status mismatch.
- **Live:** build a small reference (`reference_builder.build_reference(cur, n_episodes=5)` — cheap subset, not the full committed artifact, to keep the test fast) against a real Neon connection; run `run_stage5c` against episode 1's real Stage 4 output for `active_customers_purchased_30d` window 9–14; assert every resulting `BorrowedAttribution` for a region slice with real reference coverage has `status="BORROWED"` and `0.0 <= borrowed_percentile <= 1.0`.
- **Edge case:** a thin slice whose `(kpi, dimension, slice_value)` key never appears in the reference (e.g. a `slice_value` that's genuinely rare across the whole corpus, or query the built reference for a key you know is absent) → `status="NO_REFERENCE_AVAILABLE"`, `borrowed_percentile is None` — asserted explicitly, not left to hope.
- **Edge case:** a `DecompositionResult` with no `LIMITED_HISTORY`/`INSUFFICIENT_DATA` slices at all (a mature-window cluster) → `Stage5cResult.attributions == []`, no crash, nothing fabricated.

Gate: `.venv/bin/python test_stage5c.py` must print `OK`.

## Acceptance criteria

- [ ] `reference_builder.py` runs live against real Neon data and produces `reference/artifacts/reference.json`, committed.
- [ ] `run_stage5c` on episode 1's real `active_customers_purchased_30d` window-9–14 decomposition (Stage 4's own documented `LIMITED_HISTORY` case) returns at least one non-abstained `BorrowedAttribution`.
- [ ] No slice ever gets a fabricated `borrowed_percentile` when its reference is empty — abstention is structural (`__post_init__` + `output_schema.validate`), not incidental.
- [ ] Stage 5c's output is never merged with Stage 5a's `FingerprintResult` or Stage 5b's `ConfoundedAttributionResult` in any code path.
- [ ] `test_stage5c.py` prints `OK` (offline + live).
- [ ] `README.md` updated with real status, output contract, and the eligibility-uniformity finding (matching Stage 4/5a/5b's own README style — state deviations from the design doc plainly, don't hide them).
- [ ] `.claude/reference/architecture.md`'s Stage 5a–11 row updated to reflect Stage 5c's real status.

## Risks

- **Corpus coverage gaps:** a `(kpi_name, dimension, slice_value)` combination genuinely rare across the sampled `--n-episodes 20` (e.g. a product category that happens to have near-zero mature-day residual variance, or a region that's empty in most episodes) may yield a `NO_REFERENCE_AVAILABLE` more often than the design doc's confident-borrow framing implies. This is the honest outcome, not a bug — widening `--n-episodes` (up to the full 150) is the direct lever, same as Stage 5b's `--n-per-cause` note, not attempted here given time budget.
- **A seventh stacked cross-stage import** (Stage 5c → Stage 2 directly, Stage 5c → Stage 4 → Stage 2 for the CLI/reference-builder paths) via the `sys.path`/`sys.modules`-eviction pattern. `architecture.md`'s Known Risks already called a real package overdue at the fourth stage; unchanged conclusion, not folded into this slice.
- **Downstream contract not yet enforced:** Stage 7 (hypothesis debate, not yet built) is where `confidence_tier="BORROWED"` is supposed to get structurally capped below `Known`/`Likely`. Nothing in this slice enforces that — it's a note for whoever builds Stage 7, same as the design doc already flagged.
- **Stage 5a's README currently states Stage 5c "doesn't exist"** — once this lands, Stage 5a's README's "Deferred, not implemented" section is stale and should be corrected in a small follow-up (not bundled into this branch, to keep the diff scoped to Stage 5c only).
