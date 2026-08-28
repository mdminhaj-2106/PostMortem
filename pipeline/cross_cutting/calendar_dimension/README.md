# Cross-Cutting Service — Calendar Dimension

**Job:** a single shared reference table that buckets any raw, atomic-grain timestamp into any calendar convention in play (Gregorian week, fiscal week, billing-cycle month, UTC day, local-timezone day).

**Status:** Introduced and specified in detail by the Stage 1 design report — not yet its own standalone design report.

**Specification:** [`docs/02-stage-design-reports/stage1-reconciliation-design.md`](../../../docs/02-stage-design-reports/stage1-reconciliation-design.md) §3.2 and Scenario 5 (Calendar Misalignment). Because Layer 1 of the simulator is atomic-grain and owned by the team, re-bucketing on demand from raw truth is exact — this is why the design deliberately rejects materializing every calendar-convention variant separately.

No code yet.
