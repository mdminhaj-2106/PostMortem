---
name: debug
description: Systematic debugging workflow for diagnosing errors, unexpected behavior, and data-realism issues in this project's generator, views, and (once built) pipeline stages.
---

## Steps

1. **Reproduce.** Confirm the exact symptom — an exception, or (more common in this project so far) a value that's technically valid but wrong: a distribution that doesn't look real, a metric stuck in an implausible range. Check `git log` for a recent change that could explain it.
2. **Read the evidence.** For an exception: start from the bottom of the traceback. For a realism/distribution bug (the pattern that's caught every real bug in this project so far): **query the live Neon database directly** — `psql "$DATABASE_URL" -c "..."` — don't trust what the code says it should produce. Compare against a real external anchor when one exists (Olist's own stats, an industry benchmark) rather than just "does this look plausible."
3. **Check recent changes:** `git log -n 15 -- <file>`, `git diff HEAD~3 -- <file>`.
4. **Hypothesize** 2–3 concrete, ranked causes before touching code. This project's real bugs so far all had a specific, findable mechanism (a missing upper bound on noise, an unset `page_size` defaulting to 100, a threshold checked in the wrong order) — don't guess-and-check.
5. **Test the hypothesis** with a targeted query or the module's `test_*.py`, not a full regenerate-and-eyeball.
6. **Fix** only what the evidence points to. Re-run the module's test.
7. **Write a regression check** into `test_*.py` if the bug was a realism/bounds issue (e.g. `test_generate.py`'s `assert all(0.0 <= row[6] <= 1.0 ...)` guard, added specifically because `product_reliability` was once observed exceeding 1.0).
8. **Confirm against live data**, not just the offline test, for anything DB-facing — regenerate a small batch (`--n-episodes 3-5`) and query it directly.

## Patterns already found in this project (check these first)

- **Noise with no upper/lower bound** on a variable meant to be a bounded score (`product_reliability` hit 1.06 before being fixed — symmetric noise around a ceiling spends half its mass illegally above it).
- **A definition mismatch between two "comparable" things** (`v_billing_active_customers` once measured "still a customer of record" while claiming to measure "recently active," making its comparison to CRM's definition meaningless).
- **A rate that scales off a quantity it also causes** (organic signup rate scaling off `len(customers)`, which order-driven signups were also growing — a runaway compounding loop unrelated to the actual driver).
- **Silent `execute_values` defaults**: page_size defaults to 100; against a remote Postgres host (Neon) that's dozens of unnecessary round trips per insert.
