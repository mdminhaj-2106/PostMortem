# Stage 5c — Cold-Start / Analogy Handler

**Job:** branches off Stage 4 when history is thin, runs instead of or alongside Stage 5a. For a KPI/product/segment with little history, borrow a fingerprint from the nearest analogous case and explicitly label the confidence as "borrowed," not native.

**Status:** Not yet designed. No stage design report exists yet.

**Trigger condition (already specified by Stage 4):** a decomposition slice with `eligibility: LIMITED_HISTORY` and `unusualness_percentile: null` (see [`docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md`](../../docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md) §5) is Stage 4's explicit signal to route here instead of trusting a fabricated percentile.

**Consumes:** the Learning & Memory cross-cutting service, for retrieving the "nearest analogous case" to borrow a fingerprint from — same retrieval pattern the Memory Agent uses in Stage 7's hypothesis debate (per the original architecture report §6).

No code yet, no design report yet.
