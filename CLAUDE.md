# CLAUDE.md — Claude Code Session Bootstrap

## Start Every Session By Reading

1. `CONSTITUTION.md` — tech stack, architecture, code rules, git workflow, non-negotiables
2. `.claude/reference/architecture.md` — pipeline stage map + what's actually built vs designed-only
3. `.claude/reference/database.md` — the live Neon Postgres schema (Layer 1 + Layer 2)
4. `.claude/reference/testing.md` — how this project tests things (no pytest, plain assert scripts)
5. Active plans in `.claude/plans/*.md` — currently: `stage1-reconciliation-ingestion.md`

Then run:
```bash
git status --short
git branch --show-current
gh pr list
```

**If picking up mid-project:** the docs under `docs/` are the deeper design history (per-stage design reports, the original architecture report, the Round 2 brief). `.claude/reference/` is the current-state summary; `docs/` is the *why*. Read `.claude/reference/` first, fall back to `docs/` for rationale on any specific decision.

## Quick Commands

```bash
# Per pipeline module (e.g. pipeline/simulator/layer1_ground_truth/):
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python test_<name>.py     # must print OK

# Apply a module's SQL:
psql "$DATABASE_URL" -f schema.sql
```

No app is running yet (FastAPI backend not started) — nothing to `dev`/`build` yet.

## Pre-Commit Checklist

- [ ] Every touched module's `test_*.py` prints OK
- [ ] No secrets committed (`.env` is gitignored — check `git status` before staging)
- [ ] Scope matches the plan/issue — nothing more
- [ ] `.claude/reference/` updated if a DB schema or (future) API contract changed
- [ ] On a `feature/*` branch, PR targets `develop`, never committing straight to `main` or `develop`

## Agent Rules (Summary)

Full rules in `CONSTITUTION.md`. Key non-negotiables:
- The LLM never decides significance, cause, or ranking — narration (Stage 11) only.
- `injected_events` (Layer 1's ground-truth labels) is held out — never fed to the pipeline, only used for offline scoring.
- `main` gets working code only, promoted deliberately — never docs/scaffolding, never a direct commit.
- Batch DB inserts with a real `page_size` — the default (100) silently produces dozens of unnecessary network round trips against a remote Postgres host.
- New real-world-data claims get verified against the actual data before being asserted (this project caught and fixed several bugs — VIP-segment skew, reliability exceeding 1.0, an inconsistent active-customer definition — precisely by querying live output instead of trusting the code's intent).
