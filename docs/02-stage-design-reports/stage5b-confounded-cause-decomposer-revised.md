# Plan: Stage 5b — Confounded-Cause Decomposer

**Design report:** none exists — **this plan is also the design record for Stage 5b.** Unlike Stages 1–4, there is no prior `docs/02-stage-design-reports/` doc to supersede; the only prior statements about 5b are the two-sentence job description in `docs/00-brief-and-topology/round2-topology-and-brief.md` §4 and the routing hook in `.claude/plans/stage5a-implementation-plan.md` §6. Both are honoured below; neither is detailed enough to implement from.
**Priority:** after Stage 5a is built. 5b consumes 5a's output and cannot run without it (see Risk #1 and §5).
**Branch:** `feature/stage5b-plan` (this plan doc) → `feature/stage5b-confounded-cause-decomposer` (implementation) off `develop`.
**Track:** `stage5b-confounded-cause-decomposer`.

---

## 0. Decisions locked in the design interview

Recorded here so a later session doesn't re-litigate them:

| Decision | Choice |
|---|---|
| Attribution mechanism | **Basis-fit over deviations** — non-negative least squares of the observed deviation shape onto per-cause response bases. Not probability renormalization. |
| Attribution unit | **Per (KPI, flagged window) total** — one contribution vector per KPI per window. Not per-slice, not per-day. |
| Fork trigger | **5a margin AND corroborating structural evidence** — narrow margin alone means "uncertain", not "confounded". |
| Sequencing | **Plan now, build 5a first.** This branch ships the plan document only. |
| Basis source | **Learned offline from single-event episodes**, not hand-declared. |
| Non-identifiability | **Joint bucket + refuse the split** — collinearity gate before fitting; emit one merged component with a `NON_IDENTIFIABLE` flag rather than a fabricated ratio. |
| Component set | **4 real event types + an explicit `unexplained` residual.** `seasonal` is handled upstream as baseline/normal variation, not fitted as a competing cause in 5b. |
| Evaluation | **Attribution MAE against the generator's own contribution math**, plus cause-set accuracy, dominant-cause accuracy, and abstention precision. |

---

## 1. What this stage is for (the distinction that *is* the component)

Stage 5a ends with a probability vector over cause families. When that vector is split — `product_outage 0.42 / marketing_cut 0.38` — the ordinary move is to take the top-1 and continue. That is wrong in two different ways, and only the first is obvious:

1. The system might have picked the wrong cause.
2. **There may be no single right answer to pick** — both causes are running simultaneously, and a top-1 answer structurally cannot represent the truth.

5b exists for (2). The load-bearing point, which every implementation step below is built to protect:

- `P(cause)` — what 5a emits — is **uncertainty about which one**. "I am 42% confident it was the outage."
- `contribution share` — what 5b emits — is a **decomposition of the movement itself**. "The outage explains 6.1 of the 8.0 points; the marketing cut explains 1.9." Both are true at once and they reconcile to the observed deviation.

These are different quantities. Any implementation that renormalizes 5a's probabilities into percentages and labels them "contributions" has relabelled a confidence, not decomposed a movement — and it is the first thing a sharp reviewer will test. **The rejection of that shortcut is the reason this stage is separately named and separately built** (`docs/00-brief-and-topology/round2-topology-and-brief.md` §3 calls confounded-cause decomposition the project's sharpest differentiator, precisely because commercial RCA products all stop at a ranked top-1).

**Design precedent to reuse, not reinvent:** Stage 3's design report §6 (Multi-Path Combination Rule) already draws the distinction 5b needs, in a different setting — **shared-node paths must be combined jointly** (projecting each independently and summing double-counts their interaction), while **disjoint paths may be summed**. Stage 3's own doc flags this as "the same underlying spirit as Stage 5b's confounded-cause decomposer." It transfers directly and literally: the reactive `product_outage → marketing_cut` chain is a *shared-node* pair (one caused the other), so its two contributions must never be presented as two independent additive terms. That is exactly the joint-bucket case in §7.3.

---

## 2. Live-verified data facts (queried against Neon during planning — not assumed)

Per CONSTITUTION.md's non-negotiable that new real-world-data claims get verified against actual data before being asserted:

