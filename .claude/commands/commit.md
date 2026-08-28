# Commit: Package Changes for Review

Atomic, reviewable commit + PR, following the branch-per-feature workflow established throughout this project.

## Process

1. `git status --short`, `git diff --stat`, `git diff` — inspect before staging anything.
2. Confirm scope: only files related to this change. Exclude `.env`, generated artifacts (`.venv/`, `__pycache__/`, `*.db`, `.olist_cache/` — all already in `.gitignore`), and anything from a different unit of work.
3. Run the module's validation gate (`.venv/bin/python test_<name>.py`) — do not skip.
4. Stage specific files by name — never `git add .` or `git add -A` without reviewing `git status` first.
5. Commit message: `<type>: <imperative description>`, body explaining *why* (not what — the diff already shows what). Types used throughout this project: `feat`, `fix`, `perf`, `docs`, `chore`.
6. Push the feature branch, open a PR into `develop` (`gh pr create --base develop --head <branch>`), merge with `gh pr merge --merge --delete-branch`.

## Non-negotiables

- Never commit `.env` or any real connection string/secret.
- Never push directly to `main` or `develop` — always through a `feature/*` branch and PR, even for a one-line fix.
- One logical change per commit — if a fix surfaces a second, unrelated bug mid-verification, that's a separate commit (this has happened repeatedly in this project — e.g. fixing the segment model surfaced a runaway signup-growth bug that got its own fix, not a bundled one).
- `main` never receives design docs or scaffolding — only working code, promoted deliberately.
