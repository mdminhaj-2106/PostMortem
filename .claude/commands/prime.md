# Prime: Load Project Context

Start-of-session context loading for PS3 — BusinessIntelligence.ai.

## Steps

1. Repo state:
   ```bash
   git status --short
   git branch --show-current
   git log -n 8 --oneline
   git remote -v
   ```
2. Read durable context in priority order: `CONSTITUTION.md`, `PRD.md`, then everything in `.claude/reference/`.
3. Inspect repo shape: `find . -maxdepth 3 -type f -not -path '*/.git*' -not -path '*/.venv*' -not -path '*/__pycache__*'`.
4. Read active plans: `ls .claude/plans/` and read whichever is in progress.
5. Check GitHub context if `gh` is available: `gh pr list`, `gh issue list --limit 10`.
6. Note which pipeline stages are implemented vs designed-only (see `.claude/reference/architecture.md`'s status table) — don't assume a stage exists just because it has a design doc.

## Output

A concise context brief: current branch, project phase, what's implemented vs designed, dirty files, active plan, validation gate, known blockers (e.g. Stage 1 blocked on nothing currently; Stage 4 blocked on confirming Stage 2's function interface).
