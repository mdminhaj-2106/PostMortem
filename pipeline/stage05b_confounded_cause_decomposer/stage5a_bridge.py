"""Re-exports Stage 5a's real run_stage5a, so stage5b.py's CLI can re-derive a real
FingerprintResult instead of a hand-built fixture -- same pattern as every other
cross-stage bridge in this repo, one level deeper again.
"""

import importlib
import os
import sys

_STAGE5A_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage05a_fingerprint_classification")
)
_STAGE5A_MODULE_NAMES = (
    "models", "signatures", "classifier", "onset_fetcher",
    "stage3_bridge", "stage4_bridge", "stage5a",
)


def _import_stage5a():
    for name in _STAGE5A_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE5A_DIR)
    try:
        return importlib.import_module("stage5a")
    finally:
        sys.path.remove(_STAGE5A_DIR)
        for name in _STAGE5A_MODULE_NAMES:
            sys.modules.pop(name, None)


_stage5a = _import_stage5a()
run_stage5a = _stage5a.run_stage5a
