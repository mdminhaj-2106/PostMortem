# Plan Feature: Design Doc / Stage → Implementation Plan

Convert a stage's design report (or any feature description) into an executable implementation plan. No code during this step.

## Inputs

A stage number (design report lives in `docs/02-stage-design-reports/`), a GitHub issue (`gh issue view <n>`), or a plain description with acceptance criteria.

## Process

1. Read `CONSTITUTION.md` and the relevant `.claude/reference/*.md` file for the target area (usually `architecture.md` + `database.md`).
2. Read the stage's full design report in `docs/02-stage-design-reports/` — the mechanism, the reused-machinery cross-references, and (critically) the **output contract** section, since that's the exact interface the next stage will assume exists.
3. Investigate the codebase: what's actually implemented that this stage depends on (check `.claude/reference/architecture.md`'s status table before assuming anything exists), existing patterns to match (see `pipeline/simulator/` for the established style), files to read before touching anything.
4. Design: atomic steps, each with what/files/validation; edge cases (empty input, a declined/unresolved result, a materially-insignificant change that shouldn't trigger downstream work); required tests (a runnable `test_*.py` self-check, matching the existing pattern).
5. Write the plan to `.claude/plans/<stage-slug>.md`.

## Plan template

Stage metadata (design report link, priority, branch name) · outcome (testable, not aspirational — "Stage 1 emits a canonical timeline with confidence tags for episode 1's revenue KPI" not "Stage 1 works") · scope (in/out) · files to read first · files to change/create · implementation steps (each with what/files/validation) · tests and validation gate · acceptance criteria checkboxes · risks (schema changes needed upstream, unresolved design questions, performance unknowns).
