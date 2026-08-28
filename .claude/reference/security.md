# Security Reference

## Current state

Nothing security-sensitive is built yet — the codebase so far is entirely the synthetic simulator (Layer 1 + Layer 2), which contains no real customer data and no auth surface. This doc is a placeholder for what's coming, not a description of a hardened system.

## Auth model

UNKNOWN — needs a decision alongside the Security & Access Filter cross-cutting service (not yet designed — see `docs/00-brief-and-topology/round2-topology-and-brief.md` §4). This service is explicitly meant to gate row/column/domain-level access on Stage 10's output before narration reaches anyone, and Decision Rights (a separate, deliberately-not-merged concept) governs who's authorized to *act* on a recommendation, not just see it.

## Sensitive data inventory

None currently. `.env` holds one secret (`DATABASE_URL`), gitignored. Revisit this whole file once real data or user auth enters the picture — don't assume "none" stays true.

## Secrets management

- `.env` gitignored, `.env.example` shape-only.
- No secrets are ever printed to logs/stdout in the existing generator scripts (verified — `generate.py`/`inject_outages.py` never echo `DATABASE_URL`).

## Graded requirement this maps to

Objective #8 in the brief: "operate within security, cost, latency, and scalability constraints." Not yet addressed beyond basic secret hygiene — this is real, undone work, not a completed section.
