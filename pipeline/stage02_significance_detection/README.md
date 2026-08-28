# Stage 2 — Per-KPI Significance Detection (Relevance Extraction & Change Classification)

**Job:** for each individual KPI stream, decide Normal / Emerging / Significant / Structural. Runs independently per metric.

**Status:** Design complete.

**Design report:** [`docs/02-stage-design-reports/stage2-relevance-extraction-architecture.md`](../../docs/02-stage-design-reports/stage2-relevance-extraction-architecture.md)

**Covers:** the data-eligibility gate, adaptive expected-behavior baseline, self-normalized unusualness (percentile against the KPI's own historical residuals, not a fixed threshold), business-importance evidence, the KPI relationship graph, relevance resolution, and temporal change classification (EMERGING → SIGNIFICANT → STRUCTURAL).

**Output contract (→ Stage 3, and consumed as a library by Stage 4):** see design report §18 for the full JSON shape (unusualness score+basis, business_importance with evidence, relationship_context/cluster_id, relevance level+tier, classification state+evidence, confidence).

**Critical dependency:** Stage 4's implementation plan expects Stage 2's eligibility-gate / expected-behavior / unusualness-percentile logic to exist as **importable functions** (see Stage 4's design report §4 for the exact expected signatures). Confirm the real function names/signatures early — this is a blocking dependency for Stage 4.

No code yet.
