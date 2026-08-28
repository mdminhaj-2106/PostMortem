# Testing Reference

## Quality gate (current)

No pytest, no CI yet. Every module that has non-trivial logic ships a `test_<name>.py` — plain `assert` statements, an `if __name__ == "__main__":` block, prints `OK` on success. Run directly:

```bash
.venv/bin/python test_generate.py   # pipeline/simulator/layer1_ground_truth/
.venv/bin/python test_views.py      # pipeline/simulator/layer2_observed_sources/
```

This is a deliberate choice (see `CONSTITUTION.md`), not a gap — matches the project's low-ceremony style. Revisit if the test surface grows past what a handful of asserts can cover, or once a real CI pipeline exists.

## Test layers

| Layer | What it covers | Example |
|---|---|---|
| Offline invariant checks | Generation logic, no DB needed | `test_generate.py`: effect-curve shapes, order/customer index bounds, `[0,1]` bounds on reliability/satisfaction, segment domain, event trigger-index ordering |
| Live-DB smoke checks | Whether the *actual data* in Neon has the properties it's supposed to | `test_views.py`: total-gap suppression, drift-boundary ratio, entity-mismatch presence, grain differences |
| Manual live verification | Real bugs live here — code that "should" work but doesn't when you look at real output | Every real bug this project has found (VIP-segment skew, reliability >1.0, billing's active-customer definition) was caught by querying live Neon data directly, not by reading the code |

**The pattern to keep:** every non-trivial change gets both an offline check (fast, catches structural bugs) *and* a live-data spot-check (catches calibration/realism bugs the offline check can't see, since it doesn't know what "realistic" looks like). Neither alone has been sufficient so far.

## File conventions

- `test_<module_name>.py` sits next to the module it tests, not in a separate `tests/` tree.
- No fixtures/mocks framework — tests call the real generation functions directly with a fixed seed, or query the real (or a throwaway) database.
- A regression guard gets added to the relevant `test_*.py` the moment a real bug is found and fixed — e.g. `test_generate.py`'s `assert all(0.0 <= row[6] <= 1.0 ...)` exists specifically because `product_reliability` was once observed hitting 1.06 in live data.

## What must have a test

Any function with a branch, a loop, a threshold, or anything touching a causal claim or money. The event effect-curve model, the segment-tier computation, any Layer 2 view doing non-trivial aggregation.

## What doesn't need one

Simple pass-through queries, one-line CLI argument wiring, anything where the SQL itself is the entire logic and a syntax error would be immediately obvious on apply.

## Critical journeys (fill in as later stages get built)

| Journey | Status |
|---|---|
| Generate episodes → verify KPIs queryable and realistic | ✅ covered (`test_generate.py` + manual live verification) |
| Layer 2 views reproduce all 6 implemented reconciliation scenarios | ✅ covered (`test_views.py`) |
| Stage 1 reconciles a Layer 2 conflict into a confidence-tagged canonical value | Not yet — add once Stage 1 exists |
| End-to-end: episode → Stage 1–11 → narrated recommendation, scored against `injected_events` | Not yet — the eventual offline eval loop (architecture report §9) |
