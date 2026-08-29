"""Re-exports Stage 3's real run_stage3, so stage5a.py's CLI can re-derive a real
StageThreeResult cluster instead of requiring a hand-built fixture -- same reasoning
stage4.py's own stage3_bridge.py already used.

Same sys.path + sys.modules-eviction pattern, one dir over
(pipeline/stage03_cross_kpi_correlation instead of stage02_significance_detection).
"""

import importlib
import os
import sys

_STAGE3_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage03_cross_kpi_correlation")
)
_STAGE3_MODULE_NAMES = ("models", "dag", "grouping", "priority", "stage2_bridge", "stage3")


def _import_stage3():
    for name in _STAGE3_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE3_DIR)
    try:
        return importlib.import_module("stage3")
    finally:
        sys.path.remove(_STAGE3_DIR)
        for name in _STAGE3_MODULE_NAMES:
            sys.modules.pop(name, None)


_stage3 = _import_stage3()
run_stage3 = _stage3.run_stage3
