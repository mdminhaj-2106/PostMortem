# API Reference

**Not yet built.** No FastAPI app exists in this repo yet — the tech-stack decision (Python + FastAPI backend, Next.js frontend) is made, but implementation hasn't started. This doc records the *planned* surface so it isn't re-derived from scratch when the API gets built.

## Planned endpoints (per `docs/01-architecture/architecture-report.md` §8)

| Endpoint | Purpose | Depends on |
|---|---|---|
| `/detect` | Run significance detection across KPIs, return what moved | Stage 2 |
| `/investigate/{kpi_id}` | Full pipeline run for one flagged KPI — decomposition through ranked hypotheses | Stages 3–7 |
| `/counterfactual` | "What would this KPI look like without X" | Stage 8 |
| `/story/{id}` | Persona-narrated recommendation for a completed investigation | Stages 9–11 |

## Global standards (to decide when building)

- Base path: undecided
- Auth: undecided — the brief grades row/column-level security (Security & Access Filter cross-cutting service, not yet designed), so auth design should happen alongside that, not bolted on after
- Response envelope: undecided
- Every response touching a diagnosis should carry the same confidence-tagging discipline Stage 1's output contract establishes (value, confidence tier, provenance, imputation flag, uncertainty width) — don't let the API layer flatten that away

## Contract rules (once this exists)

- Pydantic models for every request/response.
- Update this file the moment a route's shape changes — it's the reference other sessions/teammates read before touching the API.
