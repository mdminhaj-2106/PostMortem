"""Re-exports Stage 2's real Layer 1/2/3 functions -- eligibility.assess_eligibility,
baseline.compute_residuals, unusualness.score_unusualness -- directly, not wrapped:
their real (list-based) signatures already match what slice_fetcher.load_slice_timeline
produces, so no adapter shim is needed beyond this import bridge itself (the design
doc's anticipated "adapter layer" turns out to be exactly this module, one level deeper
than Stage 3's own stage2_bridge.py -- see architecture.md's Known Risks on why a real
package is overdue now that a fourth stage needs this sys.path + sys.modules-eviction
pattern; same self-name-collision rationale as Stage 3's bridge for not calling this
ingest.py -- Stage 2 already has its own ingest.py).
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
        stage2_eligibility = importlib.import_module("eligibility")
        stage2_baseline = importlib.import_module("baseline")
        stage2_unusualness = importlib.import_module("unusualness")
    finally:
        sys.path.remove(_STAGE2_DIR)
        for name in _STAGE2_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage2_eligibility, stage2_baseline, stage2_unusualness


_stage2_eligibility, _stage2_baseline, _stage2_unusualness = _import_stage2()

assess_eligibility = _stage2_eligibility.assess_eligibility
compute_residuals = _stage2_baseline.compute_residuals
score_unusualness = _stage2_unusualness.score_unusualness

ELIGIBLE = _stage2_eligibility.ELIGIBLE
LIMITED_HISTORY = _stage2_eligibility.LIMITED_HISTORY
LOW_CONFIDENCE = _stage2_eligibility.LOW_CONFIDENCE
INSUFFICIENT_DATA = _stage2_eligibility.INSUFFICIENT_DATA
