"""Re-exports Stage 4's real run_stage4, dimension_config, slice_fetcher, models --
same sys.path + sys.modules-eviction pattern as Stage 5a/5b's own stage4_bridge.py.
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
        stage4_module = importlib.import_module("stage4")
        dimension_config = importlib.import_module("dimension_config")
        slice_fetcher = importlib.import_module("slice_fetcher")
        models = importlib.import_module("models")
    finally:
        sys.path.remove(_STAGE4_DIR)
        for name in _STAGE4_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage4_module, dimension_config, slice_fetcher, models


_stage4, dimension_config, slice_fetcher, models = _import_stage4()
run_stage4 = _stage4.run_stage4
