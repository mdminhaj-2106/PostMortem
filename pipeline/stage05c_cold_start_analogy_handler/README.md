# Stage 5c — Cold-Start / Analogy Handler

**Job:** given Stage 4's dimensional decomposition, for any slice Stage 4 itself refused to fingerprint (`eligibility` in `LIMITED_HISTORY`/`INSUFFICIENT_DATA`, `unusualness_percentile: None`), borrow a relative-deviation reference distribution and score the slice's own deviation against it -- an honestly-tagged `BORROWED` signal instead of nothing, or an honest abstention if no reference exists.

**Status:** First implementation slice built and passing (`test_stage5c.py`, offline + live-DB). Importable Python functions + a CLI, no FastAPI wiring yet.

**Design report:** [`docs/02-stage-design-reports/stage5c-implementation-plan.md`](../../docs/02-stage-design-reports/stage5c-implementation-plan.md) -- **not usable as written**: its golden example (a declared per-slice-value analog, e.g. "Product A borrows from Product B") assumes eligibility varies by slice_value within one decomposition run. Tracing the real code shows it doesn't -- see the implementation plan below for the corrected mechanism.
**Implementation plan:** [`.claude/plans/stage5c-cold-start-analogy-handler.md`](../../.claude/plans/stage5c-cold-start-analogy-handler.md)

