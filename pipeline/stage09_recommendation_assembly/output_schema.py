"""Rejects a fabricated per-member joint split, a monetary-cost field, an
LLM import anywhere in this package, and a primary/alternative referencing a
hypothesis_id Stage 7 never produced. Same dual-validation pattern as every
other stage's output_schema.py (plan step 10, acceptance criteria).
"""

import os

from models import DECISION_STATUSES

_COST_FIELD_MARKERS = ("cost", "budget", "roi", "price_tag")
# design doc §96's own regression test, made real and greppable rather than
# just asserted in prose.
_LLM_MARKERS = ("openai", "anthropic", "langchain", "transformers", "torch", "genai")


def _recommendation_hypothesis_ids(result):
    ids = set()
    if result.primary_recommendation is not None:
        ids.add(result.primary_recommendation.hypothesis_id)
    ids.update(r.hypothesis_id for r in result.alternatives)
    return ids


def validate(result, stage7_result):
    assert result.decision_status in DECISION_STATUSES, f"free-text decision_status: {result.decision_status!r}"

    if result.decision_status == "NO_DEFENSIBLE_ACTION":
        assert result.primary_recommendation is None, "NO_DEFENSIBLE_ACTION must not carry a primary recommendation"
        return

    assert result.primary_recommendation is not None, f"{result.decision_status} requires a primary recommendation"

    known_ids = {h.hypothesis_id for h in stage7_result.hypotheses}
    for hypothesis_id in _recommendation_hypothesis_ids(result):
        assert hypothesis_id in known_ids, f"recommendation references unknown hypothesis_id: {hypothesis_id!r}"

    for rec in [result.primary_recommendation] + result.alternatives:
        assert not any(k in rec.__dataclass_fields__ for k in _COST_FIELD_MARKERS), \
            f"monetary-cost-shaped field found on Recommendation: {rec.__dataclass_fields__.keys()!r}"
        # a joint hypothesis carries exactly one aggregate expected_impact/owner
        # set -- Recommendation structurally has no per-member breakdown field
        # to fabricate one into, so this is enforced by the dataclass shape
        # itself (models.Recommendation), not re-checked per instance here.


def assert_no_llm_import():
    """Greppable regression test (design doc §96) -- fails loudly if any
    module in this package's own source imports a generative-model library."""
    package_dir = os.path.dirname(__file__)
    offenders = []
    for filename in os.listdir(package_dir):
        if not filename.endswith(".py") or filename.startswith("test_"):
            continue
        with open(os.path.join(package_dir, filename)) as f:
            for line_no, line in enumerate(f, start=1):
                stripped = line.strip()
                if not (stripped.startswith("import ") or stripped.startswith("from ")):
                    continue
                if any(marker in stripped.lower() for marker in _LLM_MARKERS):
                    offenders.append(f"{filename}:{line_no}: {stripped}")
    assert not offenders, f"LLM/generative-model import found in stage09 package: {offenders!r}"
