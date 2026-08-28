# Stage 7 — Hypothesis Debate & Ranking

**Job:** combine 5a/5b/5c output + Stage 6 evidence into a ranked hypothesis list with Known/Likely/Possible/Unknown buckets.

**Status:** Not yet designed. No stage design report exists yet.

**Related prior art:** the original Round 1 architecture's Component D (Multi-Agent Hypothesis Debate — see [`docs/01-architecture/architecture-report.md`](../../docs/01-architecture/architecture-report.md) §6), a direct reuse of the team's existing "Board That Remembers" structure remapped to cause families (Demand / Supply / Competitive / Reliability agents + a Memory agent + a Judge/Synthesizer). The critical constraint carried over: each agent is seeded with the fingerprint classifier's probability + SHAP features + retrieved evidence — never a blank "brainstorm why revenue fell" prompt — so a hallucinated story has nothing to attach to.

**Consumes:** Stage 5a/5b/5c cause hypotheses, Stage 6 evidence, and the Learning & Memory service (prior investigations with similar fingerprints).

No code yet, no design report yet.