**The finding that drove the redesign (verified against real code, not assumed):** Stage 4's `decomposer.py` sets `day_range = range(max(0, window_start-30), window_end+1)` identically for every `(kpi_name, dimension, slice_value)` in one `decompose_cluster` call -- the window comes from one `stage3_result`, shared by everything in the cluster. So `eligibility.assess_eligibility`'s `n_usable` count, and therefore the `LIMITED_HISTORY`/`INSUFFICIENT_DATA` tier itself, land the *same* for every slice_value of a given `(kpi, dimension)` together (Stage 4's own README already found this live for region slices; this stage's plan confirms it's structural, not incidental). The design doc's "Product A is thin, Product B is solid, borrow across them" scenario is therefore unreachable with this codebase's real data model -- a same-window sibling slice is never a valid analog, because it's equally thin. **User decision (2026-08-30):** borrow from the *same* slice's own history in *other* episodes instead -- a cross-episode corpus reference distribution per `(kpi_name, dimension, slice_value)`, built offline once. No declared `analogy_groups.yaml`, no per-slice team decision required.

**Covers in this slice:**
- `models.py` -- `BorrowedAttribution` (`kpi_name`, `dimension`, `slice_value`, `deviation_pct`, `borrowed_percentile` nullable, `reference_sample_count`, `status` -- `BORROWED`/`NO_REFERENCE_AVAILABLE`, `analog_source` fixed `CROSS_EPISODE_CORPUS`, `confidence_tier` fixed `BORROWED`) with `__post_init__` structurally coupling `status`/`borrowed_percentile` nullness -- abstention is a type-level guarantee, not incidental. `Stage5cResult` (`episode_id`, `cluster_id`, `attributions`).
- `reference_builder.py` -- offline: scans `--n-episodes` real episodes (default 20), and for each `(kpi_name, dimension, slice_value)` reachable via Stage 4's own `dimension_config.DIMENSION_APPLICABILITY` + `slice_fetcher.distinct_slice_values`, pools the slice's own mature (`day_offset >= 30`, matching `eligibility.MIN_OBSERVATIONS_FOR_ELIGIBLE`) relative deviations (`residual/expected`) across every sampled episode into `reference/artifacts/reference.json`. Same offline-JSON-artifact shape as Stage 5b's `basis/build_bases.py` -- no `numpy`/`joblib` needed here, just list pooling.
- `borrowed_percentile.py` -- the actual borrow-and-score mechanism: builds a synthetic `residuals`-shaped list with the reference samples as "prior history" and the thin slice's own `deviation_pct` as the final entry, then calls Stage 2's real `score_unusualness` and reads off that entry's score -- the exact percentile-rank function Stage 2/4/5a all already reuse, never reimplemented, just handed a borrowed reference list instead of the slice's own causal history.
- `stage2_bridge.py` / `stage3_bridge.py` / `stage4_bridge.py` -- re-export Stage 2/3/4's real functions (`compute_residuals`/`score_unusualness`, `run_stage3`, `run_stage4`/`dimension_config`/`slice_fetcher`), same `sys.path`/`sys.modules`-eviction pattern as every other cross-stage bridge in this repo -- a seventh stage now needing it.
- `output_schema.py` -- rejects free text outside the declared enums, belt-and-suspenders with `models.py`'s own `__post_init__`.
- `stage5c.py` -- orchestrator (`run_stage5c`): filters a `DecompositionResult`'s slices to `eligibility in (LIMITED_HISTORY, INSUFFICIENT_DATA)` with a real `deviation_pct`, looks each up in the reference, emits one `BorrowedAttribution` per thin slice -- kept structurally separate from Stage 5a's `FingerprintResult`/Stage 5b's `ConfoundedAttributionResult`, never merged. CLI entrypoint.

**A real finding from live verification (episode 1, `active_customers_purchased_30d`, window 9-14 -- the same fixture Stage 4's own README documents):** every region slice in that decomposition lands `LIMITED_HISTORY` together, and `run_stage5c` correctly borrows a real percentile for each from a small 5-episode corpus reference built on the fly in `test_stage5c.py`'s live check.

**Output contract (→ Stage 6/7):** `models.Stage5cResult` -- a `confidence_tier="BORROWED"` value that Stage 7 (not yet built) will need to structurally cap below `Known`/`Likely` once it exists; not enforced here, a note for whoever builds Stage 7 (design doc §6's rule, carried forward).

**Consumes:** Stage 4's `models.DecompositionResult` (per-slice `eligibility`/`deviation_pct`) and Stage 2's `compute_residuals`/`score_unusualness` (via `stage2_bridge.py`).

**Cross-stage plumbing added alongside this stage (see `stage05a_fingerprint_classification/README.md`):** Stage 5a's `signatures.product_concentration` now excludes `LIMITED_HISTORY`/`INSUFFICIENT_DATA` product slices (it previously fingerprinted whatever `deviation_pct` Stage 4 attached to a thin slice, even though Stage 4 itself refused to attach a percentile), and `stage5a.py` gained `run_stage5a_and_5c` -- runs both stages on one `DecompositionResult` and returns `(FingerprintResult, Stage5cResult)` as a pair, routing per-slice rather than assuming a cluster is uniformly thin or uniformly solid (even though real data verifies it always is one or the other, uniformly, per the finding above).

**Deferred, not implemented (per the plan, unchanged):**
- **Declared `analogy_groups.yaml` / per-slice-value analog pairing** -- dropped, not deferred: actively wrong given how eligibility actually works in this codebase (see the finding above), not a future team decision waiting to happen.
- **Cause-prior borrowing (design doc §5)** -- stretch goal, depends on the Learning & Memory cross-cutting service, which has zero code (`pipeline/cross_cutting/learning_memory/` is a README only).
- FastAPI wiring -- same phased-build reasoning as Stages 1-5b.
- **A seventh stacked cross-stage import** (Stage 5c -> Stage 2 directly, Stage 5c -> Stage 4 -> Stage 2 for the CLI/reference-builder paths). `architecture.md`'s Known Risks already called a real package overdue at the fourth stage; unchanged conclusion.

**Run:**
```bash
cd pipeline/stage05c_cold_start_analogy_handler
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python reference_builder.py --n-episodes 20      # one-time (or re-run to widen), writes reference/artifacts/reference.json
.venv/bin/python test_stage5c.py                            # must print OK (offline + 1 live end-to-end run)
.venv/bin/python stage5c.py --episode-id 1
```
