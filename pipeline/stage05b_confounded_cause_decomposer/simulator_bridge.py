"""Offline-only: re-exports the real generator's effect_fraction, the ground-truth
intensity math the scorer grades against -- never reimplemented, so the scorer can't
drift from the truth it's scoring (design report §11.2). Never imported by stage5b.py's
runtime path.
"""

import importlib
import os
import sys

_SIMULATOR_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "simulator", "layer1_ground_truth")
)
_SIMULATOR_MODULE_NAMES = ("generate", "bootstrap")


def _import():
    for name in _SIMULATOR_MODULE_NAMES:
        sys.modules.pop(name, None)
    sys.path.insert(0, _SIMULATOR_DIR)
    try:
        return importlib.import_module("generate")
    finally:
        sys.path.remove(_SIMULATOR_DIR)
        for name in _SIMULATOR_MODULE_NAMES:
            sys.modules.pop(name, None)


_generate = _import()
effect_fraction = _generate.effect_fraction
