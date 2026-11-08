"""Re-exports Stage 2's real compute_residuals/score_unusualness directly -- same
sys.path + sys.modules-eviction pattern as Stage 4/5a's own stage2_bridge.py /
onset_fetcher.py, one level further (a seventh stage now needing this; architecture.md's
Known Risks already called a real package overdue at the fourth).
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
        stage2_baseline = importlib.import_module("baseline")
        stage2_unusualness = importlib.import_module("unusualness")
    finally:
        sys.path.remove(_STAGE2_DIR)
        for name in _STAGE2_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage2_baseline, stage2_unusualness


_stage2_baseline, _stage2_unusualness = _import_stage2()

compute_residuals = _stage2_baseline.compute_residuals
score_unusualness = _stage2_unusualness.score_unusualness
