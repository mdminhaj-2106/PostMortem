"""Re-exports Stage 5c's real run_stage5c + its reference-loader, so stage5a.py can
serve a mixed decomposition (some slices ELIGIBLE enough for 5a's own classifier,
others LIMITED_HISTORY/INSUFFICIENT_DATA and routed to 5c's borrowed percentile)
without duplicating either stage's logic. Same sys.path + sys.modules-eviction pattern
as every other cross-stage bridge in this repo -- a sideways bridge (5a and 5c are
siblings off Stage 4, not a downstream/upstream pair), same reasoning Stage 5b already
used to bridge into Stage 5a despite the numeric ordering.
"""

import importlib
import os
import sys

_STAGE5C_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage05c_cold_start_analogy_handler")
)
_STAGE5C_MODULE_NAMES = (
    "models", "stage2_bridge", "stage4_bridge", "stage3_bridge",
    "borrowed_percentile", "reference_builder", "output_schema", "stage5c",
)


def _import_stage5c():
    for name in _STAGE5C_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE5C_DIR)
    try:
        stage5c_module = importlib.import_module("stage5c")
        reference_builder = importlib.import_module("reference_builder")
    finally:
        sys.path.remove(_STAGE5C_DIR)
        for name in _STAGE5C_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage5c_module, reference_builder


_stage5c, _reference_builder = _import_stage5c()
run_stage5c = _stage5c.run_stage5c
load_reference = _reference_builder.load_reference
build_reference = _reference_builder.build_reference
