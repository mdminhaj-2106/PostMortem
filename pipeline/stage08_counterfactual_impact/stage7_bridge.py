"""Re-exports Stage 7's own run_stage7 plus its already-built stage3/4/5a/5b/6
bridges transitively, so Stage 8's CLI can replay the full upstream chain without
re-deriving each layer's cross-import plumbing a second time. Same sys.path +
sys.modules-eviction pattern as every other cross-stage bridge in this repo -- the
eviction list is wider here since it must also cover everything stage7.py itself
imports at its own top level (models, output_schema, and its sibling resolver/
ranker/etc. modules), which would otherwise shadow Stage 8's own same-named files.

Stage 07's own stage5b_bridge.py already fixed a real bare-module-name collision
(its "stage4_bridge" vs Stage 5b's internal "stage4_bridge", see
architecture.md's Known architectural risks #6) -- importing it here as a
black box reuses that fix rather than re-deriving it.
"""

import importlib
import os
import sys

_STAGE7_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage07_hypothesis_debate_ranking")
)
_STAGE7_MODULE_NAMES = (
    "models", "cause_config", "candidate_assembler", "hypothesis_builder",
    "evidence_analytical", "evidence_observational", "evidence_structural",
    "support_resolver", "contradiction_resolver", "confidence_resolver", "ranker",
    "abstention", "output_schema", "stage7",
    "stage4_bridge", "stage5a_bridge", "stage5b_bridge", "stage6_bridge",
)


def _import_stage7():
    for name in _STAGE7_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE7_DIR)
    try:
        stage7_module = importlib.import_module("stage7")
        stage4_bridge = importlib.import_module("stage4_bridge")
        stage5a_bridge = importlib.import_module("stage5a_bridge")
        stage5b_bridge = importlib.import_module("stage5b_bridge")
        stage6_bridge = importlib.import_module("stage6_bridge")
    finally:
        sys.path.remove(_STAGE7_DIR)
        for name in _STAGE7_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage7_module, stage4_bridge, stage5a_bridge, stage5b_bridge, stage6_bridge


_stage7, _stage4_bridge, _stage5a_bridge, _stage5b_bridge, _stage6_bridge = _import_stage7()

run_stage7 = _stage7.run_stage7
run_stage3 = _stage4_bridge.run_stage3
run_stage4 = _stage4_bridge.run_stage4
run_stage5a_and_5c = _stage5a_bridge.run_stage5a_and_5c
load_reference = _stage5a_bridge.load_reference
should_fork = _stage5b_bridge.should_fork
run_stage5b = _stage5b_bridge.run_stage5b
run_stage6 = _stage6_bridge.run_stage6
