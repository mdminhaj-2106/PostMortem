# Stage 8 — Counterfactual / Consequence Quantification

**Job:** for the top-ranked hypothesis (or each contributing cause from Stage 5b), estimate what the KPI would look like without it — a number and an interval, not a paragraph. What stops recommendations from being delusional.

**Status:** Not yet designed. No stage design report exists yet.

**Related prior art:** the original Round 1 architecture's Component C (Structural Causal Model — see [`docs/01-architecture/architecture-report.md`](../../docs/01-architecture/architecture-report.md) §5) specifies the DAG, per-edge fitted models, and Pearl's abduction–action–prediction counterfactual procedure with bootstrap/residual-resampling uncertainty — including the rule that a weak-fit edge (low R²) must say so explicitly rather than propagate a confident number through a shaky link.

**Referenced by earlier stages already designed:** Stage 1 Scenario 3's provisional-data extension explicitly hands Stage 8 the question "what if this resolves unfavorably"; Stage 3's revenue-equivalent projection is explicitly a cheap first-order proxy that defers real rigor to this stage.

No code yet, no design report yet.
