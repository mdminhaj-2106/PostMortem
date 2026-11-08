"""Re-exports Stage 4's real run_stage4, so stage5a.py's CLI can re-derive a real
DecompositionResult instead of requiring a hand-built fixture -- same reasoning
stage4.py's own stage3_bridge.py already used, one stage further down the chain.

Same sys.path + sys.modules-eviction pattern, one dir over
(pipeline/stage04_dimensional_decomposition).
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
        return importlib.import_module("stage4")
    finally:
        sys.path.remove(_STAGE4_DIR)
        for name in _STAGE4_MODULE_NAMES:
            sys.modules.pop(name, None)


_stage4 = _import_stage4()
run_stage4 = _stage4.run_stage4
