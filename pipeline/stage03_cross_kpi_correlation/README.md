# Stage 3 — Cross-KPI Correlation & Prioritization

**Job:** given several KPIs flagged as moved in the same window by Stage 2, decide whether they're one underlying story told twice or genuine coincidences, and rank which cluster deserves investigation first by business impact.

**Status:** Design complete, pre-implementation.

**Design report:** [`docs/02-stage-design-reports/stage3-cross-kpi-correlation-prioritization.md`](../../docs/02-stage-design-reports/stage3-cross-kpi-correlation-prioritization.md)

**Covers:** grouping via a hand-authored DAG (causation check) + lag/direction-aware correlation (confirmation check), never live causal discovery; prioritization via a revenue-equivalent dollar score (statistical significance used as a gate, business impact as the ranking scale); the shared-node-vs-disjoint-path combination rule for multi-KPI clusters; and why a composite KPI is never handed to Stage 4 (the full untouched cluster is, so each member can still be decomposed dimensionally).

**Hard boundary:** never touches *why* something moved (Stage 5), *where within* a KPI it's concentrated (Stage 4), or evidence (Stage 6).

**Output contract (→ Stage 4):** see design report §8 — full contributing-KPI set (untouched), priority score (revenue-equivalent, observed or projected), Stage 2 confidence tag carried through. No dimensional breakdown, cause hypothesis, or evidence.

No code yet.
