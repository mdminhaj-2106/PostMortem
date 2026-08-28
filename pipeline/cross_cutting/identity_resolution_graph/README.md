# Cross-Cutting Service — Identity Resolution Graph

**Job:** a probabilistic record-linkage service that resolves whether records across sources (CRM customer ID, billing ID, email, support-ticket account name) refer to the same real-world entity. Consulted by Stage 1 (source reconciliation) and Stage 6 (evidence-to-entity linking).

**Status:** Introduced and specified in detail by the Stage 1 design report — the one genuinely new cross-cutting component to come out of Stage 1 design (everything else in Stage 1 reused existing machinery). Not yet its own standalone design report.

**Specification:** [`docs/02-stage-design-reports/stage1-reconciliation-design.md`](../../../docs/02-stage-design-reports/stage1-reconciliation-design.md) §3.3 and Scenario 6 (Entity / Join-Key Mismatch). Uses the Fellegi-Sunter probabilistic record-linkage model (same approach as real MDM tools like Informatica MDM), with field weights derived from rarity (not intuition), two thresholds / three zones (auto-merge / auto-reject / human-in-loop), and an explicit ruling that under-merging is the safer default for this problem statement.

No code yet.
