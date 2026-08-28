# Stage 9 — Recommendation Assembly

**Job:** turn the quantified diagnosis into the brief's exact structure: driver → lever → action → expected impact → owner → confidence → monitoring plan.

**Status:** Not yet designed. No stage design report exists yet. Flagged in the topology doc as entirely missing from the Round 1 architecture (the "decision rights" governance concept didn't exist yet).

**Consumes:** the Decision Rights cross-cutting service for the `owner` field (who is authorized to *act* on this recommendation — distinct from who can *see* it, which is Security & Access Filter's job at Stage 10).

**Referenced by Stage 1 already:** Scenario 3's provisional-data extension uses this stage's existing recommendation-structure slot to output a soft `monitor — do not act` action with a monitoring plan set to a resolution date.

No code yet, no design report yet.