| Fact | Value | Consequence for 5b |
|---|---|---|
| Real cause label space | **4 event types**: `marketing_cut` (53), `inventory_shortage` (39), `product_outage` (34), `competitor_launch` (26) | The 8-label list in `.claude/plans/stage5a-implementation-plan.md` §4 (`churn`, `pricing_change`, `regional_economic`, …) is inherited from the pre-narrowing architecture report and **cannot be produced by this simulator**. 5a's label space must be amended before 5b is built — see §5.2. |
| Episodes with ≥1 injected event | 96 of 150 (54 have none) | The 54 zero-event episodes are the training set for the `seasonal` / normal-variation basis. |
| Events per episode | 1: 56 · 2: 26 · 3: 12 · 4: 2 | **56 single-event episodes** are the basis training set. |
| Single-event episodes by type | `inventory_shortage` 17 · `marketing_cut` 16 · `product_outage` 12 · `competitor_launch` 11 | Each basis is a mean over 11–17 episodes. Thin — see Risk #2. |
| Episodes containing a temporally overlapping event pair | **33** (28 with a *distinct-type* pair) | 5b has a real evaluation set of 28 episodes, not a hand-built demo. |
| Overlapping distinct-type pairs by kind | `marketing_cut × product_outage` 20 · `competitor_launch × marketing_cut` 7 · `inventory_shortage × marketing_cut` 6 · `competitor_launch × inventory_shortage` 3 · `competitor_launch × product_outage` 2 · `inventory_shortage × product_outage` 1 | The headline pair dominates. |
| Reactive chains (`triggered_by_event_id` set) | 19, **all starting <10 days after their trigger** | 19 of the 20 `marketing_cut × product_outage` overlaps are the *same* causal chain, at short lag. The collinearity gate will fire on most of them — see Risk #3. |
| Generator combination law | Additive in latent space per channel (`mc_frac`, `po_frac`, `cl_frac` each `sum(...)` over their events); `inventory_shortage` is multiplicative on `product_weights` | Ground-truth contribution shares are **exactly computable** from `injected_events` — this is what makes numeric scoring possible instead of a top-1 accuracy claim. |

---

## 3. Outcome (testable)

Given a real Stage 5a result for an episode whose flagged window genuinely contains two distinct-type overlapping injected events (one of the 28 verified episodes, e.g. a `competitor_launch × marketing_cut` case), Stage 5b emits one `ConfoundedAttributionResult` per (KPI, window) containing a non-negative contribution **in KPI units** for each candidate cause plus `seasonal`, an explicit `unexplained` residual, and shares that reconcile to the observed window deviation — with `NON_IDENTIFIABLE` merging applied where two candidate bases are collinear. Scored offline against the generator's own `effect_fraction`-derived contribution shares over all 28 overlapping-pair episodes, it reports a real share-MAE, a cause-set accuracy, a dominant-cause accuracy, and an abstention precision — numbers printed by the test, not claimed in prose.

Explicitly, the test asserts the **honest** expectation, in the spirit of Stage 4's live-verification correction: on the reactive-chain subset (19 episodes, onsets <10 days apart), 5b is expected to return `NON_IDENTIFIABLE` joint components more often than clean splits, and that abstention counts as *correct* behaviour, not a failure — while the non-chained subset (≈9 episodes) is where a genuine numeric split must be demonstrated.

---

## 4. Scope

