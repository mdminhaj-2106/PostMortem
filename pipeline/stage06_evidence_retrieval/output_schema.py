"""Rejects any free-text field outside the fixed enums (design doc §5's still-valid
rule, same discipline as every other stage's output_schema.py). segment_scope/
region_scope/product_scope/text_snippet are exempt -- real per-customer/episode
data, not a free-text field this stage fabricated.
"""

from models import ENTITY_LINK_CONFIDENCES, SENTIMENTS, SOURCE_TYPES, TEMPORAL_TAGS


def validate(result):
    for item in result.evidence:
        assert item.source_type in SOURCE_TYPES, f"free-text source_type: {item.source_type!r}"
        assert item.temporal_tag in TEMPORAL_TAGS, f"free-text temporal_tag: {item.temporal_tag!r}"
        assert item.entity_link_confidence in ENTITY_LINK_CONFIDENCES, \
            f"free-text entity_link_confidence: {item.entity_link_confidence!r}"
        assert item.sentiment in SENTIMENTS, f"free-text sentiment: {item.sentiment!r}"
        assert isinstance(item.relevance_score, (int, float)) and 0.0 <= item.relevance_score <= 1.0, \
            f"relevance_score out of range: {item.relevance_score!r}"
        assert item.text_snippet, "evidence item must carry real text"
