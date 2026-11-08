# Init Workspace: Install the AI Workflow Scaffold

Install this scaffold into another repo (e.g. if the frontend gets split into its own repository later) without touching source code.

## Process

1. Detect target: `pwd`, `git status`, check for an existing `.claude/` or `CLAUDE.md`.
2. Detect project type (language, framework, database, test runner, package manager, CI, hosting) from manifests.
3. Create the directory structure: `.claude/commands/`, `.claude/skills/`, `.claude/plans/`, `.claude/reference/`, `.claude/templates/reference/`, `.github/ISSUE_TEMPLATE/`.
4. Write scaffold files, skipping any that already exist unless overwrite is explicitly requested.
5. Adapt `CLAUDE.md` and `CONSTITUTION.md` to the detected project — do not copy this repo's Python/FastAPI specifics onto a different stack.
6. Report: installed / skipped / needs-human-review / next steps.
