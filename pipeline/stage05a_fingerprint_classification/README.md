# Stage 5a — Fingerprint / Cause-Signature Classification

**Job:** read the shape of the Stage 4 decomposition (onset, spread, entropy) and hypothesize the cause family.

**Status:** Not yet designed. No stage design report exists for 5a yet.

**Related prior art:** the original Round 1 architecture's Component B (Fingerprint Root-Cause Classifier — see [`docs/01-architecture/architecture-report.md`](../../docs/01-architecture/architecture-report.md) §4) sketches the feature vector (visits delta, spend-per-visit delta, product/geo entropy, onset shape, duration, day-of-week profile shift, channel mix shift), a multiclass GBM (XGBoost) model with SHAP explanations, and the eval plan (top-1/top-3 accuracy, confusion matrix). Stage 5a should be designed as the Round 2 refinement of that component, now consuming Stage 4's decomposition matrix as its feature source instead of a single-KPI breakdown.

**Forks off this stage:**
- **5b — Confounded-Cause Decomposer**, when fingerprint confidence is split between causes (see that stage's README — this is the sharpest differentiator in the whole pipeline, don't skip designing it).
- **5c — Cold-Start / Analogy Handler**, when a slice has thin history (`unusualness_percentile: null` from Stage 4).

**Consumes:** Stage 4's decomposition matrix; the SCM/DAG (for neighbor-consistency checks, per Stage 1 Scenario 7's precedent).

No code yet, no design report yet.
