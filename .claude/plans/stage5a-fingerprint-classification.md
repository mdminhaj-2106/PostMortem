# Plan: Stage 5a — Fingerprint / Cause-Signature Classification

**Design report:** `docs/02-stage-design-reports/stage5a-implementation-plan.md` — **not usable as written; treat
like the Stage 4 design report was treated** (`.claude/plans/stage4-dimensional-decomposition.md`): mechanism
useful, specifics wrong, and here the specifics being wrong changes the *recommended mechanism itself*, not
just names. That doc assumes: an 8-class cause taxonomy (`churn, marketing_reduction, product_reliability,
inventory_shortage, competitor_activity, pricing_change, seasonal, regional_economic`); a `conversion_rate` KPI
that is not one of this project's 6 declared KPIs; `North/Enterprise` taxonomy already corrected at Stage 4
(`customers.region` = 27 real Olist state codes, `customers.segment` = `New/Returning/VIP`); ISO-date windows
(real contract is integer `day_offset`); and a trained XGBoost + SHAP pipeline with Platt-scaled probabilities
over 8 classes, evaluated on "a few hundred synthetic episodes."

**Deadline context this plan must respect:** submission is due 2026-08-30 23:59. Report + PPT + video (~7-11.5h,
not started) still sit ahead of any Stage 5a work. This plan's scope recommendation is chosen accordingly — see
§Scope decision below before reading implementation steps.

## What's actually true about the cause taxonomy (verified against the real generator, not the design doc)

`pipeline/simulator/layer1_ground_truth/generate.py` — the actual source of truth for what a "cause" is in this
dataset:

```python
EVENT_TYPES = ["product_outage", "marketing_cut", "competitor_launch", "inventory_shortage"]
```

**Four real classes, not eight.** `churn`, `pricing_change`, `seasonal`, `regional_economic` do not exist as
injectable causes anywhere in the generator — they are pure carryover from the Round 1 architecture report and
were never implemented. `marketing_reduction`/`competitor_activity`/`product_reliability` are the design doc's
renamed versions of the real `marketing_cut`/`competitor_launch`/`product_outage`.

**A more consequential finding: three of the four classes have no dimensional fingerprint at all**, traced
through the actual structural equations (`generate_episode`, lines ~231-314):

| event_type | Mechanism | Dimensional footprint |
|---|---|---|
| `inventory_shortage` | Cuts `product_weights[affected_product_idx]` — reallocates orders away from **one specific product** | **Real, strong**: concentrated deviation in exactly one `product` category |
| `marketing_cut` | Cuts `marketing_spend` → `traffic` → orders, company-wide | **None** — no region/segment/product is ever touched by this mechanism |
| `product_outage` | Cuts `reliability` → `conversion_rate` → orders, company-wide; also raises churn via the `satisfaction` EMA (delayed) | **None** — same company-wide shape |
| `competitor_launch` | Raises `competitor_activity` → `churn_rate` → shrinks the active-customer pool over time | **None on region/segment/product**, but **hits `active_customers_purchased_30d` before/more than `orders_count`/`revenue`**, unlike the other two |

`affected_segment` (40% chance, any event type, 1.5-4x multiplier) is an **orthogonal modifier independent of
cause** — it says "this event happened to concentrate in one segment," not "which cause this is." Using
`segment_spread_entropy` as a cause-discriminating feature (as both the design doc and the original Round 1
architecture report assumed) is not supported by how the generator actually works. Same conclusion, more
strongly, for `geo_spread_entropy`: no event type ever touches `region`. **These two features, imported wholesale
from the original architecture report, carry no real signal in this dataset** — this is exactly the kind of
claim this project's own process requires verifying against real behavior before asserting (`CLAUDE.md`), and it
was previously wrong.

`onset_type` is genuinely informative but **noisy by construction**: `_sample_onset` gives only 55% probability
to a class's "typical" onset (`marketing_cut`→step, `inventory_shortage`→step, `product_outage`→ramp,
`competitor_launch`→ramp) and splits the remaining 45% across `ramp/spike_decay/delayed` (or `step` for the
ramp-typical pair) uniformly. It is a lean, not a rule.

