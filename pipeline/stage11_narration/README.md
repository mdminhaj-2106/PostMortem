# Stage 11 — Narration (LLM-only)

**Job:** turn the final structured object into prose. Nothing upstream of this stage is allowed to touch narrative language.

**Status:** Not yet designed. No stage design report exists yet.

**Founding principle (applies across the whole pipeline, not just this stage):** "the LLM is never the source of quantitative truth." The LLM only runs after every number, hypothesis rank, and confidence label already exists — its job is to turn a structured object into prose, not to decide what's true. See [`docs/01-architecture/architecture-report.md`](../../docs/01-architecture/architecture-report.md) §1 and [`docs/00-brief-and-topology/round2-topology-and-brief.md`](../../docs/00-brief-and-topology/round2-topology-and-brief.md) §2 — this is now a graded Round 2 rubric item, not just a design preference, and needs to be a visible, inspectable breakdown in the running prototype (e.g. an LLM-vs-non-LLM cost/call breakdown per the minimum prototype checklist), not a claim in a report.

**Cost-sensitivity:** wrapped by the Telemetry & Cost Governor cross-cutting service, which can route cheap-heuristic vs. expensive-model-call decisions for this stage (and Stage 6).

No code yet, no design report yet.
