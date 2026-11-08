"""Re-exports Stage 11's narrate_incident. Same sys.path + sys.modules-eviction
pattern as stage04's stage3_bridge.py (pipeline/stage11_narration instead of
pipeline/stage03_cross_kpi_correlation)."""

import importlib
import os
import sys

_STAGE11_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage11_narration")
)
_STAGE11_MODULE_NAMES = ("narrate", "stage3_bridge", "priority")


def _import_narrate():
    for name in _STAGE11_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE11_DIR)
    try:
        return importlib.import_module("narrate")
    finally:
        sys.path.remove(_STAGE11_DIR)
        for name in _STAGE11_MODULE_NAMES:
            sys.modules.pop(name, None)


_narrate = _import_narrate()
narrate_incident = _narrate.narrate_incident
