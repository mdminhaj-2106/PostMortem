"""Re-exports Stage 4's real run_stage4 -- and, transitively, Stage 3's run_stage3
via Stage 4's own stage3_bridge.py -- so Stage 6 can re-derive a real
DecompositionResult end-to-end without a separate stage3_bridge.py of its own.
Stage 6 only needs window bounds/cluster_id/episode_id, all of which
DecompositionResult already carries per slice (window_start_day_offset/
window_end_day_offset are the same across every slice in one decomposition --
decomposer.py passes them in from the one StageThreeResult).

Same sys.path + sys.modules-eviction pattern as every other cross-stage bridge in
this repo (architecture.md's Known architectural risks).
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
        stage4_module = importlib.import_module("stage4")
        stage3_bridge = importlib.import_module("stage3_bridge")
    finally:
        sys.path.remove(_STAGE4_DIR)
        for name in _STAGE4_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage4_module, stage3_bridge


_stage4, _stage3_bridge = _import_stage4()
run_stage4 = _stage4.run_stage4
run_stage3 = _stage3_bridge.run_stage3
