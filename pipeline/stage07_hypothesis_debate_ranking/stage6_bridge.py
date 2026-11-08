"""Re-exports Stage 6's real run_stage6 (the plain function, not its CLI main()),
plus EvidenceResult/EvidenceItem for offline test fixtures. run_stage6.py's own
stage4_bridge/stage5a_bridge imports are lazy inside its main() only, so importing
the "run_stage6" module here never touches them.

Same sys.path + sys.modules-eviction pattern as every other cross-stage bridge in
this repo (architecture.md's Known architectural risks).
"""

import importlib
import os
import sys

_STAGE6_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "stage06_evidence_retrieval")
)
_STAGE6_MODULE_NAMES = (
    "models", "output_schema", "entity_scope_filter", "temporal_tagger",
    "embedding_index", "ner_sentiment_tagger", "run_stage6",
)


def _import_stage6():
    for name in _STAGE6_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE6_DIR)
    try:
        run_stage6_module = importlib.import_module("run_stage6")
        models_module = importlib.import_module("models")
    finally:
        sys.path.remove(_STAGE6_DIR)
        for name in _STAGE6_MODULE_NAMES:
            sys.modules.pop(name, None)
    return run_stage6_module, models_module


_run_stage6_module, _stage6_models = _import_stage6()
run_stage6 = _run_stage6_module.run_stage6
EvidenceResult = _stage6_models.EvidenceResult
EvidenceItem = _stage6_models.EvidenceItem
