"""Re-exports Stage 8's own run_stage8 plus its already-built stage3/4/5a/5c/
[5b]/6/7 bridges transitively (via Stage 8's own stage7_bridge.py), so Stage
9's CLI can replay the full upstream chain without re-deriving each layer's
cross-import plumbing a second time. Same sys.path + sys.modules-eviction
pattern as every other cross-stage bridge in this repo -- the eviction list
covers everything stage8.py imports at its own top level (which would
otherwise shadow Stage 9's own same-named files) plus stage7_bridge itself
(plan step 2 -- mirror Stage 8's own stage7_bridge.py list-building exactly).

Also sideways-bridges into Stage 6's entity_scope_filter.py directly (same
reasoning as Stage 5a's own sideways bridge into Stage 5c) -- neither Stage
7's nor Stage 8's own bridge re-exports it (only run_stage6 itself), and it's
the real, already-built target-scope-binding function Stage 9 needs (plan
finding #3), not something worth re-deriving.
"""

import importlib
import os
import sys

_STAGE8_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage08_counterfactual_impact")
)
_STAGE8_MODULE_NAMES = (
    "models", "config", "hypothesis_eligibility", "impact", "reconstruction",
    "uncertainty", "output_schema", "canonical_bridge", "stage8", "stage7_bridge",
)

_STAGE6_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage06_evidence_retrieval")
)
_STAGE6_MODULE_NAMES = (
    "models", "output_schema", "entity_scope_filter", "temporal_tagger",
    "embedding_index", "ner_sentiment_tagger", "run_stage6",
)


def _import_stage8():
    for name in _STAGE8_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE8_DIR)
    try:
        stage8_module = importlib.import_module("stage8")
        stage7_bridge = importlib.import_module("stage7_bridge")
    finally:
        sys.path.remove(_STAGE8_DIR)
        for name in _STAGE8_MODULE_NAMES:
            sys.modules.pop(name, None)
    return stage8_module, stage7_bridge


def _import_entity_scope_filter():
    for name in _STAGE6_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE6_DIR)
    try:
        module = importlib.import_module("entity_scope_filter")
    finally:
        sys.path.remove(_STAGE6_DIR)
        for name in _STAGE6_MODULE_NAMES:
            sys.modules.pop(name, None)
    return module


_stage8, _stage7_bridge = _import_stage8()
_entity_scope_filter = _import_entity_scope_filter()

run_stage8 = _stage8.run_stage8
run_stage7 = _stage7_bridge.run_stage7
run_stage3 = _stage7_bridge.run_stage3
run_stage4 = _stage7_bridge.run_stage4
run_stage5a_and_5c = _stage7_bridge.run_stage5a_and_5c
load_reference = _stage7_bridge.load_reference
should_fork = _stage7_bridge.should_fork
run_stage5b = _stage7_bridge.run_stage5b
run_stage6 = _stage7_bridge.run_stage6
flagged_facets = _entity_scope_filter.flagged_facets
