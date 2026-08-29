# Stage 5a — Fingerprint / Cause-Signature Classification

**Job:** given Stage 4's dimensional decomposition, hypothesize which of the 4 real injectable causes drove the movement -- a ranked, never-single-guess dict over all 4, plus an honest confidence tier.

**Status:** First implementation slice built and passing (`test_stage5a.py`, offline + live-DB). Importable Python functions + a CLI, no FastAPI wiring yet.

**Design report:** [`docs/02-stage-design-reports/stage5a-implementation-plan.md`](../../docs/02-stage-design-reports/stage5a-implementation-plan.md) -- **not usable as written**: assumes an 8-class taxonomy, a `conversion_rate` KPI that doesn't exist as a declared KPI, `North/Enterprise` region/segment values Stage 4 already corrected, ISO-date windows, and a trained XGBoost + SHAP pipeline. See the implementation plan below for the corrected mechanism.
**Implementation plan:** [`.claude/plans/stage5a-fingerprint-classification.md`](../../.claude/plans/stage5a-fingerprint-classification.md)

**Scope decision (Tier A, not Tier B):** the real generator (`pipeline/simulator/layer1_ground_truth/generate.py`) injects exactly 4 cause types (`product_outage`, `marketing_cut`, `competitor_launch`, `inventory_shortage`), and tracing the real structural equations shows only `inventory_shortage` leaves a dimensional fingerprint at all -- it's the only event type that ever touches `product`. `marketing_cut`/`product_outage`/`competitor_launch` all move KPIs company-wide with no region/segment/product footprint, so `geo_spread_entropy`/`segment_spread_entropy` (both imported wholesale from the Round 1 architecture report) carry no real cause-discriminating signal in this dataset -- verified against the real generator, not assumed. A trained multiclass model over features with no real signal for 3 of 4 classes would not generalize better than a stated heuristic; a small, explainable, threshold-based classifier was chosen deliberately. See the plan's ceiling analysis for the full trace.

**Covers in this slice:**
- `models.py` -- `FingerprintResult` (`episode_id`, `cluster_id`, `cause_scores` dict summing to 1 over the real 4-class taxonomy, `top_cause`, `confidence`, `signals_used`)
- `signatures.py` -- the three real signal functions, pure (no DB access):
  - `product_concentration` -- the one near-deterministic signal: a product slice's share of total `|deviation_pct|` clearing a margin over the runner-up fires `inventory_shortage`
  - `dominant_kpi_shift` -- `active_customers_purchased_30d` moving more than `orders_count`/`revenue` leans `competitor_launch` (the only event type that drives churn before/instead of orders); the reverse leans `{marketing_cut, product_outage}`
  - `onset_lean` -- a day-1-vs-day-7 `|residual|` ratio tie-breaks `marketing_cut` (step) vs `product_outage` (ramp) only -- does not discriminate the other two causes
