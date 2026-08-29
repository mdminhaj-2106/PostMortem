# Stage 2 — Per-KPI Significance Detection (Relevance Extraction & Change Classification)

**Job:** for each individual KPI stream, decide Normal / Emerging / Significant / Structural. Runs independently per metric.

**Status:** First implementation slice built and passing (`test_stage2.py`, offline + live-DB, including a real scoring check against `injected_events`). Importable Python functions + a CLI, no FastAPI wiring yet.

**Design report:** [`docs/02-stage-design-reports/stage2-relevance-extraction-architecture.md`](../../docs/02-stage-design-reports/stage2-relevance-extraction-architecture.md)
**Implementation plan:** [`.claude/plans/stage2-relevance-extraction.md`](../../.claude/plans/stage2-relevance-extraction.md)

**Covers in this slice:**
- Layer 1 — `eligibility.assess_eligibility`: `ELIGIBLE` / `LIMITED_HISTORY` / `LOW_CONFIDENCE` / `INSUFFICIENT_DATA`
- Layer 2 — `baseline.compute_residuals`: one rolling-median baseline (no STL/seasonal decomposition — see plan Scope/Out)
- Layer 3 — `unusualness.score_unusualness`: causal empirical percentile against each KPI's own prior residuals (never looks at future data)
- Broad candidate selection — `candidate_selection.select_candidates`, percentile-threshold, **`target_candidate_rate=0.30` (not the originally-planned 0.15)** — empirically calibrated against a real injected event; see the comment in `candidate_selection.py` for why 0.15 essentially never fired on this project's noisy daily KPIs
- Layer 4 — `business_importance.assess_importance`: declared criticality + the one declared relationship edge, no fabricated formulas
- Layer 5 — `relationship_graph.py`: the single honest edge this project's 2-KPI universe supports (`active_customers_purchased_30d → revenue`), declared once and traversed **both** ways — `related_kpis` derives the reverse (`DOWNSTREAM_OF`) edge rather than requiring each edge be written twice
- Layer 6 — `relevance.resolve_relevance`: design doc §14's rule matrix, one test case per row
- Layer 7 — `classification.classify_trajectory`: `EMERGING`→`SIGNIFICANT`→`STRUCTURAL` state machine, run as a full-episode offline backtest
- `ingest.py`: pulls a KPI timeline by calling Stage 1's real `reconcile.py` functions per day — imports it via a `sys.path` insert (no root package exists yet), and carefully evicts the modules that would otherwise collide with Stage 2's own same-named files (`models.py`, `materiality.py`, etc.) from `sys.modules` after the import — see the comment in `ingest.py` if touching this.

**A real finding from live verification, not just the automated tests:** a naive `sys.path` insert in `ingest.py` initially made Stage 1's `models.py` permanently shadow Stage 2's own `models.py` in Python's import cache — `from models import StageTwoResult` broke with an `ImportError` the module didn't even mention. Fixed by evicting the colliding names from `sys.modules` right after grabbing what's needed from Stage 1. Separately, the first live scoring check (a genuine, isolated `marketing_cut` event) showed the originally-planned `target_candidate_rate=0.15` essentially never let a real sustained revenue drop survive 3 consecutive candidate days — daily revenue in this simulator is noisy enough (small per-episode customer counts, Poisson order counts, and occasional 2-3x volatility regime blocks that can swamp a real event's residual for a week or two) that the default needed raising to 0.30 before Stage 2 reliably reacted to a real cause. See `candidate_selection.py`'s comment for the specific episode this was verified against.

**Layer 5 was structurally dead until 2026-08-29 (audit finding F3).** `run_stage2`'s `other_kpi_candidates` parameter was never passed by any caller, *and* `related_kpis` only resolved the forward edge — so `KNOWN_RELATIONSHIP` evidence, `cluster_id`, and `related_candidates` were provably always empty (verified live: 0 occurrences across 32 days of episode 8). Both halves are fixed; Stage 3 now threads each KPI's candidate days into the other, and `test_stage3.py::test_relationship_evidence_is_live_not_dead` asserts the evidence appears on real data so it cannot silently die again. Every unit test passed the whole time it was broken — a passing `test_*.py` is not evidence that a stage runs.

**Output contract (→ Stage 3):** `models.StageTwoResult` — matches design doc §18 field-for-field, flattened (not nested) per this project's dataclass convention.

**Known interface mismatch with Stage 4's plan (confirmed, not just flagged):** Stage 4's design report §4 expects Stage 2 to expose `eligibility_gate(series: pd.Series, ...)`, `expected_behavior(...)`, and `unusualness_percentile(...)` operating on `pandas.Series`. What actually exists is `eligibility.assess_eligibility(timeline)`, `baseline.compute_residuals(timeline, window)`, and `unusualness.score_unusualness(residuals)`, all operating on plain `[(day_offset, ReconciledValue_or_None), ...]` lists — no pandas dependency was added (this project's KPI histories are at most ~120 points per episode; a list is enough, and the design doc's own §4 already anticipated this might not match: *"If Stage 2's actual functions differ, this is the adapter layer to write — do not fork the logic."* Stage 4 should write that adapter against the real signatures above, not re-derive eligibility/baseline/unusualness logic itself.

**Consumes:** Stage 1's `reconcile.py` (via `ingest.py`) for `revenue` and `active_customers_purchased_30d` — the only 2 KPIs Stage 1 currently reconciles (plan Risk #2).

**Run:**
```bash
cd pipeline/stage02_significance_detection
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_stage2.py            # must print OK
.venv/bin/python stage2.py --episode-id 1 --kpi revenue
```
