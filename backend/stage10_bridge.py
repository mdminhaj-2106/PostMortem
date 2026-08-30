"""Re-exports Stage 10's own stage9_bridge chain (Stage 3 through 9) plus
personas.narrate_for_all_personas, one bridge layer past
stage10_persona_narrative_routing/'s own stage9_bridge.py. Same sys.path +
sys.modules-eviction pattern as every other cross-stage bridge in this repo --
the deepest chain yet (backend -> Stage 10 -> 9 -> 8 -> 7 -> 6/5b/5a/4/3), so
the eviction list mirrors Stage 10's own list-building exactly rather than
hand-deriving a shorter one (every shorter hand-derived list in this repo has
eventually collided -- see architecture.md's Known Architectural Risks).

One wrinkle, same shape as stage06_evidence_retrieval/stage5a_bridge.py's own:
personas.narrate_for_all_personas does its own lazy `from stage11_bridge import
narrate_incident` *inside* its function body, which runs at call time -- long
after this module's sys.path insert has been removed. A plain `import` checks
sys.modules before touching sys.path, so this bridge explicitly imports
stage11_bridge itself too (not just personas/stage9_bridge) to warm that cache
entry, and "stage11_bridge" is deliberately left OUT of the post-import
eviction (unlike every other name here) so personas.py's later lazy import
finds it already cached instead of failing a real path lookup. (A first attempt
at this bridge added "stage11_bridge" to _KEEP_CACHED without actually
importing it here -- there was nothing cached to keep, so the later call still
failed with ModuleNotFoundError. The cache only gets warmed by an import that
actually runs.)
"""

import importlib
import os
import sys

_STAGE10_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "pipeline", "stage10_persona_narrative_routing")
)
_STAGE10_MODULE_NAMES = (
    "personas", "stage11_bridge", "stage9_bridge", "stage10",
    # everything stage9_bridge.py itself evicts one layer further in --
    # mirrored here so a stale cached module from stage9_bridge's own import
    # can't leak past this bridge either.
    "models", "config", "mechanism_resolver", "lever_resolver", "action_builder",
    "owner_resolver", "feasibility", "intent_resolver", "monitoring", "success_criteria",
    "selection", "output_schema", "stage9", "stage8_bridge",
)
_KEEP_CACHED = {"stage11_bridge"}


def _import_stage10():
    for name in _STAGE10_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE10_DIR)
    try:
        stage9_bridge = importlib.import_module("stage9_bridge")
        importlib.import_module("stage11_bridge")  # warm the cache -- see module docstring
        personas = importlib.import_module("personas")
    finally:
        sys.path.remove(_STAGE10_DIR)
        for name in _STAGE10_MODULE_NAMES:
            if name not in _KEEP_CACHED:
                sys.modules.pop(name, None)
    return stage9_bridge, personas


_STAGE11_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "pipeline", "stage11_narration")
)
_STAGE11_MODULE_NAMES = ("narrate", "stage3_bridge", "priority")


def _import_stage11_pricing():
    """Sideways bridge straight into Stage 11's narrate.py for its MODEL/pricing
    constants only -- same reasoning as Stage 9's own sideways bridge into Stage 6's
    entity_scope_filter (architecture.md): the thing needed isn't re-exported by any
    stage already on this bridge chain, and it's cheaper to reach it directly than to
    thread it through personas.py/stage11_bridge.py just for this."""
    for name in _STAGE11_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _STAGE11_DIR)
    try:
        return importlib.import_module("narrate")
    finally:
        sys.path.remove(_STAGE11_DIR)
        for name in _STAGE11_MODULE_NAMES:
            sys.modules.pop(name, None)


_stage9_bridge, _personas = _import_stage10()
_narrate = _import_stage11_pricing()
NARRATION_MODEL = _narrate.MODEL
USD_PER_MTOK_IN = _narrate.USD_PER_MTOK_IN
USD_PER_MTOK_OUT = _narrate.USD_PER_MTOK_OUT

run_stage3 = _stage9_bridge.run_stage3
run_stage4 = _stage9_bridge.run_stage4
run_stage5a_and_5c = _stage9_bridge.run_stage5a_and_5c
load_reference = _stage9_bridge.load_reference
should_fork = _stage9_bridge.should_fork
run_stage5b = _stage9_bridge.run_stage5b
run_stage6 = _stage9_bridge.run_stage6
run_stage7 = _stage9_bridge.run_stage7
run_stage8 = _stage9_bridge.run_stage8
run_stage9 = _stage9_bridge.run_stage9
flagged_facets = _stage9_bridge.flagged_facets
narrate_for_all_personas = _personas.narrate_for_all_personas
