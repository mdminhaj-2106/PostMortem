"""Re-exports Stage 5b's real run_stage5b + router.should_fork, so Stage 7 can
decide whether to invoke 5b at all before asking for its result (most clusters
never fork -- design doc's own §4.2 assumption, plan finding #4). Also re-exports
cause_config.CAUSE_FAMILIES/DEPENDENT_PAIRS and the CauseContribution/
ConfoundedAttributionResult dataclasses, needed by test_stage7.py to assert its
own copies stay equal and to build offline fixtures without duplicating the
dataclasses.

Same sys.path + sys.modules-eviction pattern as every other cross-stage bridge in
this repo (architecture.md's Known architectural risks).
"""

import importlib
import os
import sys

_STAGE5B_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage05b_confounded_cause_decomposer")
)
_STAGE5B_MODULE_NAMES = (
    "models", "cause_config", "attribution", "deviation_matrix",
    "identifiability", "shape_features", "router", "stage5b",
    # deviation_matrix.py imports its own "stage4_bridge" (a different file than
    # this stage's own stage4_bridge.py, same bare name) -- must be evicted too,
    # or it poisons sys.modules for every later plain `import stage4_bridge`
    # elsewhere in the process (caught live: AttributeError, no run_stage3).
    "stage4_bridge",
)


def _import_stage5b():
    for name in _STAGE5B_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE5B_DIR)
    try:
        stage5b_module = importlib.import_module("stage5b")
        router_module = importlib.import_module("router")
        cause_config_module = importlib.import_module("cause_config")
        models_module = importlib.import_module("models")
    finally:
        sys.path.remove(_STAGE5B_DIR)
        for name in _STAGE5B_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage5b_module, router_module, cause_config_module, models_module


_stage5b, _router, cause_config, _stage5b_models = _import_stage5b()
run_stage5b = _stage5b.run_stage5b
should_fork = _router.should_fork
CAUSE_FAMILIES = cause_config.CAUSE_FAMILIES
DEPENDENT_PAIRS = cause_config.DEPENDENT_PAIRS
CauseContribution = _stage5b_models.CauseContribution
ConfoundedAttributionResult = _stage5b_models.ConfoundedAttributionResult
