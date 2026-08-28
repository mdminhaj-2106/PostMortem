# Stage 1 — Data Reconciliation & Ingestion

**Job:** pull from heterogeneous sources at different grains/cadences and normalize into one canonical event stream. Nothing downstream can trust its inputs until this exists.

**Status:** Design complete, pre-implementation.

**Design report:** [`docs/02-stage-design-reports/stage1-reconciliation-design.md`](../../docs/02-stage-design-reports/stage1-reconciliation-design.md)

**Covers:** the two-layer simulator (Layer 1 ground truth / Layer 2 observed sources), the seven reconciliation scenarios (conflicting values, definitional mismatch, late-arriving history, gaps, calendar misalignment, entity/join-key mismatch, silent definitional drift), and the two new cross-cutting services it introduces (Calendar Dimension, Identity Resolution Graph).

**Output contract (→ Stage 2):** every emitted data point carries value, confidence tier, source provenance, imputation flag, uncertainty width, provisional flag + resolution date where applicable, and version/restatement lineage. See design report §7 for the full contract.

**Consumes cross-cutting services:** KPI Semantic Contract, Calendar Dimension, Identity Resolution Graph.

No code yet — build against the design report's §6 internal pipeline diagram and §7 output contract.
