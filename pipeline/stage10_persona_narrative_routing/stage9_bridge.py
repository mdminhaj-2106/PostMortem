"""Re-exports Stage 9's own run_stage9 plus its already-built stage3/4/5a/5c/
[5b]/6/7/8 bridge chain transitively (via Stage 9's own stage8_bridge.py), so
Stage 10's live check can replay the full upstream chain without re-deriving
each layer's cross-import plumbing a second time. Same sys.path +
sys.modules-eviction pattern as every other cross-stage bridge in this repo --
the eviction list covers every file actually present in
stage09_recommendation_assembly/ (not just what stage9.py imports at its own
top level -- several of these are only reached transitively through its
submodules, and leaving one off risks the same bare-module-name collision
already hit at the Stage 7/8 layer, see architecture.md's Known
Architectural Risks) plus stage8_bridge itself.
"""

import importlib
import os
import sys

_STAGE9_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage09_recommendation_assembly")
)
_STAGE9_MODULE_NAMES = (
    "models", "config", "mechanism_resolver", "lever_resolver", "action_builder",
    "owner_resolver", "feasibility", "intent_resolver", "monitoring", "success_criteria",
    "selection", "output_schema", "stage9", "stage8_bridge",
)


def _import_stage9():
    for name in _STAGE9_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE9_DIR)
    try:
        stage9_module = importlib.import_module("stage9")
        stage8_bridge = importlib.import_module("stage8_bridge")
    finally:
        sys.path.remove(_STAGE9_DIR)
        for name in _STAGE9_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage9_module, stage8_bridge


_stage9, _stage8_bridge = _import_stage9()

run_stage9 = _stage9.run_stage9
run_stage8 = _stage8_bridge.run_stage8
run_stage7 = _stage8_bridge.run_stage7
run_stage3 = _stage8_bridge.run_stage3
run_stage4 = _stage8_bridge.run_stage4
run_stage5a_and_5c = _stage8_bridge.run_stage5a_and_5c
load_reference = _stage8_bridge.load_reference
should_fork = _stage8_bridge.should_fork
run_stage5b = _stage8_bridge.run_stage5b
run_stage6 = _stage8_bridge.run_stage6
flagged_facets = _stage8_bridge.flagged_facets
