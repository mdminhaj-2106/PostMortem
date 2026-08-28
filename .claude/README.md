# AI Workflow Scaffold

This directory contains the AI-agent workflow scaffold for PS3 — BusinessIntelligence.ai.

## Directory Structure

```text
.claude/
  README.md                          — this file
  commands/
    prime.md                         — start-of-session context loading
    create-rules.md                  — generate/refresh CONSTITUTION.md
    create-prd.md                    — refresh PRD.md when scope genuinely changes
    plan-feature.md                  — convert a stage design report to an implementation plan
    execute.md                       — implement a prepared plan
    commit.md                        — package changes for review (branch/PR/merge workflow)
    init-workspace.md                — install this scaffold into another repo
  skills/
    agent-browser/SKILL.md           — browser UI verification (dormant, no frontend yet)
    e2e-test/SKILL.md                — end-to-end journey testing
    debug/SKILL.md                   — systematic debugging, with this project's known bug patterns
  plans/                             — feature/stage implementation plans
    stage1-reconciliation-ingestion.md
  reference/                         — live project technical docs (the "memory index")
    architecture.md                  — system shape + build status (design vs code) per stage
    api.md                           — planned FastAPI surface (not built yet)
    database.md                      — the live Neon schema, Layer 1 + Layer 2
    testing.md                       — how this project actually tests things
    deployment.md                    — Neon + hosting status
    security.md                      — current state (minimal — nothing sensitive built yet)
```

No `templates/` directory — this scaffold was populated with real project content directly rather than left as blank templates, since the project already has enough history to fill every section honestly.

## Daily Workflow

```text
Start session   → /prime
Pick work       → check .claude/plans/ for an active plan, or docs/02-stage-design-reports/ for the next undesigned stage
Plan            → /plan-feature (turns a stage's design report into an implementation plan)
Implement       → /execute
Verify          → module's test_*.py + live-DB spot check if DB-facing (see testing.md)
Debug           → /debug
Commit + PR     → /commit  (branch off develop → PR into develop → merge; main only gets promoted, working code)
```

## Command Reference

| Command | When to use |
|---|---|
| `/prime` | Starting a session or switching context |
| `/create-rules` | Rebuilding CONSTITUTION.md once the stack actually changes (FastAPI added, lint adopted, etc.) |
| `/create-prd` | Scope genuinely changes — not for routine PRD edits |
| `/plan-feature` | Turning a stage's design report into an implementation plan |
| `/execute` | Implementing a prepared plan |
| `/commit` | Packaging changes into a branch → PR → merge |
| `/debug` | Diagnosing a bug systematically |
| `/agent-browser` | Verifying UI — not yet applicable, no frontend |
| `/e2e-test` | Running complete journey tests across simulator/DB/pipeline |
| `/init-workspace` | Installing this scaffold into another repo (e.g. if the frontend splits out) |

## Where things actually live

- **`docs/02-stage-design-reports/`** — the deep design history, one report per stage/layer, in the mechanism → reused-machinery → output-contract format. This is the *why*.
- **`.claude/reference/`** — the current-state summary. This is the *what, right now*. Read this first each session; fall back to `docs/` for rationale.
- **`.claude/plans/`** — turns a design report into concrete, buildable steps.
