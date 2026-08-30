"""Stage 7 orchestrator -- (FingerprintResult, Optional[ConfoundedAttributionResult],
Stage5cResult, EvidenceResult) -> Stage7Result. See
.claude/plans/stage7-hypothesis-debate-ranking.md.

Usage:
    python stage7.py --episode-id 15
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

import abstention
import candidate_assembler
import confidence_resolver
import contradiction_resolver
import evidence_analytical
import evidence_observational
import evidence_structural
import hypothesis_builder
import output_schema
import ranker
import support_resolver
from models import RankedHypothesis, Stage7Result


def run_stage7(episode_id, cluster_id, fingerprint_result, stage5b_result, cold_start_result, evidence_result):
    single_causes = candidate_assembler.assemble_single_candidates(fingerprint_result)
    joint_candidates = candidate_assembler.assemble_joint_candidates(stage5b_result)
    hypotheses = hypothesis_builder.build_hypotheses(single_causes, joint_candidates)

    evidence_by_hypothesis = evidence_observational.link_evidence(
        hypotheses, evidence_result, fingerprint_result.top_cause
    )

    ranked_hypotheses = []
    for h in hypotheses:
        analytical = evidence_analytical.build_analytical_evidence(
            h, fingerprint_result, stage5b_result, cold_start_result
        )
        structural = evidence_structural.build_structural_evidence(h)
        refs = evidence_by_hypothesis.get(h.hypothesis_id, [])
        supporting = [e for e in refs if e.direction == "SUPPORTING"]
        contradicting = [e for e in refs if e.direction == "CONTRADICTING"]
        neutral = [e for e in refs if e.direction == "NEUTRAL"]

        support_level, support_codes = support_resolver.resolve_support(h, analytical, supporting, structural)
        contradiction_status, contradiction_codes = contradiction_resolver.resolve_contradiction(contradicting)
        confidence_bucket, reason_codes = confidence_resolver.resolve_confidence(
            support_level, support_codes, contradiction_status, analytical, structural
        )

        ranked_hypotheses.append(RankedHypothesis(
            hypothesis_id=h.hypothesis_id,
            member_causes=h.member_causes,
            hypothesis_type=h.hypothesis_type,
            identifiability=h.identifiability,
            borrowed=analytical.stage5c_is_borrowed,
            confidence_bucket=confidence_bucket,
            confidence_reason_codes=reason_codes,
            analytical_evidence=analytical,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            neutral_evidence=neutral,
            structural_evidence=structural,
            contradiction_status=contradiction_status,
            contradiction_reason_codes=contradiction_codes,
            evidence_count=len(refs),
            # No stable id/customer_id survives downstream of Stage 6's own
            # output -- plan finding #8 -- so independence can't be grouped
            # beyond "each Stage 6 evidence item is its own independent source".
            independent_source_count=len(refs),
            independent_entity_count=len(refs),
        ))

    ranked_hypotheses = ranker.rank(ranked_hypotheses)
    abstained, abstention_codes = abstention.determine_abstention(ranked_hypotheses)

    result = Stage7Result(
        episode_id=episode_id, cluster_id=cluster_id,
        hypotheses=ranked_hypotheses, abstained=abstained,
        abstention_reason_codes=abstention_codes,
    )
    output_schema.validate(result)
    return result


def main():
    import stage4_bridge
    import stage5a_bridge
    import stage5b_bridge
    import stage6_bridge

    parser = argparse.ArgumentParser(description="Run Stage 7 hypothesis debate & ranking.")
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
            fingerprint_result, cold_start_result = stage5a_bridge.run_stage5a_and_5c(
                cur, args.episode_id, stage3_result, decomposition_result, reference
            )
            print(f"fingerprint: {fingerprint_result}")

            forked, fork_reason = stage5b_bridge.should_fork(fingerprint_result.cause_scores, decomposition_result)
            print(f"Stage 5b fork decision: {forked} ({fork_reason})")
            stage5b_result = (
                stage5b_bridge.run_stage5b(cur, args.episode_id, fingerprint_result, decomposition_result)
                if forked else None
            )
            if stage5b_result:
                print(f"5b: {stage5b_result}")

            evidence_result = stage6_bridge.run_stage6(cur, args.episode_id, decomposition_result, fingerprint_result)
            print(f"evidence: {len(evidence_result.evidence)} item(s)")

            result = run_stage7(
                args.episode_id, stage3_result.cluster_id,
                fingerprint_result, stage5b_result, cold_start_result, evidence_result,
            )
            print(f"\nabstained={result.abstained} ({result.abstention_reason_codes})")
            for rh in result.hypotheses:
                print(
                    f"  rank {rh.rank} ({rh.rank_group}) [{rh.confidence_bucket}] "
                    f"{rh.member_causes} -- {rh.confidence_reason_codes}"
                )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
