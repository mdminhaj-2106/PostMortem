"""Stage 6 orchestrator -- (DecompositionResult, FingerprintResult) -> EvidenceResult.
See .claude/plans/stage6-evidence-retrieval.md.

Usage:
    python run_stage6.py --episode-id 15

Same "first Stage 3 result" simplicity as every other stage's own CLI
(stage4.py/stage5a.py) -- for the seeded demo's actual cluster (`cluster_15_93_94`),
see test_stage6.py, which selects it explicitly rather than taking whichever
cluster happens to sort first.
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

import embedding_index
import entity_scope_filter
import ner_sentiment_tagger
import output_schema
import temporal_tagger
from models import EvidenceItem, EvidenceResult


def _load_candidate_tickets(cur, episode_id):
    cur.execute(
        "SELECT ticket_id, day_offset, customer_id, text FROM support_tickets "
        "WHERE episode_id=%s AND text IS NOT NULL",
        (episode_id,),
    )
    return cur.fetchall()


def _load_customer_lookup(cur, episode_id, customer_ids):
    if not customer_ids:
        return {}
    cur.execute(
        "SELECT customer_id, segment, region FROM customers WHERE episode_id=%s AND customer_id = ANY(%s)",
        (episode_id, list(customer_ids)),
    )
    return {customer_id: {"segment": segment, "region": region} for customer_id, segment, region in cur.fetchall()}


def _product_scope(matched_dims, facets):
    if "product" not in matched_dims:
        return None
    return next(value for dimension, value in facets if dimension == "product")


def run_stage6(cur, episode_id, decomposition_result, fingerprint_result):
    if not decomposition_result.slices:
        print("no decomposed slices -- nothing to scope evidence against")
        return EvidenceResult(episode_id=episode_id, cluster_id=decomposition_result.cluster_id, evidence=[])

    window_start = decomposition_result.slices[0].window_start_day_offset
    window_end = decomposition_result.slices[0].window_end_day_offset

    all_tickets = _load_candidate_tickets(cur, episode_id)
    print(f"all evidence items in the system (support tickets with text): {len(all_tickets)}")

    facets = entity_scope_filter.flagged_facets(decomposition_result)
    print(f"flagged facets: {facets}")

    scoped = entity_scope_filter.filter_tickets(cur, episode_id, facets, all_tickets)
    print(f"after Filter 1 (segment/region/product scope): {len(scoped)}")

    customer_lookup = _load_customer_lookup(cur, episode_id, {ticket[2] for ticket, _dims in scoped})

    tagged = []
    excluded_missing_timestamp = 0
    for ticket, matched_dims in scoped:
        day_offset = ticket[1]
        temporal_tag = temporal_tagger.tag(day_offset, window_start, window_end)
        if temporal_tag is None:
            excluded_missing_timestamp += 1
            continue
        tagged.append((ticket, matched_dims, temporal_tag))
    print(
        f"after Filter 2 (temporal tagging, {excluded_missing_timestamp} excluded for missing timestamp): "
        f"{len(tagged)}"
    )

    query_text = embedding_index.build_query(fingerprint_result.top_cause)
    ranked = embedding_index.rank(tagged, query_text)
    print(
        f"after Filter 3 (semantic relevance >= {embedding_index.RELEVANCE_THRESHOLD}, "
        f"capped at {embedding_index.MAX_EVIDENCE_ITEMS}): {len(ranked)}"
    )

    evidence = []
    for ticket, matched_dims, temporal_tag, score in ranked:
        _ticket_id, day_offset, customer_id, text = ticket
        customer = customer_lookup.get(customer_id, {})
        evidence.append(EvidenceItem(
            source_type="support_ticket",
            text_snippet=text,
            day_offset=day_offset,
            temporal_tag=temporal_tag,
            entity_link_confidence="HIGH",
            segment_scope=customer.get("segment"),
            region_scope=customer.get("region"),
            product_scope=_product_scope(matched_dims, facets),
            relevance_score=round(score, 4),
            sentiment=ner_sentiment_tagger.sentiment(text),
        ))

    result = EvidenceResult(episode_id=episode_id, cluster_id=decomposition_result.cluster_id, evidence=evidence)
    output_schema.validate(result)
    return result


def main():
    import stage4_bridge
    import stage5a_bridge

    parser = argparse.ArgumentParser(description="Run Stage 6 evidence retrieval.")
    parser.add_argument("--episode-id", type=int, required=True)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            stage3_results = stage4_bridge.run_stage3(cur, args.episode_id)
            if not stage3_results:
                print(f"no Stage 3 results for episode {args.episode_id}")
                return
            stage3_result = stage3_results[0]
            print(f"investigating: {stage3_result}")

            decomposition_result = stage4_bridge.run_stage4(cur, args.episode_id, stage3_result)
            reference = stage5a_bridge.load_reference()
            fingerprint_result, _cold_start_result = stage5a_bridge.run_stage5a_and_5c(
                cur, args.episode_id, stage3_result, decomposition_result, reference
            )
            print(f"fingerprint: {fingerprint_result}")

            result = run_stage6(cur, args.episode_id, decomposition_result, fingerprint_result)
            print(f"\nfinal evidence set ({len(result.evidence)} item(s)):")
            for item in result.evidence:
                print(f"  {item}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
