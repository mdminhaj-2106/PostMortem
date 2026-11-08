"""Pulls Stage 2's classified results + baseline residuals for a KPI, by importing
Stage 2's real modules directly -- same "reuse machinery, don't fork logic"
discipline Stage 2 established for calling into Stage 1 (plan Risk #3: this stacks
the same sys.path + sys.modules-eviction pattern one level deeper; a real package
is overdue now that a third stage needs it, see architecture.md's Known Risks).

Named stage2_bridge.py, not ingest.py: Stage 2 already has its own ingest.py, and
this module needs to `import_module("ingest")` to reach it -- reusing the same
plain name for *this* file would collide with the very module it's importing.
"""

import importlib
import os
import sys

_STAGE2_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage02_significance_detection")
)
_STAGE2_MODULE_NAMES = (
    "models", "ingest", "baseline", "eligibility", "unusualness",
    "candidate_selection", "business_importance", "relationship_graph",
    "relevance", "classification", "stage2",
)


def _import_stage2():
    for name in _STAGE2_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE2_DIR)
    try:
        stage2 = importlib.import_module("stage2")
        stage2_ingest = importlib.import_module("ingest")
        stage2_baseline = importlib.import_module("baseline")
    finally:
        sys.path.remove(_STAGE2_DIR)
        for name in _STAGE2_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage2, stage2_ingest, stage2_baseline


_stage2, _stage2_ingest, _stage2_baseline = _import_stage2()

KPI_NAMES = _stage2_ingest.KPI_NAMES


def load_stage2_results(cur, episode_id, kpi_name, day_range, other_kpi_candidates=None):
    """Returns Stage 2's real list[StageTwoResult] for one KPI.

    other_kpi_candidates ({day_offset: set(kpi_names)}) is what lets Stage 2's Layer 4/5
    see same-day co-occurrence with ANOTHER KPI. Stage 2's own docstring asked callers to
    thread this through and no caller ever did, so KNOWN_RELATIONSHIP evidence -- and
    therefore Stage 2's whole relationship-graph layer -- was structurally dead: verified
    live at 0 occurrences across 32 days (audit finding F3,
    .claude/plans/remediation-audit-and-fix-plan.md). Stage 3 already runs both KPIs, so
    it is the natural place to feed each one's candidate days into the other."""
    return _stage2.run_stage2(
        cur, episode_id, kpi_name, day_range=day_range,
        other_kpi_candidates=other_kpi_candidates,
    )


def candidate_days_by_day(stage2_results):
    """{day_offset: {kpi_name}} for days this KPI was a real candidate -- the shape
    run_stage2's other_kpi_candidates expects. A day is a candidate exactly when Stage 2
    ran the full Layer 4-7 path on it, which it signals by attaching an importance level."""
    return {
        r.day_offset: {r.kpi_name}
        for r in stage2_results
        if r.business_importance_level != "NONE"
    }


def load_dollar_residuals(cur, episode_id, kpi_name, day_range):
    """Returns [(day_offset, residual_or_None), ...] -- the same rolling-median
    baseline residual Stage 2 uses for unusualness, reused here as the real
    observed dollar delta (design doc §5)."""
    timeline = _stage2_ingest.load_kpi_timeline(cur, episode_id, kpi_name, day_range)
    residuals = _stage2_baseline.compute_residuals(timeline)
    return [(day_offset, residual) for day_offset, _expected, residual in residuals]
