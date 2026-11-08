# Create PRD: Product Requirements Document

Turn product intent into a buildable, sprint-ready `PRD.md`. Use when scope genuinely changes (a new stage gets designed, the brief's requirements shift) — not for routine updates, which just edit `PRD.md` directly.

## Required sections

Executive summary (product/users/problem/MVP success) · principles (3–5 guiding decisions, already established: LLM-narration-only, decline-over-false-confidence, declare-don't-infer, materiality-gated action, ground-in-real-data) · users table (role/goal/pain) · MVP scope (explicit in/out, tied to the brief's actual minimum checklist) · functional requirements with acceptance criteria · system architecture with a Mermaid diagram · API and data contracts (once the FastAPI surface exists) · success metrics (the architecture report §9 metrics: precision/recall, top-1/top-3 accuracy, false-causality rate, counterfactual MAE, calibration) · phased roadmap.

## Rules

- Concrete acceptance criteria over vague descriptions.
- Separate what's MVP from what's roadmap — the brief's own scope guard (§11 of the architecture report) already names several things explicitly out of scope; don't silently expand it.
- Every requirement should be traceable to one of the 8 graded objectives or 10 real-world complexities in `docs/00-brief-and-topology/round2-topology-and-brief.md`.
- Update `.claude/reference/` when the PRD changes a contract (schema, API surface).