- `onset_fetcher.py` -- bridges to Stage 2's real `ingest.load_kpi_timeline` + `baseline.compute_residuals` (same `sys.path`/`sys.modules`-eviction pattern as Stage 3/4's own bridges) for the unsliced, company-wide series both `dominant_kpi_shift` and `onset_lean` need
- `classifier.py` -- combines the three signals into a ranked `{event_type: score}` dict + confidence tier: `HIGH` only when product concentration fires, `MEDIUM` when `dominant_kpi_shift` + `onset_lean` agree on a specific cause, `LOW` otherwise -- never a single unqualified guess, never zeroing out a cause on silence
- `stage3_bridge.py` / `stage4_bridge.py` -- re-export Stage 3/4's real `run_stage3`/`run_stage4`, so `stage5a.py`'s CLI can re-derive a real cluster + decomposition instead of a hand-built fixture (same pattern as Stage 4's own bridges)
- `stage5a.py` -- orchestrator (`run_stage5a`) + CLI entrypoint
- `eval_against_ground_truth.py` -- offline-only accuracy/confusion scoring against `injected_events`; never imported by any runtime module

**Cold-start plumbing added once Stage 5c existed (this slice, follow-up to the original build):** `product_concentration` now excludes `LIMITED_HISTORY`/`INSUFFICIENT_DATA` product slices -- previously it fingerprinted whatever `deviation_pct` Stage 4 attached to a thin slice, even though Stage 4 itself already refused to attach a percentile to it. `stage5c_bridge.py` re-exports Stage 5c's real `run_stage5c`/`load_reference`/`build_reference` (a sideways bridge -- 5a and 5c are siblings off Stage 4, not a downstream/upstream pair, same reasoning Stage 5b already used bridging into 5a despite the numeric order), and `stage5a.py`'s new `run_stage5a_and_5c(cur, episode_id, stage3_result, decomposition_result, reference)` runs both and returns `(FingerprintResult, Stage5cResult)` as a pair -- never merged into one confidence number. In practice Stage 4's eligibility is uniform per `(kpi, dimension)` across a whole decomposition (see `stage05c_cold_start_analogy_handler/README.md`), so a cluster ends up served by one or the other, not truly mixed -- but the routing itself is per-slice, not a hardcoded mode flag, so it stays correct if that ever stops holding.

**A real finding from live verification, not the plan's a-priori assumption:** most real `inventory_shortage` events never clear Stage 2/3's company-wide significance bar at all -- a single product's weight cut is too small a fraction of total revenue/orders to register as a company-wide flagged window, even at `severe` severity. Live search across 7 episodes with a real `inventory_shortage` event found only episode 15 produces a Stage-3-flagged cluster that actually overlaps the event window (`cluster_15_93_94`, day 93-94) -- and episode 15 happens to have only 2 distinct product categories total, which is why `product_concentration`'s share metric clears the threshold so cleanly there (0.76) but would behave differently with a more typical product catalog. `test_stage5a.py`'s live check documents this fixture and why it had to be found empirically rather than assumed from any injected event.

**`eval_against_ground_truth.py` — not completed at full scale, stated rather than hidden:** a `--n-episodes 30` run was started but takes 45-90+ minutes (each episode re-derives the full 5-KPI Stage 3 DAG walk, ~100-150s live) and was stopped before finishing given this project's time budget the night before submission; a second attempt also hit one transient Neon `SSL SYSCALL`/connection drop mid-run (not a code bug). `PRODUCT_CONCENTRATION_THRESHOLD` (`signatures.py`) therefore stays at the plan's stated starting value (`0.6`), uncalibrated against a real accuracy number — this is an open gap, not a silently-skipped one (see Known gaps below). What *is* verified live: `test_stage5a.py`'s single real-episode check (episode 15, `cluster_15_93_94`) confirms the mechanism actually fires correctly (`inventory_shortage` at `HIGH` confidence, product-concentration share 0.76) — a real positive case, just not a full-dataset accuracy/confusion sweep.

**Output contract (→ Stage 11):** `models.FingerprintResult` -- shaped for `stage11_narration/narrate.py`'s `build_fact_sheet` to add a `top_causes` field alongside its existing `top_slices`, once that stage wires it in (not done in this slice -- Stage 11 isn't part of Stage 5a's scope).

**Consumes:** Stage 4's `models.DecompositionResult` (for `product_concentration`) and Stage 3's `models.StageThreeResult` (window bounds + `kpi_names`, for the KPI-shift/onset fetches via `onset_fetcher.py`).

**Deferred, not implemented (per the plan, unchanged from the existing audit triage):**
- **Tier B** -- a trained XGBoost + SHAP pipeline over the corrected 4-class taxonomy. Worth building with more time; this plan's ceiling analysis is the reason a heuristic was chosen deliberately, not for lack of time.
- **Stage 5b** (confounded-cause decomposer) -- 5a has no live `BRANCH_5B_CONFOUNDED` destination, so on a split signal it says so honestly (`LOW` confidence with an even split) rather than routing to a stage that doesn't dispatch from here. (Stage 5b exists and is built, just not wired as an automatic dispatch target from 5a's own code.)
- **Stage 5c** (cold-start/analogy handler) is no longer undispatched -- see the cold-start plumbing note above. `run_stage5a_and_5c` is opt-in (a separate function from `run_stage5a`), not automatically invoked by `run_stage5a` itself.
- FastAPI wiring -- same phased-build reasoning as Stages 1-4.
- **A fifth stacked cross-stage import** (Stage 5a -> Stage 2 directly via `onset_fetcher.py`, plus Stage 5a -> Stage 3 -> Stage 2 and Stage 5a -> Stage 4 -> Stage 2/Stage 3 for the CLI/eval paths) via the `sys.path`/`sys.modules`-eviction pattern. `architecture.md`'s Known Risks already flagged this as overdue at the fourth stage; a real package is a stronger case now, still not folded into this slice.

**Run:**
```bash
cd pipeline/stage05a_fingerprint_classification
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_stage5a.py                          # must print OK (offline + live Stage 3->4->5a(+5c) runs)
.venv/bin/python stage5a.py --episode-id 1                # loads stage05c_.../reference/artifacts/reference.json;
                                                            # build it first (see that stage's README) if missing
.venv/bin/python eval_against_ground_truth.py --n-episodes 30   # offline-only, prints real accuracy + confusion table
```
