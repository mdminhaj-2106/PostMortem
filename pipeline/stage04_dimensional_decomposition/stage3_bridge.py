"""Re-exports Stage 3's real run_stage3, so stage4.py's CLI can re-derive a real
StageThreeResult cluster to decompose instead of requiring a hand-built fixture --
same reasoning stage3.py's own CLI already used for re-deriving its input from Stage 2.

Same sys.path + sys.modules-eviction pattern as stage2_bridge.py, one dir over
(pipeline/stage03_cross_kpi_correlation instead of stage02_significance_detection).
Stage 3's own models.py/stage2_bridge.py would otherwise collide with Stage 4's
same-named files in Python's flat sys.modules namespace.
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
