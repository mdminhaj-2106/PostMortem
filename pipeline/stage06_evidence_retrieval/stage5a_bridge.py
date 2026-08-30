"""Re-exports Stage 5a's real run_stage5a_and_5c + Stage 5c's reference loader, so
Stage 6 can re-derive a real FingerprintResult for the same cluster it decomposed
via stage4_bridge.py, exactly the way stage5a.py's own CLI does. load_reference is
re-exported too since run_stage5a_and_5c requires it as an argument.

Same sys.path + sys.modules-eviction pattern as Stage 5a's own stage4_bridge.py /
stage5c_bridge.py, one dir over -- with one wrinkle: run_stage5a_and_5c does its own
lazy `import stage5c_bridge` *inside* its function body (stage5a.py's own
lazy-bridge-loading choice), which runs at call time, long after this module's
sys.path insert has been removed. A plain `import` checks sys.modules before
touching sys.path at all, so "stage5c_bridge" is deliberately left OUT of the
post-import eviction (unlike every other name here) so that later call finds it
already cached instead of failing a real path lookup.
"""

import importlib
import os
import sys

_STAGE5A_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage05a_fingerprint_classification")
)
_STAGE5A_MODULE_NAMES = (
    "models", "onset_fetcher", "signatures", "classifier",
    "stage3_bridge", "stage4_bridge", "stage5c_bridge", "stage5a",
)
_KEEP_CACHED = {"stage5c_bridge"}


def _import_stage5a():
    for name in _STAGE5A_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE5A_DIR)
    try:
        stage5a_module = importlib.import_module("stage5a")
        stage5c_bridge = importlib.import_module("stage5c_bridge")
    finally:
        sys.path.remove(_STAGE5A_DIR)
        for name in _STAGE5A_MODULE_NAMES:
            if name not in _KEEP_CACHED:
                sys.modules.pop(name, None)
    return stage5a_module, stage5c_bridge


_stage5a, _stage5c_bridge = _import_stage5a()
run_stage5a_and_5c = _stage5a.run_stage5a_and_5c
load_reference = _stage5c_bridge.load_reference
