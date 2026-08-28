# Stage 3 — Cross-KPI Correlation & Prioritization

**Job:** given several KPIs flagged as moved in the same window by Stage 2, decide whether they're one underlying story told twice or genuine coincidences, and rank which cluster deserves investigation first by business impact.

**Status:** First implementation slice built and passing (`test_stage3.py`, offline + live-DB, including a real clustering check against `injected_events`). Importable Python functions + a CLI, no FastAPI wiring yet.

**Design report:** [`docs/02-stage-design-reports/stage3-cross-kpi-correlation-prioritization.md`](../../docs/02-stage-design-reports/stage3-cross-kpi-correlation-prioritization.md)
**Implementation plan:** [`.claude/plans/stage3-cross-kpi-correlation.md`](../../.claude/plans/stage3-cross-kpi-correlation.md)

**Covers in this slice:**
- `dag.py` — the declared DAG: Stage 2's one real edge (`active_customers_purchased_30d → revenue`), extended with an expected-lag window and expected-direction annotation
- `grouping.py` — the actual clustering test: DAG adjacency + same-direction co-movement within the expected lag, using each KPI's own flagged (`SIGNIFICANT`/`STRUCTURAL`) day-windows from Stage 2. Failed grouping (no adjacent flag, wrong direction, or out-of-lag) always falls back to standalone results — never a forced cluster (design doc §2, reusing Stage 1 Scenario 6's under-merge-is-safer principle)
- `priority.py` — revenue-equivalent dollar scoring: Case 1 (revenue in cluster) uses revenue's own observed dollar delta directly, reusing Stage 2's baseline residuals; Case 2 (revenue not in cluster) is explicitly gated `PROJECTED_UNAVAILABLE` rather than fabricated — see Known Gaps below. Axis 1 (Stage 2 confidence) gates *ranking* via `rank()` without discarding results from the output
- `stage2_bridge.py` — pulls Stage 2's real classified results and reuses Stage 2's own `ingest`/`baseline` for the raw dollar residual, via the same `sys.path` + `sys.modules`-eviction pattern Stage 2 established for importing Stage 1 (now one stage deeper — see Known Gaps)
- `stage3.py` — orchestrator: episode → `list[StageThreeResult]`, CLI entrypoint

**Known gaps in this slice (matches this project's real KPI universe, not an oversight):**
- **Case 2 (projected priority) is structurally untestable right now.** Stage 1 only reconciles 2 KPIs with one declared edge, so a lone `active_customers_purchased_30d` cluster without `revenue` has no declared coefficient to project a dollar figure through — building one would mean inventing an unjustified formula (the same reasoning Stage 2's own plan already used to reject its Layer 4 §9.1/§9.4 gaps). Revisit once Stage 1 tracks `orders_count`/`avg_order_value` as their own KPIs.
- **Multi-path combination (design doc §6, joint vs. disjoint) is out of scope** — needs a 3+-member cluster, which this project's 2-KPI universe can't produce (max cluster size = 2).
- **Composite-KPI synthesis before handoff is not built, deliberately** — the design doc itself rejects this (§7); the full untouched cluster passes through as-is.
- **A third stacked cross-stage import** (Stage 3 → Stage 2 → Stage 1) via the `sys.path`/`sys.modules`-eviction pattern. `architecture.md`'s Known Risks already flagged consolidating into a real package as overdue "once a third stage needs the same cross-import" — that threshold is now met.
- **`grouping_basis` reason attribution is asymmetric.** `attempt_cluster` computes the precise reason (`SEPARATE_NO_ADJACENT_KPI` vs. `SEPARATE_NO_CORRELATION`) only from the DAG-key KPI's side (`active_customers_purchased_30d`). An unclustered `revenue` window falls back to a coarser guess (`SEPARATE_NO_CORRELATION` whenever the other KPI flagged *anywhere* in the episode, even nowhere near this window) rather than running the same lag-aware check symmetrically. Both labels still correctly mean "not clustered" — this only affects which of the two failure-reason labels a lone `revenue` window gets, not whether real KPIs ever get force-clustered incorrectly.
- **Performance:** each KPI's timeline gets ingested twice per Stage 3 run (once inside `stage2.run_stage2`, once again in `stage2_bridge.load_dollar_residuals` for the raw dollar residual `run_stage2` doesn't expose) — 4 full ingestion passes per episode across 2 KPIs. Fine for a single-episode demo; the live test bounds each candidate episode to a ~35-day window around its injected event and caps the episode loop at 5, rather than sweeping full 120-day episodes across every qualifying candidate.

**Output contract (→ Stage 4):** `models.StageThreeResult` — matches design doc §8 field-for-field, flattened per this project's dataclass convention.

**Consumes:** Stage 2's `stage2.run_stage2`, `ingest.load_kpi_timeline`, and `baseline.compute_residuals` (via `stage2_bridge.py`) for `revenue` and `active_customers_purchased_30d`.

**Run:**
```bash
cd pipeline/stage03_cross_kpi_correlation
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_stage3.py            # must print OK
.venv/bin/python stage3.py --episode-id 1
```
