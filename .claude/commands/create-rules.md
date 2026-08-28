# Create Rules: Generate or Refresh CONSTITUTION.md

Regenerate `CONSTITUTION.md` from actual codebase evidence — no guessing, no stale carry-forward.

## Steps

1. Inventory: `find pipeline -maxdepth 2 -type f`, check for a root `pyproject.toml`/`requirements.txt` (there isn't one yet — each pipeline module has its own).
2. Detect the current stack: is FastAPI actually a dependency yet, or still planned? Is a linter/type-checker in use? Has pytest replaced the plain `assert`-script pattern?
3. Read representative source: one implemented module's `generate.py`/`views.sql` equivalent, one `test_*.py`.
4. Read `.github/workflows/*` (if it exists by then) for the real CI command sequence.
5. Update `CONSTITUTION.md`'s Tech Stack table, Commands section, and Validation Gate to match reality — mark anything genuinely unclear `UNKNOWN — needs human input`, never leave a stale placeholder.
6. Output: what changed, with the evidence file for each change, and what's still unknown.
