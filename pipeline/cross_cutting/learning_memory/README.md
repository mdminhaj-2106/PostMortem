# Cross-Cutting Service — Learning & Memory

**Job:** stores past investigations, retrieves similar past fingerprints into Stages 5/7, and absorbs analyst corrections/overrides back into training data. Replaces the old Round 1 "Memory agent," split cleanly into retrieval-in and correction-in.

**Status:** Named in the locked topology; not yet designed as its own standalone service, though several stages already specify how they use it. No dedicated design report exists yet.

**Already used by Stage 1** (correction-in side): Scenarios 2 and 7 both write one-time human-in-loop resolutions into the Semantic Contract via this service — the mechanism that satisfies graded requirement #7, "mechanism to learn from analyst and business-user feedback." See [`docs/02-stage-design-reports/stage1-reconciliation-design.md`](../../../docs/02-stage-design-reports/stage1-reconciliation-design.md) Scenarios 2 and 7.

**Referenced for retrieval-in side:** the original architecture's Memory Agent (Component D, [`docs/01-architecture/architecture-report.md`](../../../docs/01-architecture/architecture-report.md) §6) queries prior investigations with similar fingerprints; Stage 5c's cold-start handler is expected to use the same retrieval pattern.

No code yet.
