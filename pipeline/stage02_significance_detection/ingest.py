"""Pulls a KPI timeline out of Stage 1, one day at a time -- Stage 2 must not
reinvent reconciliation (design doc §5), only call it.

No root-level Python package exists yet to import across pipeline/stage0N_*/
modules cleanly (architecture.md's Known Risks; plan Risk #1) -- this sys.path
insert is a known, deliberately narrow interim wrinkle, not a new dependency.

Stage 1 and Stage 2 each have their own models.py/materiality.py/etc. Python's
import cache (sys.modules) is a single flat namespace keyed by plain module name,
so a naive `sys.path.insert` + `import reconcile` would permanently shadow Stage
2's own same-named modules for the rest of the process (Stage 1's models.py would
win, and Stage 2's `from models import StageTwoResult` would break). Load Stage
1's module with its directory on sys.path only for the duration of the import,
then evict everything it cached under a colliding plain name.
"""

import importlib
import os
import sys

_STAGE1_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage01_reconciliation_ingestion")
)
_STAGE1_MODULE_NAMES = ("reconcile", "models", "materiality", "calendar_dimension", "semantic_contract")


def _import_stage1_reconcile():
    sys.path.insert(0, _STAGE1_DIR)
    try:
        return importlib.import_module("reconcile")
    finally:
        sys.path.remove(_STAGE1_DIR)
        for name in _STAGE1_MODULE_NAMES:
            sys.modules.pop(name, None)


stage1_reconcile = _import_stage1_reconcile()

KPI_NAMES = ("revenue", "active_customers_purchased_30d")


_reconciled_day_cache = {}  # (episode_id, kpi_name, day_offset) -> ReconciledValue_or_None


def clear_cache():
    """Drop the memoized days. Only needed if Layer 1/2 data changes inside a live
    process (re-applying views.sql, regenerating an episode) -- normal runs never
    need it, and the demo/tests do not call it."""
    _reconciled_day_cache.clear()


def _reconcile_day(cur, episode_id, kpi_name, day_offset):
    if kpi_name == "revenue":
        return stage1_reconcile.reconcile_conflicting_values(cur, episode_id, day_offset)
    rows = stage1_reconcile.reconcile_definitional_active_customers(
        cur, episode_id, day_offset, _start_date(cur, episode_id)
    )
    return next((r for r in rows if r.kpi_name == "active_customers_purchased_30d"), None)


def load_kpi_timeline(cur, episode_id, kpi_name, day_range):
    """Returns [(day_offset, ReconciledValue_or_None), ...] for day_range (an
    iterable of day_offsets). A ReconciledValue with value=None (declared_unresolved)
    is kept, not dropped -- the eligibility gate needs to see the gap. Only truly
    absent rows (active_customers_purchased_30d has no billing row that day) become
    a bare None.

    Memoized per DAY, not per timeline (audit finding F13). Each day costs real Neon
    round trips through Stage 1's reconciliation, and one Stage 3 run re-requests the
    same days five times over: run_stage2 three times (F3's two-pass relationship
    wiring) plus load_dollar_residuals twice. Measured before this cache, Stage 3
    alone was 111s of a 175s demo.

    Keyed per day rather than per (episode, kpi, day_range) so partially-overlapping
    ranges still hit -- test_stage3 asks for a different window per episode, and a
    whole-range key would miss every time.

    `cur` is deliberately not part of the key: this project runs one connection per
    process against one database, and Layer 1 is generated once and frozen while
    Layer 2 is a set of deterministic views over it, so the same (episode, kpi, day)
    is the same value for the life of the process. clear_cache() exists for the one
    case that isn't true. Unbounded by design -- a full 150-episode x 2-KPI x 120-day
    sweep is ~36k small dataclasses, and no run in this repo is long-lived enough for
    eviction to be worth the code.
    """
    if kpi_name not in KPI_NAMES:
        raise ValueError(f"unknown kpi_name: {kpi_name!r}, expected one of {KPI_NAMES}")

    timeline = []
    for day_offset in day_range:
        key = (episode_id, kpi_name, day_offset)
        if key not in _reconciled_day_cache:
            _reconciled_day_cache[key] = _reconcile_day(cur, episode_id, kpi_name, day_offset)
        timeline.append((day_offset, _reconciled_day_cache[key]))
    return timeline


_start_date_cache = {}


def _start_date(cur, episode_id):
    if episode_id not in _start_date_cache:
        _start_date_cache[episode_id] = stage1_reconcile._fetch_episode_start_date(cur, episode_id)
    return _start_date_cache[episode_id]
