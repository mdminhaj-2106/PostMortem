"""Runtime telemetry + LLM cost ledger (audit finding F16; brief checklist items
"runtime telemetry" and "LLM-vs-non-LLM cost/call breakdown").

Measured from the CALLER, not by instrumenting each stage. The demo already invokes
every stage in sequence at a clear boundary, so wrapping those calls gives the same
per-stage wall time and call counts without threading a shared telemetry import
through four stage packages -- each of which would need another sys.path/sys.modules
hack (see stage02/ingest.py's docstring for why that pattern is already the repo's
sharpest edge). Nothing in pipeline/ imports this module.

The headline number this exists to make measurable: 0 LLM calls in Stages 1-4. That
is an architectural guarantee (CONSTITUTION.md non-negotiable #4 -- Stage 11 is the
only place an LLM is permitted), and this ledger is what turns it from a claim into
a printed row.

Token pricing is passed IN by the caller rather than hardcoded here: Stage 11 does
not exist yet, and a stale rate table baked into a file nobody re-reads is exactly
the two-sources-of-truth bug F8/F9 already cost this project once. Stage 11 should
supply current rates from the `claude-api` skill at the point of the call.

Stdlib only, no dependencies.
"""

import time
from contextlib import contextmanager

_records = []


@contextmanager
def stage(name, uses_llm=False):
    """Times a stage. Yields its record dict so the caller can attach LLM usage.

    uses_llm is the DECLARED expectation; llm_calls is what was actually observed.
    print_summary flags any disagreement -- an unexpected call in Stages 1-4 is a
    non-negotiable violation and must fail loudly rather than blend into a table.
    """
    record = {
        "stage": name, "uses_llm": uses_llm, "seconds": 0.0,
        "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
    }
    _records.append(record)
    started = time.perf_counter()
    try:
        yield record
    finally:
        record["seconds"] = time.perf_counter() - started


def record_llm_call(record, input_tokens, output_tokens, usd_per_mtok_in, usd_per_mtok_out):
    """Accumulate one LLM call into a stage record. Rates are per million tokens."""
    record["llm_calls"] += 1
    record["input_tokens"] += input_tokens
    record["output_tokens"] += output_tokens
    record["cost_usd"] += (
        input_tokens * usd_per_mtok_in + output_tokens * usd_per_mtok_out
    ) / 1_000_000


def reset():
    _records.clear()


def print_summary():
    if not _records:
        print("no stages recorded")
        return

    print(f"{'stage':<34} {'seconds':>9} {'LLM calls':>10} {'in tok':>9} {'out tok':>9} {'cost USD':>10}")
    print("-" * 84)
    for r in _records:
        print(f"{r['stage']:<34} {r['seconds']:>9.2f} {r['llm_calls']:>10} "
              f"{r['input_tokens']:>9} {r['output_tokens']:>9} {r['cost_usd']:>10.4f}")

    total_seconds = sum(r["seconds"] for r in _records)
    total_calls = sum(r["llm_calls"] for r in _records)
    total_cost = sum(r["cost_usd"] for r in _records)
    print("-" * 84)
    print(f"{'TOTAL':<34} {total_seconds:>9.2f} {total_calls:>10} "
          f"{sum(r['input_tokens'] for r in _records):>9} "
          f"{sum(r['output_tokens'] for r in _records):>9} {total_cost:>10.4f}")

    deterministic = [r for r in _records if not r["uses_llm"]]
    print(f"\nDeterministic stages: {len(deterministic)}/{len(_records)}  "
          f"({', '.join(r['stage'] for r in deterministic)})")
    print(f"LLM calls in those stages: {sum(r['llm_calls'] for r in deterministic)}  "
          f"<- architectural guarantee, not a tuning result")

    violations = [r["stage"] for r in deterministic if r["llm_calls"]]
    if violations:
        print(f"\n*** VIOLATION: LLM call recorded in a non-LLM stage: {violations} ***")


def demo():
    """Self-check: assert-based, no framework (see .claude/reference/testing.md)."""
    reset()
    with stage("fake_deterministic"):
        pass
    with stage("fake_narration", uses_llm=True) as rec:
        record_llm_call(rec, 1000, 500, usd_per_mtok_in=3.0, usd_per_mtok_out=15.0)
        record_llm_call(rec, 1000, 500, usd_per_mtok_in=3.0, usd_per_mtok_out=15.0)

    det, llm = _records
    assert det["llm_calls"] == 0
    assert llm["llm_calls"] == 2
    assert llm["input_tokens"] == 2000 and llm["output_tokens"] == 1000
    # 2000 in @ $3/Mtok = $0.006 ; 1000 out @ $15/Mtok = $0.015
    assert abs(llm["cost_usd"] - 0.021) < 1e-9, llm["cost_usd"]
    assert det["seconds"] >= 0.0
    reset()
    print("OK")


if __name__ == "__main__":
    demo()
