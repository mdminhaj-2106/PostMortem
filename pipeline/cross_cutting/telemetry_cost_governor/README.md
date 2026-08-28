# Cross-Cutting Service — Telemetry & Cost Governor

**Job:** wraps every stage, tracking latency/calls/tokens, and can decide routing (cheap heuristic vs. expensive model call) for cost-sensitive stages like Stage 6 (evidence retrieval) and Stage 11 (narration).

**Status:** Named in the locked topology; not yet designed. No design report exists yet. Flagged in the topology doc's gap-check as entirely missing from the Round 1 architecture (one of the graded requirements — "operate within... cost, latency, and scalability constraints" — that Round 2 adds).

**Minimum prototype checklist requirement this satisfies:** an LLM-vs-non-LLM cost/call breakdown, and runtime telemetry — both explicitly required by the Round 2 brief's minimum prototype checklist. See [`docs/00-brief-and-topology/round2-topology-and-brief.md`](../../../docs/00-brief-and-topology/round2-topology-and-brief.md) §1.

No code yet.
