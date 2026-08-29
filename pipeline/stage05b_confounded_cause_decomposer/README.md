# Stage 5b — Confounded-Cause Decomposer

**Job:** when Stage 5a's confidence is split between causes, decompose the observed movement itself into per-cause contributions (KPI units, non-negative, reconciling to the observed deviation) instead of forcing a top-1 pick. `P(cause)` (5a) is uncertainty about which one; `contribution share` (5b) is a decomposition of the movement itself — both true at once.

**Status:** First implementation slice built and passing (`test_stage5b.py`, offline + one live-DB end-to-end run). Importable Python functions + a CLI, no FastAPI wiring yet.

**Design report:** [`docs/02-stage-design-reports/stage5b-confounded-cause-decomposer-revised.md`](../../docs/02-stage-design-reports/stage5b-confounded-cause-decomposer-revised.md) — the mechanism (NNLS basis-fit attribution, declared + empirical identifiability gate, joint-bucket abstention) is followed; several scale parameters are cut down for time (see below), stated here rather than silently.

**Scope cuts from the design doc, stated plainly:**
- **Basis training set:** learns from 5 real single-event episodes per cause (+ 5 zero-event episodes for `seasonal`), not the full 56-single-event/54-zero-event set. `basis_sample_count` in the output still reports the real `n` either way, so nothing downstream has to guess how thin a basis is.
- **No `scipy`/`joblib` dependency:** a ~20-line active-set NNLS in plain `numpy` (`attribution.py`) instead of `scipy.optimize.nnls`, and the basis artifact is a plain JSON (`basis/artifacts/bases.json`) instead of a `joblib` pickle — CONSTITUTION.md's "check new dependencies first," and this project runs on `psycopg2`+`numpy` only so far.
- **`router.should_fork`'s structural-evidence check:** only the multi-dimension-concentration check is implemented. Changepoint detection needs a per-day series 5a doesn't carry; the declared-dependent-pair check needs each candidate's own onset day, which 5a's `FingerprintResult` doesn't carry either — and "both members clear the 5% probability floor" turned out NOT to be real evidence (verified live: it's true for almost every narrow-margin case, since 5a spreads mass close to evenly whenever it's unsure). Both are honest deferrals, not silent gaps — see `router.py`'s docstring.
- **Offline scorer:** `scoring/score_attribution.py` runs against `--n-episodes` real overlapping-pair episodes (default 5), not the full 28.

**Covers in this slice:**
- `cause_config.py` — the 4 real `CAUSE_FAMILIES` (asserted equal to the generator's own `EVENT_TYPES` in `test_stage5b.py`, not by comment), `SEASONAL`/`UNEXPLAINED` sentinels, the declared `product_outage→marketing_cut` chain lag, thresholds
- `models.py` — `CauseContribution` / `ConfoundedAttributionResult`, with `unexplained` structurally required (never silently zero) and a `NON_IDENTIFIABLE_JOINT` component structurally required to carry ≥2 `member_causes`
- `stage4_bridge.py` — re-exports Stage 4's `slice_fetcher` + Stage 2's `compute_residuals`/`assess_eligibility` (same `sys.path`/`sys.modules`-eviction pattern, one level deeper again)
- `deviation_matrix.py` — the per-(dimension, slice_value) daily residual matrix for a window, skipping `LIMITED_HISTORY`/`INSUFFICIENT_DATA` slices (Stage 4's own rule)
- `shape_features.py` — the one shared shape-vector builder used by **both** basis learning and runtime (no train/serve skew): temporal profile + region/product sorted-share concentration profiles + segment identity profile, a pure function of `(BASIS_WINDOW_DAYS, TOP_K_SLICES)`
- `identifiability.py` — declared dependent-pair merge (when onsets are known) then an empirical cosine-similarity gate, in that order, before anything reaches the fit
- `attribution.py` — NNLS-style fit in KPI units, `unexplained` as the honest residual, never distributed across named causes to make shares tidy
- `router.py` — `should_fork` (margin + structural evidence, not margin alone)
- `output_schema.py` — free-text-cause rejection + "no separate entry for a joint component's own member"
- `basis/build_bases.py` — offline learner, queries `injected_events` (offline only)
- `stage5a_bridge.py` / `pipeline_bridge.py` — re-export Stage 5a/4/3's real `run_*` functions for the CLI
- `stage5b.py` — orchestrator (`run_stage5b`) + CLI entrypoint
- `scoring/score_attribution.py` — offline-only, scores against the generator's real `effect_fraction` math (imported via `simulator_bridge.py`, never reimplemented)

**A real finding from the one live run, not assumed:** with only 5 basis samples per cause, the cosine-similarity identifiability gate merged all 5 candidates (4 causes + seasonal) into one `FULLY_MERGED` joint bucket on the one episode tested — an honest "can't separate with this little training data" abstention, not a bug (the bug that *was* found and fixed: a joint component's `basis_sample_count` lookup was keyed by individual cause name instead of the joint fit-name, `KeyError` on any merge). Widening `--n-per-cause` in `build_bases.py` is the direct lever if a cleaner split is needed for a demo — not attempted here given the time budget.

**Output contract (→ Stages 6/7/8):** `models.ConfoundedAttributionResult` — one per (KPI, window), `contributions` a list of `CauseContribution` always including `unexplained`, `identifiability_verdict` one of `CLEAN_SPLIT`/`PARTIAL_MERGE`/`FULLY_MERGED`.

**Consumes:** Stage 5a's `FingerprintResult.cause_scores` and Stage 4's `DecompositionResult` (window bounds + dimension signal for the router).

**Deferred, not implemented (per the design doc, unchanged):**
- Per-slice/per-day attribution (unit is (KPI, window) only).
- Bootstrap confidence intervals on shares (joint bucket is the chosen non-identifiability handling).
- "Which slice a cause owns" (bases match on shape profiles, not slice identity, by construction).
- Any counterfactual estimate (Stage 8's job).
- FastAPI wiring — same phased-build reasoning as Stages 1-5a.
- **A sixth stacked cross-stage import** (5b → 4 → 2 → 1, 5b → 5a → 3/4, 5b → simulator for offline scoring). `architecture.md`'s Known Risks called a real package overdue at the fourth stage; this is the sixth.

**Run:**
```bash
cd pipeline/stage05b_confounded_cause_decomposer
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python basis/build_bases.py --n-per-cause 5    # one-time, writes basis/artifacts/bases.json
.venv/bin/python test_stage5b.py                          # must print OK (offline + 1 live end-to-end run)
.venv/bin/python stage5b.py --episode-id 15
.venv/bin/python scoring/score_attribution.py --n-episodes 5   # offline-only
```
