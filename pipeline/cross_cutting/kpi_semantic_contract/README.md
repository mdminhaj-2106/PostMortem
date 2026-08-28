# Cross-Cutting Service — KPI Semantic Contract

**Job:** definitions, thresholds, lineage rules, hierarchy — declared once at design time, not inferred live. Consulted by Stages 1, 2, 4, 5.

**Status:** Introduced and specified in detail by the Stage 1 design report — not yet its own standalone design report, since it's fully specified as part of Stage 1.

**Specification:** [`docs/02-stage-design-reports/stage1-reconciliation-design.md`](../../../docs/02-stage-design-reports/stage1-reconciliation-design.md) §3.1 — per-source declared metadata: grain, cadence, reporting lag, plain-language definition, known bias direction, calendar convention, classification rules/thresholds (e.g. the Enterprise revenue cutoff). Modeled on how real data-governance tools (Collibra, Alation) maintain trust/definition metadata per source.

**Also specifies:** Stage 4's dimension taxonomy (region/segment/product canonical values + per-source column mapping) is described as living inside this contract — see [`docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md`](../../../docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md) §2.2.

No code yet.
