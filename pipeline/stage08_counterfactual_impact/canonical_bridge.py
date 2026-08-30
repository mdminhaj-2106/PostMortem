"""Re-exports Stage 2's real load_kpi_timeline/compute_residuals/assess_eligibility
-- the actual "baseline machinery" design doc §18 says Stage 8 must reuse, never
redefine. Same sys.path + sys.modules-eviction pattern as every other cross-stage
bridge in this repo.

`ingest.py` bridges to Stage 1 internally (for `reconcile.py`) and cleans up
after itself -- but only in its own `finally`, never pre-emptively. Every stage
in this repo has its own `models.py`, so if this process already imported
Stage 8's own `models` (e.g. via `output_schema.py`'s `from models import ...`)
before this bridge runs, `sys.modules["models"]` is already cached under the
wrong file, and Stage 1's `reconcile.py`'s own `from models import ReconciledValue`
silently resolves to Stage 8's models instead of Stage 1's -- caught live as
`ImportError: cannot import name 'ReconciledValue' from 'models'`. `"models"` is
therefore evicted here too, defensively, even though it isn't one of Stage 2's
own three module names -- it's the transitively-reached name that actually
collides.
"""

import importlib
import os
import sys

_STAGE2_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage02_significance_detection")
)
_STAGE2_MODULE_NAMES = ("ingest", "baseline", "eligibility", "models")


def _import_stage2():
    for name in _STAGE2_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE2_DIR)
    try:
        ingest = importlib.import_module("ingest")
        baseline = importlib.import_module("baseline")
        eligibility = importlib.import_module("eligibility")
    finally:
        sys.path.remove(_STAGE2_DIR)
        for name in _STAGE2_MODULE_NAMES:
            sys.modules.pop(name, None)
    return ingest, baseline, eligibility


_ingest, _baseline, _eligibility = _import_stage2()

load_kpi_timeline = _ingest.load_kpi_timeline
KPI_NAMES = _ingest.KPI_NAMES
compute_residuals = _baseline.compute_residuals
assess_eligibility = _eligibility.assess_eligibility
ELIGIBLE = _eligibility.ELIGIBLE
LIMITED_HISTORY = _eligibility.LIMITED_HISTORY
LOW_CONFIDENCE = _eligibility.LOW_CONFIDENCE
INSUFFICIENT_DATA = _eligibility.INSUFFICIENT_DATA
