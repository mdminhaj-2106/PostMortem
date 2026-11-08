"""CLI-only: re-exports Stage 5a's own stage3_bridge.run_stage3 / stage4_bridge.run_stage4
so stage5b.py's CLI can re-derive real Stage 3/4 output, reusing 5a's bridges instead of
writing a third copy (5b's own stage4_bridge.py already exists for a different purpose --
slice_fetcher access for deviation_matrix.py -- so this file is named separately).
"""

import importlib
import os
import sys

_STAGE5A_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage05a_fingerprint_classification")
)
_STAGE5A_MODULE_NAMES = ("models", "stage3_bridge", "stage4_bridge", "stage5a")


def _import():
    for name in _STAGE5A_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE5A_DIR)
    try:
        stage3_bridge = importlib.import_module("stage3_bridge")
        stage4_bridge = importlib.import_module("stage4_bridge")
    finally:
        sys.path.remove(_STAGE5A_DIR)
        for name in _STAGE5A_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage3_bridge, stage4_bridge


_stage3_bridge, _stage4_bridge = _import()
run_stage3 = _stage3_bridge.run_stage3
run_stage4 = _stage4_bridge.run_stage4