**Real event volume** (live query, 150 episodes): `marketing_cut` 53, `inventory_shortage` 39, `product_outage`
34, `competitor_launch` 26 — enough episodes exist to *evaluate* a classifier honestly, but training a proper
held-out multiclass model (feature extraction requires a live Stage 1→4 run per labeled episode, ~50-65s each)
is a multi-hour data-pipeline undertaking on top of the classifier itself, for a feature set that structurally
cannot separate 3 of 4 classes well no matter how it's trained.

## Scope decision — recommend rule-based, not trained

Given the verified ceiling above and the remaining time budget, **do not build the design doc's XGBoost + SHAP
pipeline.** A trained model over features with no real signal for 3 of 4 classes will not generalize better than
a stated heuristic, costs 6-8h of episode-generation-plus-training risk the night before the deadline, and adds
exactly the kind of "prompt-faked ML" surface the audit's own differentiation analysis (round2-topology-and-brief
§3) warns scores worse than an honest simpler system.

**Recommended (Tier A, ~2-3h): a small, explainable, threshold-based classifier**, using only the three real
signals traced above:

1. **Product concentration** (from Stage 4's `product` dimension slices, when the KPI has one): one category's
   `|deviation_pct|` far exceeds the others' → `inventory_shortage`, high confidence. This is the one
   near-deterministic signal and should be checked first.
2. **Which KPI moved most**: if `active_customers_purchased_30d` is in the cluster and shows the largest
   relative deviation, and `orders_count`/`revenue` lag or are smaller → lean `competitor_launch`. If
   `orders_count`/`revenue`/`units_sold` move together and `active_customers_purchased_30d` is flat or absent
   from the cluster → lean `{marketing_cut, product_outage}`.
3. **Onset shape** (a short trailing-window pull, same targeted fetch the design doc's §3.2 already scoped —
   only for the already-flagged window, not every slice): step → `marketing_cut`; ramp → `product_outage`.
   Weight this as a tie-breaker, not a primary signal, given the 55/45 noise.

**Output is a ranked probability-flavored dict over the 4 real labels** (not a single committed guess, matching
this project's existing significance/relevance/priority style of never discarding the losing hypotheses), plus
an honest `LOW`/`MEDIUM`/`HIGH` confidence tier reflecting how many of the three signals agree — a genuine,
inspectable "this is a heuristic with a stated ceiling" story for the report, in the same spirit as the
already-calibrated `0.30` candidate-rate threshold (`.claude/plans/SESSION-HANDOFF-2026-08-29.md` §5). This
should still be **measured against `injected_events` offline** (never fed to the running pipeline — same
held-out discipline as the empirically-calibrated threshold) so the report can state a real top-1/near-miss
accuracy number instead of an assumed one.

**Deferred (Tier B, 6-8h, not recommended before the deadline):** the design doc's trained XGBoost + SHAP
pipeline, corrected to the real 4-class taxonomy. Worth a paragraph in the report as "what we'd build with more
time and why" (the report outline already has this slot, §10 of the audit plan) — cite this plan's ceiling
analysis as the reason a heuristic was chosen deliberately, not for lack of time to write ML code.

**Also deferred, per the existing audit triage (unchanged):** Stage 5b (confounded-cause decomposer) and 5c
(cold-start/analogy handler), the two forks this stage's own README names — still cut for this deadline.
5a's own routing therefore has no live `BRANCH_5B_CONFOUNDED`/`BRANCH_5C_COLD_START` destination; on a split or
cold-start signal, 5a should say so honestly in its output (`routing_decision: "INCONCLUSIVE"` or similar) rather
than route to a stage that doesn't exist.

## Outcome (testable)

Given a real `DecompositionResult` (+ its source `StageThreeResult`) from Stage 4 for a cluster containing an
`inventory_shortage`-driven episode window, Stage 5a's product-concentration check fires and returns
`inventory_shortage` as the top hypothesis at `HIGH` confidence. Given a cluster from a `marketing_cut` or
`product_outage` episode, Stage 5a returns both as plausible with `LOW`/`MEDIUM` confidence and states the reason
(no dimensional fingerprint distinguishes them) rather than fabricating certainty — this is the honest-abstention
story, verified against real episodes' actual `injected_events` labels (offline scoring only).

## Files to read first

1. `pipeline/simulator/layer1_ground_truth/generate.py` lines 41-49, 92-135, 220-260, 290-315 — the real event
   mechanics this whole plan is grounded in; re-read before changing any signature feature, the same way Stage
   4's plan made schema.sql the taxonomy source of truth
2. `pipeline/stage04_dimensional_decomposition/models.py`, `stage4.py` — the real `DecompositionResult`/
   `SliceResult` input contract
3. `pipeline/stage03_cross_kpi_correlation/models.py`, `dag.py` — `StageThreeResult`, and which KPI pairs can
   even appear together in one cluster (bounds what "which KPI moved most" can compare)
4. `pipeline/stage11_narration/narrate.py`'s `build_fact_sheet` — Stage 5a's output needs to slot into that fact
   sheet eventually (a `top_causes` field), so shape its output with that consumer in mind
5. This plan's ceiling analysis above — do not re-derive `geo_spread_entropy`/`segment_spread_entropy` as
   features without re-reading why they were dropped

## Files to create

```
pipeline/stage05a_fingerprint_classification/
  README.md              — update from "no code yet" to real status, link this plan
  requirements.txt        — psycopg2-binary, python-dotenv (no numpy/pandas needed for Tier A's threshold logic)
  signatures.py            — the three signal functions (product_concentration, dominant_kpi_shift, onset_lean),
                             pure functions over a DecompositionResult + a short trailing timeline, no DB access
  onset_fetcher.py         — the short trailing-window pull for the flagged window only (reuses stage3/4's
                             sys.path-eviction bridge pattern to reach Stage 1's canonical timeline)
  classifier.py            — combines the three signals into a ranked {event_type: score} dict + confidence tier,
                             no trained artifact, no joblib
  stage5a.py               — run_stage5a(cur, stage3_result, decomposition_results) -> FingerprintResult; CLI
                             entrypoint re-deriving Stage 3+4 output for a given --episode-id, same style as
                             stage3.py/stage4.py
  models.py                — FingerprintResult dataclass: episode_id, cluster_id, cause_scores (dict, sums to 1),
                             top_cause, confidence ("LOW"/"MEDIUM"/"HIGH"), signals_used (list, for the analyst
                             persona's "why" narration)
  eval_against_ground_truth.py — offline-only script: for N real episodes with an injected_events row, run
                             Stage 3->4->5a and compare top_cause to the real event_type; prints an accuracy
                             number and a confusion table. NEVER imported by stage5a.py or any runtime path —
                             same isolation as the already-existing offline threshold calibration work.
  test_stage5a.py           — offline (signal functions on synthetic fixtures) + live (real episode, asserts
                             inventory_shortage detection fires when a real product-concentrated window exists)
```

## Implementation steps

1. **`signatures.py` — `product_concentration(decomposition_result) -> (product_or_None, score)`**: for each KPI
   with `product` in its applicable dimensions, take that KPI's `product`-dimension `SliceResult`s, compute each
   slice's `|deviation_pct|` share of the total (only `OBSERVED` slices); if the top share exceeds a stated
   threshold (start at 0.6 — this needs a real number from Step 6's live check, not a guessed one) over the
   second-highest, return that `slice_value` and the margin as score. *Validation:* synthetic fixture, one
   dominant product slice vs three flat ones, confirm it fires; four flat ones, confirm it returns `None`.

2. **`signatures.py` — `dominant_kpi_shift(decomposition_result) -> "customers_first" | "orders_first" | None`**:
   compare `active_customers_purchased_30d`'s slice deviations (company-wide daily view, not per-dimension — use
   the un-sliced Stage 2/3 series already available on `stage3_result`, not a new query) against
   `orders_count`/`revenue`'s. *Validation:* needs the real question answered live first — does a real
   `competitor_launch` episode actually produce a Stage 3 cluster containing `active_customers_purchased_30d`
   alongside `orders_count`/`revenue`? Check this against 2-3 real `competitor_launch` episodes before writing
   the comparison logic — if clustering rarely links them (the DAG-constrained lag/direction test may not
   confirm the churn-mediated relationship within Stage 3's window), this signal may need to fall back to
   `active_customers_purchased_30d`'s own trend even when it's a `SINGLE_KPI` result, not clustered.

3. **`onset_fetcher.py`**: mirrors `stage04_dimensional_decomposition/stage2_bridge.py`'s sys.path-eviction
   pattern one level further (Stage 5a → Stage 1) to pull the flagged window's own daily series (not a slice —
   the same canonical series Stage 2 scored) for a simple day-1-vs-day-7 ratio, same shape as the design doc's
   `onset_shape_ratio` (§3.2) but against the real series, not a pandas one. *Validation:* a known step-onset
   real episode window vs a known ramp-onset one, confirm the ratio meaningfully differs.

4. **`classifier.py` — `classify(product_signal, kpi_shift_signal, onset_signal) -> {event_type: score}` +
   confidence tier**: start simple — product signal alone determines `inventory_shortage` at `HIGH` if it fires;
   otherwise split remaining mass across the other 3 by which of signals 2/3 agree, confidence `MEDIUM` if both
   lean the same way, `LOW` if they disagree or are absent. *Validation:* table-driven unit tests, one row per
   signal combination worth naming.

5. **`stage5a.py`**: wires 1-4 into `run_stage5a`, CLI re-deriving Stage 3→4 for `--episode-id` (same re-
   derivation style as `stage4.py`'s own CLI). *Validation:* runs end-to-end on episode 1 without crashing.

6. **`eval_against_ground_truth.py`**: the number that makes Tier A's "explainable heuristic with a measured
   ceiling" claim real instead of assumed. Run against ~20-30 real episodes spanning all 4 event types (query
   `injected_events` directly — this script is explicitly offline-only, never on the runtime path), print top-1
   accuracy and a 4x4 confusion table. **This step is what calibrates the 0.6 threshold in Step 1** — same
   discipline as the project's existing `0.30` candidate-rate calibration, run this before finalizing the
   threshold, not after.

7. **`test_stage5a.py`**: offline signal-function tests (steps 1/2/4's fixtures) + one live check — run
   `run_stage5a` against a real `inventory_shortage` episode/window and assert `top_cause == "inventory_shortage"`
   at `HIGH` confidence. Must print `OK`.

8. **Update `stage05a_fingerprint_classification/README.md`** — real status, this plan linked, and the same
   "here's exactly where this diverges from the old design doc and why" honesty precedent Stage 2-4's READMEs
   already set.

## Tests and validation gate

```bash
cd pipeline/stage05a_fingerprint_classification
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_stage5a.py            # must print OK
.venv/bin/python eval_against_ground_truth.py --n-episodes 30   # prints accuracy + confusion table, not gated on a fixed pass threshold -- report whatever the real number is
```

## Acceptance criteria

- [ ] `geo_spread_entropy`/`segment_spread_entropy` are NOT used as cause-discriminating features — the plan's
      ceiling analysis is carried into the code as a comment, not silently dropped and forgotten
- [ ] Product-concentration threshold (0.6 starting value) is calibrated against a real `eval_against_ground_truth.py`
      run before being treated as final, not left as a guess
- [ ] `run_stage5a` never queries `injected_events` — only `eval_against_ground_truth.py` does, and it is not
      imported by any runtime module
- [ ] Output always carries a ranked dict over all 4 real labels plus a stated confidence tier, never a single
      unqualified guess
- [ ] `test_stage5a.py` passes, offline and live
- [ ] `eval_against_ground_truth.py`'s real accuracy/confusion numbers are copied into the report verbatim, not
      rounded up or cherry-picked
- [ ] README updated, PR opened against `develop`

## Risks

1. **The product-concentration threshold is a single hand-picked number (0.6) until Step 6 calibrates it.**
   Don't ship it uncalibrated — this is exactly the F1/F9-class mistake (asserting a number without checking it
   against real output) this project has already been burned by twice.
2. **Signal 2 (`dominant_kpi_shift`) depends on empirical clustering behavior not yet confirmed** — see Step 2's
   validation note. If `active_customers_purchased_30d` rarely clusters with `orders_count`/`revenue` under
   `competitor_launch`, this signal degrades to "was `active_customers_purchased_30d` itself flagged" rather than
   a true relative comparison, and confidence should reflect that honestly.
3. **This is still a 2-3 hour scope item on a night when 7-11.5 hours of non-code deliverables haven't started.**
   If the report/PPT/video are behind schedule when this plan is picked up for implementation, re-triage: a
   working Stage 4 + an honest "Stage 5a: designed, not built, here's why" line in the report (this plan itself
   as the artifact) is a legitimate, defensible fallback — the same call already made for Stages 5b/5c/6-9.
