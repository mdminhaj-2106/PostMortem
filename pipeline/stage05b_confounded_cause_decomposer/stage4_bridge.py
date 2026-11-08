"""Re-exports Stage 4's real slice_fetcher (load_slice_timeline, distinct_slice_values)
and its stage2_bridge (compute_residuals, assess_eligibility) directly -- no forked
logic, same sys.path + sys.modules-eviction pattern as Stages 3/4/5a's own bridges,
one level deeper again.
"""

import importlib
import os
import sys

_STAGE4_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage04_dimensional_decomposition")
)
_STAGE4_MODULE_NAMES = (
    "models", "dimension_config", "slice_fetcher", "stage2_bridge",
    "decomposer", "output_schema", "stage3_bridge", "stage4",
)


def _import_stage4():
    for name in _STAGE4_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE4_DIR)
    try:
        slice_fetcher = importlib.import_module("slice_fetcher")
        stage2_bridge = importlib.import_module("stage2_bridge")
        dimension_config = importlib.import_module("dimension_config")
    finally:
        sys.path.remove(_STAGE4_DIR)
        for name in _STAGE4_MODULE_NAMES:
            sys.modules.pop(name, None)
    return slice_fetcher, stage2_bridge, dimension_config


_slice_fetcher, _stage2_bridge, _dimension_config = _import_stage4()

load_slice_timeline = _slice_fetcher.load_slice_timeline
distinct_slice_values = _slice_fetcher.distinct_slice_values
compute_residuals = _stage2_bridge.compute_residuals
assess_eligibility = _stage2_bridge.assess_eligibility
applicable_dimensions = _dimension_config.applicable_dimensions
LIMITED_HISTORY = _stage2_bridge.LIMITED_HISTORY
INSUFFICIENT_DATA = _stage2_bridge.INSUFFICIENT_DATA
