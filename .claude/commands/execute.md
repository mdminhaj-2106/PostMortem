# Execute: Implement a Prepared Plan

Implement a plan from `.claude/plans/` faithfully, scoped and tested.

## Before starting

Read the plan in full, read `CONSTITUTION.md` (architecture + validation gate), read every file listed under "Files to Read First," run `git status` to see and preserve any unrelated changes already present.

## Process

1. Create (or confirm you're on) the plan's designated `feature/*` branch off `develop`.
2. Implement steps in order. Re-read a file immediately before editing it if it's been more than a few turns since you last saw it.
3. Run each step's own validation as you go — don't batch validation to the end.
4. Add/update the module's `test_*.py` for any behavior change (see existing examples: `pipeline/simulator/layer1_ground_truth/test_generate.py`, `.../layer2_observed_sources/test_views.py` — plain asserts, `if __name__ == "__main__"`, prints `OK`).
5. Update `.claude/reference/database.md` (or `api.md` once it exists) if this step changes a schema or contract.

## Editing rules

Narrow edits only — no drive-by refactors. No new dependency without a CONSTITUTION.md check. Business logic stays out of route handlers (once FastAPI exists). Match the file's existing conventions (see `generate.py`'s style: flat functions, no classes unless genuinely needed for state).

## Validation gate

```bash
.venv/bin/python test_<name>.py    # must print OK
```
(No lint/typecheck/build yet — add here the moment one exists, per `CONSTITUTION.md`.)

If the change touches a live Neon table: verify against the actual database, not just the offline test — this project has repeatedly caught real bugs only visible in live data (VIP-segment skew, reliability exceeding 1.0, a definitional inconsistency between two views) that a pure code read missed.

## Completion report

Files changed, behavior implemented, tests run (and their output), anything skipped and why, open gaps, PR status.
