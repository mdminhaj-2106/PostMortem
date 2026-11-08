"""Re-exports Stage 3's direction() (F1 -- DROP/SPIKE from a signed priority_score).
Same sys.path + sys.modules-eviction pattern as stage04's stage3_bridge.py, one dir
over (pipeline/stage03_cross_kpi_correlation instead of stage04_dimensional_decomposition).
"""

import importlib
import os
import sys

_STAGE3_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage03_cross_kpi_correlation")
)


def _import_priority():
    sys.modules.pop("priority", None)
    sys.path.insert(0, _STAGE3_DIR)
    try:
        return importlib.import_module("priority")
    finally:
        sys.path.remove(_STAGE3_DIR)
        sys.modules.pop("priority", None)


_priority = _import_priority()
direction = _priority.direction