**In (first implementation slice):**
- Offline basis learning from the 56 single-event and 54 zero-event episodes, producing a versioned artifact with per-basis sample counts and dispersion recorded alongside each shape.
- A shared shape-feature module used by **both** basis learning and runtime — the same train/serve-skew rule 5a's plan raises in its §3, applied here.
- Runtime NNLS attribution over candidate causes, with an explicit `unexplained` residual term.
- A simple collinearity/identifiability gate run **before** fitting, plus declared dependent-pair merging for the reactive chain (Stage 3 §6's shared-node rule).
- A trigger/router that implements the agreed fork condition (margin **and** structural evidence).
- Output contract dataclasses + a free-text-rejecting schema validation, matching Stage 4's `output_schema.py` pattern.
- An offline scorer measuring attribution MAE against the generator's own math.
- `test_stage5b.py` — offline checks plus live-DB checks, printing `OK`.

**Out (explicitly deferred):**
- **Per-slice and per-day attribution.** The unit is (KPI, window). A time-resolved "cause A fades as cause B ramps" view is the most compelling demo artifact available here and is a strong candidate for the *second* slice — it is deferred, not rejected.
- **Bootstrap confidence intervals on the shares.** The chosen non-identifiability handling is the joint bucket, not intervals. Revisit only if the joint bucket proves too coarse.
- **Which slice a cause owns.** Bases are matched on sorted-share *profiles*, not slice identity (§7.1) — by construction 5b says "the outage owns 6.1 points", never "the outage owns São Paulo". Naming the slice stays Stage 4's descriptive output and Stage 7's job to combine.
- **Any counterfactual estimate.** "What would revenue have been without the outage" is Stage 8. 5b hands Stage 8 a per-cause contribution to *run* counterfactuals on; it does not run them.
- **A `seasonal` or `volatility` basis.** Normal/seasonal variation and volatility are not separate fitted causes in the first implementation; they are handled by the upstream baseline and the `unexplained` residual.
- **Any LLM call.** Non-negotiable #4.
- **Online/live retraining.** Bases are learned once, offline, and frozen — same discipline as 5a's classifier.
- **FastAPI wiring** — same phased-build reasoning as Stages 1–4.

---

## 5. Input contract, and the two amendments Stage 5a needs first

### 5.1 What 5b consumes

Stage 5a's `run_stage5a` returns `routing_decision ∈ {PROCEED, BRANCH_5B_CONFOUNDED, BRANCH_5C_COLD_START}` (5a plan §7). 5b is invoked on `BRANCH_5B_CONFOUNDED` and consumes:

- `cluster_id`, `window` (as `day_offset`s — 5a's plan §7 shows ISO dates; the real Stage 3/4 contract is integer `day_offset`s, the same supersession Stage 4's plan had to make),
- `cause_probabilities` — the **full** distribution, which 5a's plan already commits to passing forward,
- `fingerprint_features` — reused as structural evidence by the router rather than recomputed,
- the originating `DecompositionResult` from Stage 4 (5b needs the slice matrix, and needs to re-pull daily granularity — see §7.1).

### 5.2 Amendment A — 5a's label space is wrong for this build (blocking)

5a's plan §4 declares 8 cause labels. Four of them (`churn`, `pricing_change`, `regional_economic`, and `seasonal`-as-an-event) have **no corresponding `event_type` in the simulator** — the generator can only ever emit `product_outage`, `marketing_cut`, `competitor_launch`, `inventory_shortage`. A classifier trained on 8 labels against data containing 4 would have four permanently-empty classes.

**Required before 5b is built:** amend 5a's label space to the 4 real event types. `seasonal` is kept as a 5b **attribution component** (it is a real driver in the generator and answers the exact "was it just the season?" question an executive asks) but it is not an injected event, so it is learned from the 54 zero-event episodes rather than from labels. This is the same category of correction Stage 4's plan had to make against its own design report, and it should be raised in 5a's PR, not silently worked around.

### 5.3 Amendment B — the fork trigger needs structural evidence, not just a margin

5a's plan §6 forks to 5b when `top1 - top2 < CONFOUND_MARGIN_THRESHOLD` (default 0.20). A narrow margin alone cannot distinguish "two causes are genuinely present" from "the classifier is weak on this input" — and with bases learned from 11–17 episodes each, the second will happen. The agreed trigger adds corroborating structure; see §7.4 for the exact predicate. 5a's `router.py` should call into 5b's `router.should_fork(...)` rather than duplicating the margin check.

---

## 6. Output contract (→ Stages 6/7/8)

```python
@dataclass
class CauseContribution:
    cause: str                      # one of CAUSE_FAMILIES, "seasonal", "unexplained",
                                    #   or a joint label e.g. "product_outage+marketing_cut"
    contribution: float             # KPI units, non-negative
    share: float                    # contribution / total attributed magnitude
    basis_provenance: str           # "LEARNED" | "SEASONAL_BASELINE" | "RESIDUAL"
    basis_sample_count: Optional[int]   # how many episodes the basis was averaged over
    identifiability: str            # "IDENTIFIED" | "NON_IDENTIFIABLE_JOINT"
    member_causes: Optional[List[str]]  # populated only for a joint component

@dataclass
class ConfoundedAttributionResult:
    episode_id: int
    cluster_id: Optional[str]
    kpi_name: str
    window_start_day_offset: int
    window_end_day_offset: int
    observed_deviation: float           # the movement being decomposed, KPI units
    contributions: List[CauseContribution]
    unexplained_share: float            # what the fit could NOT account for
    fit_quality: float                  # relative residual norm of the NNLS solution
    identifiability_verdict: str        # "CLEAN_SPLIT" | "PARTIAL_MERGE" | "FULLY_MERGED"
```

Two contract rules, both structurally enforced (not left to discipline):

1. **`unexplained` is always present and never silently zero.** Shares that sum to exactly 100% across named causes are a red flag; the residual is the honesty valve, and `output_schema.validate` asserts the term exists.
2. **A joint component is never split downstream.** `member_causes` names what was merged so Stage 7 can debate the pair, but no single number is offered for either member. Stage 8 counterfactuals a joint component jointly.

---

## 7. Mechanism

### 7.1 The deviation vector (shared between offline and runtime)

Stage 4 emits window-aggregate snapshots only (its own documented non-goal), so 5b re-pulls daily granularity — reusing `slice_fetcher.load_slice_timeline` + `stage2_bridge.compute_residuals`, which already return the per-`(slice, day)` `(day, expected, residual)` triples needed. **No new baseline logic is written.**

The observed vector is built from the **existing Stage 4 deviation structure**, not raw KPI values. For the first implementation, keep the representation deliberately small:

```
x = concat(
    temporal residual profile over the flagged window,
    region concentration profile,
    segment profile (New / Returning / VIP),
    product-category concentration profile
)
```

The region and product axes use sorted absolute-residual shares so the representation is comparable across episodes with different slice identities. Segment keeps its declared identity because `New/Returning/VIP` is stable across episodes. The vector is normalized to represent **shape**; the observed window magnitude `M` is carried separately.

The important boundary is that 5b **does not rediscover unusualness, KPI relationships, or dimensional decomposition**. It consumes the Stage 4/earlier-stage outputs and puts them into one shared numerical representation for attribution.

### 7.2 Basis learning (offline, one-time)

For each of the 4 event types, over that type's single-event episodes:
1. Take the event window `[start_day_offset, start_day_offset + L)` from `injected_events` (offline use only).
2. Build `x` for that episode with the **same** `shape_features` code the runtime uses.
3. Average the per-episode `x` vectors → the basis for that type. Record `n`, and the per-component standard deviation, in the artifact.

There is **no separate seasonal basis in the first implementation**. Seasonal/normal variation is handled by the upstream baseline and by the explicit `unexplained` residual in the fit. This keeps 5b focused on decomposing overlapping candidate causes rather than treating normal variation as another cause.

Artifact: `basis/artifacts/bases.joblib`, carrying the shapes, `n` per basis, dispersion, the `shape_features` version string, and the generation timestamp. A runtime version mismatch between the artifact's feature version and the loaded `shape_features` module is a hard error, not a warning.

### 7.3 The identifiability gate (runs *before* the fit)

Candidate set = causes above a probability floor in 5a's distribution. Then, in order:

1. **Declared dependent-pair merge (Stage 3 §6's shared-node rule).** `cause_config.DEPENDENT_PAIRS` declares `(product_outage → marketing_cut)` with the generator's real chain lag window (3–10 days). If both members are candidates and their inferred onsets fall inside that lag, they merge into one joint component *by declaration* — no fit is attempted between them, because one caused the other and their contributions are not independent additive terms.
2. **One empirical separability gate.** Compute pairwise cosine similarity between the remaining candidate bases. If `|cosine| > τ` (default 0.95), merge the pair into a joint component. Do not add a second condition-number mechanism in the first implementation; if pairwise similarity proves insufficient in evaluation, that can be added later.
3. Only the surviving, mutually-separable set goes to NNLS.

Merged components carry `identifiability: "NON_IDENTIFIABLE_JOINT"` and both member names. The verdict is `CLEAN_SPLIT` when no merge occurred, `FULLY_MERGED` when every candidate merged into one, `PARTIAL_MERGE` otherwise.

### 7.4 The fit

```
minimise ‖ M·x_obs − Σ_k c_k · b_k ‖₂   subject to   c_k ≥ 0
```

`c` is in KPI units. `share_k = c_k / Σc`. `unexplained_share` = relative residual norm of the solution — reported, never distributed across the named causes to make the shares tidy.

### 7.5 The fork trigger (`router.should_fork`)

Fork to 5b when the margin is narrow **and** corroborating structural evidence exists. Reuse the evidence already available from earlier stages rather than inventing new detection logic:
- two distinguishable changepoints inside the window,
- two dimensions concentrating differently,
- or a declared dependent pair is present among the candidates.

Narrow margin with none of these is a *weak classification*, not a confounded case: it stays with 5a, tagged `MEDIUM` confidence, and the reason is recorded in the routing output.

---

## 8. Files to read first

1. `.claude/plans/stage5a-implementation-plan.md` — §2 (rare-slice selection), §6 (routing), §7 (output schema). **Its §4 label space is wrong for this build — see §5.2 above.**
2. `docs/02-stage-design-reports/stage3-cross-kpi-correlation-prioritization.md` §6 — the shared-node/disjoint rule 5b's joint bucket is a second application of.
3. `pipeline/stage04_dimensional_decomposition/decomposer.py` and `slice_fetcher.py` — the exact per-`(slice, day)` residual machinery 5b reuses, and the `(day, expected, residual)` triple shape.
4. `pipeline/stage04_dimensional_decomposition/README.md` — the live-verification finding that eligibility is driven by window recency, not slice size. 5b inherits this: a window close to day 0 makes *every* slice `LIMITED_HISTORY` together, which is a 5c condition, not a 5b one.
5. `pipeline/simulator/layer1_ground_truth/generate.py` — `effect_fraction`, `EVENT_TYPES`, `TYPICAL_ONSET`, `EVENT_COUNT_WEIGHTS`, `sample_events` (the chain), and the `mc_frac`/`po_frac`/`cl_frac`/`product_weights` combination law in `generate_episode`. This is both the source of truth for what causes exist and the scorer's imported ground-truth math.
6. `pipeline/stage03_cross_kpi_correlation/stage2_bridge.py` and `pipeline/stage04_dimensional_decomposition/stage2_bridge.py` — the cross-stage import pattern 5b needs one level deeper again.
7. `.claude/reference/architecture.md`, `.claude/reference/database.md` — build status, schema, live data stats.
8. `CONSTITUTION.md` — non-negotiables #4 (LLM boundary) and #5 (`injected_events` held out); see Risk #4.

## 9. Files to create / change

```
pipeline/stage05b_confounded_cause_decomposer/
  README.md                    — update from "not yet designed" to real status
  requirements.txt             — psycopg2-binary, numpy, python-dotenv, joblib, scipy (NEW dep — see Risk #5)
  models.py                    — CauseContribution + ConfoundedAttributionResult (§6)
  cause_config.py              — CAUSE_FAMILIES (4 real types), SEASONAL/UNEXPLAINED sentinels,
                                 DEPENDENT_PAIRS (the declared outage→marketing_cut chain + its lag window),
                                 thresholds (τ, κ, probability floor, L, K). A plain dict module,
                                 this project's established pattern for declared config.
  stage4_bridge.py             — re-exports Stage 4's slice_fetcher + Stage 2's compute_residuals
                                 (sys.path insert + sys.modules eviction, same as Stages 3/4)
  shape_features.py            — §7.1. SHARED by basis learning and runtime, no exceptions.
  deviation_matrix.py          — pulls the per-(slice, day) residual matrix for a window via stage4_bridge
  basis/
    build_bases.py             — §7.2 offline learner (CLI)
    artifacts/bases.joblib     — committed artifact + a sidecar .json of n / dispersion per basis
  identifiability.py           — §7.3 declared merge + collinearity gate
  attribution.py               — §7.4 NNLS fit, shares, residual
  router.py                    — §7.5 should_fork()
  output_schema.py             — free-text rejection + the two §6 contract rules
  stage5b.py                   — run_stage5b(cur, episode_id, stage5a_result, decomposition) + CLI
  scoring/
    score_attribution.py       — §11.2 offline scorer, imports generate.effect_fraction
  test_stage5b.py              — offline + live-DB, prints OK

.claude/reference/architecture.md   — status table row for Stage 5b; note the 5th stacked cross-import
.claude/plans/stage5a-implementation-plan.md — amendments A and B (§5.2, §5.3)
```

## 10. Implementation steps

1. **`cause_config.py`** — the 4 real `CAUSE_FAMILIES`, `SEASONAL`/`UNEXPLAINED` sentinels, `DEPENDENT_PAIRS = {("product_outage", "marketing_cut"): (3, 10)}` (the generator's real `rng.integers(3, 10)` chain lag), and thresholds. *Validation:* assert `set(CAUSE_FAMILIES) == set(generate.EVENT_TYPES)` — a test that fails loudly if the simulator's event types ever change, rather than letting the label space drift silently.

2. **`stage4_bridge.py`** — re-export `load_slice_timeline`, `distinct_slice_values`, `compute_residuals`, `assess_eligibility`. Mirrors Stage 4's own bridge exactly, one level deeper. *Validation:* round-trip import in isolation; confirm no `sys.modules` collision with 5b's own `models.py`/`router.py` (both names already exist in 5a's planned tree too).

3. **`deviation_matrix.py`** — `build(cur, episode_id, kpi_name, window, trailing=30) -> {(dimension, slice_value): [(day, expected, residual)]}`. Skips slices whose eligibility is `LIMITED_HISTORY`/`INSUFFICIENT_DATA`, inheriting Stage 4's rule that such a slice never gets a fabricated number. *Validation:* against episode 1's `revenue` window 107–109 (Stage 4's own verified live case), confirm the matrix covers every applicable `(dimension, slice_value)` pair and that residual sums reconcile to Stage 4's `SliceResult.observed - expected` for the same slices — i.e. 5b's re-pull agrees with Stage 4's snapshot rather than quietly diverging.

4. **`shape_features.py`** — `build_shape_vector(matrix, window, changepoint_day) -> np.ndarray` plus a `FEATURE_VERSION` string. *Validation:* unit checks — a synthetic matrix with all deviation in one region returns a region profile of `[1, 0, 0, 0, 0]`; an evenly-spread one returns `[0.2]*5`; a step-onset temporal series and a ramp produce visibly different temporal profiles. Assert the output vector length is a pure function of `(L, K)` so basis and observation always align.

5. **`basis/build_bases.py`** — §7.2. Queries `injected_events` (offline only), selects single-event episodes per type and zero-event episodes for `seasonal`, builds each `x` via `shape_features`, averages, and writes `bases.joblib` + a sidecar JSON with `n` and per-component dispersion. *Validation:* run it; assert `n` per basis matches the live counts (`inventory_shortage` 17, `marketing_cut` 16, `product_outage` 12, `competitor_launch` 11, `seasonal` ≤54) and that the four event bases are pairwise distinguishable — print the Gram matrix and assert `inventory_shortage`'s product profile is the most concentrated of the four (the generator makes it single-category by construction; if it isn't, the shape features are not capturing what they claim to).

6. **`identifiability.py`** — §7.3, in the stated order: declared merge first, then the Gram/condition gate. `assess(candidates, bases, onsets) -> (groups, verdict)`. *Validation:* offline — two deliberately near-identical synthetic bases merge; two orthogonal ones don't; a declared dependent pair at 5-day lag merges even when its cosine is low; the same pair at 40-day lag does **not** merge by declaration (it may still merge empirically, which is a different reason and must be reported as such).

7. **`attribution.py`** — §7.4 NNLS (`scipy.optimize.nnls`, or a numpy projected-gradient fallback if the dependency is declined — see Risk #5). Returns contributions in KPI units, shares, and the relative residual. *Validation:* offline — a synthetic observation constructed as `0.7·b_outage + 0.3·b_mktcut` recovers coefficients within tolerance and an `unexplained_share` near 0; an observation built from a basis *not* in the candidate set produces a high `unexplained_share` rather than being force-fit onto the wrong causes. That second check is the one that matters — it is the test that 5b abstains instead of inventing.

8. **`router.py`** — §7.5 `should_fork(stage5a_result, decomposition) -> (bool, reason)`. *Validation:* a narrow-margin input with no structural evidence does **not** fork (and records why); a narrow-margin input with a declared dependent pair does.

9. **`output_schema.py`** — free-text rejection in Stage 4's style, plus the two §6 rules: `unexplained` term must exist; a `NON_IDENTIFIABLE_JOINT` component must carry ≥2 `member_causes` and must not be accompanied by separate per-member entries. *Validation:* one clean case passes; an injected free-text cause is rejected; a joint component that also emits its members separately is rejected.

10. **`stage5b.py`** — `run_stage5b(cur, episode_id, stage5a_result, decomposition) -> ConfoundedAttributionResult`, wiring steps 3–9, plus an `argparse` CLI taking `--episode-id` that re-derives its input by running Stages 3→4→5a (mirroring how `stage4.py`'s CLI re-derives from Stage 3). *Validation:* end-to-end on one of the 28 verified overlapping-pair episodes; no crash, contract validates, shares reconcile.

11. **`scoring/score_attribution.py`** — §11.2. *Validation:* the scorer's ground-truth path is checked against a hand-computed case for one episode before it is trusted to grade anything.

12. **`README.md` + `.claude/reference/architecture.md`** — update status, record the 5th stacked cross-import, and state plainly which parts of the eval set 5b abstains on and why.

## 11. Tests and validation gate

```bash
cd pipeline/stage05b_confounded_cause_decomposer
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # .venv/Scripts/python.exe on Windows
.venv/bin/python basis/build_bases.py        # one-time, writes the artifact
.venv/bin/python test_stage5b.py             # must print OK
.venv/bin/python scoring/score_attribution.py --report
```

### 11.1 Offline checks
Steps 1, 4, 6, 7, 8, 9's validations, collected — all runnable without a live DB (synthetic bases and matrices).

### 11.2 The offline scorer (the "real numbers" deliverable)

For each of the 28 distinct-type overlapping-pair episodes:

```python
# ground truth — imported from the generator, never reimplemented, so the scorer
# cannot drift from the truth it is scoring against
true_intensity[event] = sum(event.magnitude * effect_fraction(day, event)
                            for day in window)
true_share = true_intensity / sum(true_intensity.values())
```

Reported metrics:
- **Share MAE** — mean absolute error of predicted vs true share vectors, over episodes where 5b returned a clean split.
- **Cause-set accuracy** — did 5b name the right *pair* of contributing causes?
- **Dominant-cause accuracy** — did it get which one is bigger?
- **Abstention precision/recall** — of the episodes where 5b returned `NON_IDENTIFIABLE_JOINT`, how many were genuinely the short-lag reactive chain? An abstention on a chain pair is a **correct** outcome and is scored as such.

**A known approximation, stated rather than hidden:** `magnitude × effect_fraction` measures intensity within each event's own latent channel (ad spend, reliability, competitor pressure, product weight). Comparing intensities *across* channels to form a share treats a 0.3 marketing cut and a 0.3 reliability hit as equally impactful, which is not exactly true. The exact alternative — re-running the generator with one event ablated under the same seed — **does not work here**: removing an event changes `n_orders`, which changes how many RNG draws each day consumes, so the random stream diverges and the two runs are not comparable counterfactuals. Multi-seed averaged ablation would fix this and is the honest upgrade path; the intensity approximation is the first slice, and the scorer prints this caveat with its results.

### 11.3 Live checks
- `run_stage5b` end-to-end on ≥2 real overlapping-pair episodes — one reactive-chain (expect a joint component) and one non-chained (expect a clean split). Both must validate against the output contract.
- **Assert the runtime path never touches `injected_events`** — wrap the runtime cursor in a statement-logging proxy and assert no executed SQL references the table. This is non-negotiable #5 enforced structurally, not by discipline (see Risk #4).

## 12. Acceptance criteria

- [ ] Stage 5a's plan amended: label space reduced to the 4 real event types (Amendment A), fork trigger updated to margin + structural evidence (Amendment B)
- [ ] `CAUSE_FAMILIES` is asserted equal to the simulator's `EVENT_TYPES` by a test, not by comment
- [ ] Bases learned from real single-event episodes, with `n` and dispersion recorded in the artifact and surfaced in the output as `basis_sample_count`
- [ ] `shape_features.py` is imported by both `build_bases.py` and the runtime path — verified by a version-string check that hard-errors on mismatch
- [ ] Contributions are emitted in **KPI units**, not renormalized 5a probabilities — a test asserts the two differ on a case where 5a's probabilities are near-even but the fitted contributions are not
- [ ] `unexplained` is always present; an observation built from an out-of-candidate-set basis produces a high `unexplained_share` rather than a force-fit
- [ ] The declared `product_outage → marketing_cut` chain merges into one joint component at real chain lag, and no per-member split is emitted for it
- [ ] Output schema rejects free-text causes and rejects a joint component accompanied by separate member entries
- [ ] Offline scorer runs over all 28 overlapping-pair episodes and prints share MAE, cause-set accuracy, dominant-cause accuracy, and abstention precision — with the cross-channel-intensity caveat printed alongside
- [ ] Runtime-path test proves no SQL touched `injected_events`
- [ ] `test_stage5b.py` passes offline and against live Neon data, printing `OK`
- [ ] README + `.claude/reference/architecture.md` updated; PR opened against `develop` and merged

## 13. Risks

1. **5b is planned against a contract with no code behind it.** Stage 5a is designed only. Two of its stated facts are already known-wrong for this build (label space, ISO-date window) and a third (the margin-only fork) is being amended by this plan. Until 5a is built and its real output shape is observed, §5.1 is a plan-to-plan contract, not a verified one — the same situation Stage 4's plan was in against its own design report, which turned out to be wrong on three load-bearing facts. Expect to revise §5.1 after 5a's first live run rather than assuming it holds.

2. **The basis training set is thin: 11–17 single-event episodes per cause type.** Each basis is a mean over roughly a dozen samples, so the learned shapes carry real variance. Mitigation is disclosure, not concealment: `n` and per-component dispersion ship inside the artifact and surface in the output as `basis_sample_count`. Do not claim a basis is "learned from the data" without also stating how few episodes that was.

3. **Most of the headline evaluation set is the same causal chain, at short lag.** 20 of the 39 overlapping distinct-type pairs are `marketing_cut × product_outage`, and 19 of those are reactive chains starting <10 days after their trigger. The identifiability gate is *designed* to refuse a split there — which means 5b's honest answer on the majority of its own eval set will be "not separable." That is correct behaviour and scores as correct, but it is a weak demo if it is the only case shown. **Demo the non-chained pairs** — `competitor_launch × marketing_cut` (7) and `inventory_shortage × marketing_cut` (6) are the cases where a genuine numeric split can be demonstrated, and `inventory_shortage`'s single-category product signature makes it the most separable cause in the set. Pick the live demo episode from that subset deliberately.

4. **Learning bases from `injected_events` is not literally covered by non-negotiable #5's wording.** The constitution permits `injected_events` "only for offline scoring"; basis learning (like 5a's classifier training) is offline *training*, a third use the wording doesn't name. This needs an explicit clarification in CONSTITUTION.md — "offline scoring **and offline model training**; never on the runtime path" — rather than a quiet reinterpretation. The structural guard is in §11.3: a test proving the runtime path never issues SQL against the table.

5. **`scipy` is a new dependency.** Stages 1–4 run on `psycopg2-binary` + `numpy` + `python-dotenv` only, and CONSTITUTION.md requires new dependencies be checked first. `scipy.optimize.nnls` is the natural fit; if the dependency is declined, a projected-gradient NNLS in ~20 lines of numpy is an acceptable substitute for a problem this small (≤6 non-negative coefficients). `joblib` is also new, though 5a's plan already introduces it for its own artifacts.

6. **A fifth stacked cross-stage import** (5b → 4 → 2 → 1, plus 5b → 5a for the CLI path). `architecture.md` called a real package "overdue, not just worth revisiting" at the fourth. At five — and with 5a, 5b, and 5c all landing in the same phase, all needing the same Stage 4 machinery — the `sys.path`/`sys.modules`-eviction pattern is now actively shaping module *names* to dodge collisions (`models.py` and `router.py` will exist in 5a, 5b, and 5c simultaneously). **Recommendation: do the package consolidation before 5a/5b/5c, not after.** It is still a separately-scoped change, not folded into this plan, but it is the cheapest it will ever be right now.

7. **Sorted-share profiles are the right call and they cost something real.** Matching on concentration shape rather than slice identity is what makes cross-episode basis learning possible at all, but it means 5b structurally cannot say which region or category a cause owns. If Stage 7 or the demo turns out to need "the outage owns Enterprise," that answer has to come from joining 5b's cause attribution back onto Stage 4's slice matrix — a real piece of work, currently unscoped in any stage's plan.

8. **Windows/POSIX venv path divergence.** Every doc in this repo writes `.venv/bin/python`; on the current dev machine the interpreter is at `.venv/Scripts/python.exe`. Harmless, but the commands in §11 will not copy-paste on Windows as written.
