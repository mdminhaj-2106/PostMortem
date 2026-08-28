# Stage 5b — Confounded-Cause Decomposer

**Job:** branches off Stage 5a when fingerprint signature confidence is split between causes — not a fallback, a real fork. When the fingerprint doesn't cleanly point to one cause, attribute contribution across the overlapping causes instead of forcing a top-1 pick.

**Status:** Not yet designed. No stage design report exists yet.

**Why this matters more than it looks:** per the Round 2 topology and differentiation strategy ([`docs/00-brief-and-topology/round2-topology-and-brief.md`](../../docs/00-brief-and-topology/round2-topology-and-brief.md) §3), this is explicitly called out as **the sharpest differentiator** in the whole system — no commercial RCA/BI-diagnostic product surveyed (Datadog Watchdog, Dynatrace Davis AI, Sherlocks.ai, NeuBird, Tellius, Statspresso) explicitly decomposes two overlapping/confounded causes, and a one-week hackathon team will typically skip this too. It's named as a real, visible pipeline component on purpose — not a footnote inside 5a.

**Related design precedent to reuse, not reinvent:** Stage 3's §6 "Multi-Path Combination Rule" (shared-node vs. disjoint-path handling for combining multiple KPI contributions) is explicitly noted as "the same underlying spirit as Stage 5b's confounded-cause decomposer, just applied to ranking instead of diagnosis" — read that section before designing this stage; the joint-vs-disjoint distinction likely transfers directly.

No code yet, no design report yet. This should be prioritized alongside 5a rather than deferred.
