"""Pulls Stage 2's real (expected, residual) daily series for one KPI, company-wide
(not sliced) -- reuses Stage 2's own ingest.load_kpi_timeline + baseline.compute_residuals
exactly as Stage 3/4 do, via the same sys.path + sys.modules-eviction bridge pattern
(architecture.md's Known Risks; a fourth stage now needs this, real package overdue).

Named onset_fetcher.py, not stage2_bridge.py: this module is used for two of Stage 5a's
three signals (onset_lean AND dominant_kpi_shift both need the same unsliced per-KPI
series), fetch-only -- no signal logic lives here, that's signatures.py's job (pure
functions, no DB access, per the plan).
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
        stage2_ingest = importlib.import_module("ingest")
        stage2_baseline = importlib.import_module("baseline")
    finally:
        sys.path.remove(_STAGE2_DIR)
        for name in _STAGE2_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage2_ingest, stage2_baseline


_stage2_ingest, _stage2_baseline = _import_stage2()

KPI_NAMES = _stage2_ingest.KPI_NAMES


def fetch_residual_series(cur, episode_id, kpi_name, day_range):
    """Returns [(day_offset, expected_or_None, residual_or_None), ...] -- the same
    rolling-median baseline Stage 2/3/4 all reuse, unsliced (company-wide)."""
    timeline = _stage2_ingest.load_kpi_timeline(cur, episode_id, kpi_name, day_range)
    return _stage2_baseline.compute_residuals(timeline)
