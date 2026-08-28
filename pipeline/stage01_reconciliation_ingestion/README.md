# Stage 1 — Data Reconciliation & Ingestion

**Job:** pull from heterogeneous sources at different grains/cadences and normalize into one canonical event stream. Nothing downstream can trust its inputs until this exists.

**Status:** First implementation slice built and passing (`test_reconcile.py`, offline + live-DB). Importable Python functions + a CLI, no FastAPI wiring yet (per the plan's explicit scope).

**Design report:** [`docs/02-stage-design-reports/stage1-reconciliation-design.md`](../../docs/02-stage-design-reports/stage1-reconciliation-design.md)
**Implementation plan:** [`.claude/plans/stage1-reconciliation-ingestion.md`](../../.claude/plans/stage1-reconciliation-ingestion.md) — module breakdown, build order, first-slice scope.

**Covers in this slice:**
- Scenario 1 (conflicting values) — `reconcile.reconcile_conflicting_values`: materiality gate → Semantic Contract bias correction → agree (exact/aggregated) or anchor-on-billing-and-widen (triangulated)
- Scenario 2 (definitional mismatch) — `reconcile.reconcile_definitional_active_customers`: emits `active_customers_purchased_30d` (billing) and `active_customers_interacted_30d` (crm) as two separate features, never collapsed
- Scenario 4, partial gap only — `reconcile.reconcile_partial_gap_revenue`: when marketing's `attributed_revenue` is dark but billing's revenue is present, triangulates straight from billing
- Scenario 5 (calendar misalignment) — `reconcile.reconcile_calendar_misaligned_active_customers`: uses `calendar_dimension.bucket_day`/`billing_cycle_end_day` to align billing's daily active_customers against marketing's billing-cycle snapshot at the cycle's actual snapshot day (not an arbitrary day inside the cycle — the marketing view snapshots once per cycle, not once per day)
- Scenario 6 (entity/join-key mismatch) — `identity_resolution.resolve_customer_identities`: single-field Fellegi-Sunter-style scoring (`crm_account_id` vs `customer_id`, the only identifying field Layer 2 provides); any mismatch (duplicate or near-miss) lands in `ambiguous`, never silently auto-merged
- KPI Semantic Contract — `semantic_contract.py`, declared per-source/per-metric metadata for `billing_system`, `crm_system`, `marketing_system`, including the bias-correction factors that match `views.sql`'s 0.87/0.80 exactly

**Deferred (see the plan's Scope/Risks section):** Scenario 3 (late-arriving history — Layer 2 doesn't produce this data yet), Scenario 4's total-gap forecast reconciliation and Scenario 7 (both need Stage 2's changepoint engine, which doesn't exist yet), SQL-lineage auto-detection (not needed while 3 sources are hand-authored), FastAPI wiring, restatement/versioning logic beyond the `version`/`restated_from_version` fields existing in the contract.

**Output contract (→ Stage 2):** `models.ReconciledValue` — value, confidence tier (`exact`/`aggregated`/`estimated`/`triangulated`/`declared_unresolved`), source provenance, imputation flag + method, uncertainty width, provisional flag + resolution date, version/restatement lineage. Matches design report §7 field-for-field.

**Consumes cross-cutting services:** KPI Semantic Contract, Calendar Dimension. Identity Resolution Graph is implemented directly in `identity_resolution.py` for this slice (not yet split into its own standalone `pipeline/cross_cutting/` module).

**Run:**
```bash
cd pipeline/stage01_reconciliation_ingestion
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_reconcile.py            # must print OK
.venv/bin/python reconcile.py --episode-id 1 --day-offset 10 --kpi revenue
```
