"""Stage 2 orchestrator -- wires Layers 1-7 in the design doc's §17 flow order.
See docs/02-stage-design-reports/stage2-relevance-extraction-architecture.md and
.claude/plans/stage2-relevance-extraction.md.

Usage:
    python stage2.py --episode-id 1 --kpi revenue
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

import business_importance
import candidate_selection
import classification
import eligibility
import ingest
import relevance
import unusualness
from baseline import compute_residuals
from models import StageTwoResult

_ELIGIBILITY_TO_HISTORY_CONFIDENCE = {
    eligibility.ELIGIBLE: "HIGH",
    eligibility.LIMITED_HISTORY: "MEDIUM",
    eligibility.LOW_CONFIDENCE: "LOW",
}


def _fetch_n_days(cur, episode_id):
    cur.execute("SELECT n_days FROM episodes WHERE episode_id=%s", (episode_id,))
    return cur.fetchone()[0]


def run_stage2(cur, episode_id, kpi_name, day_range=None, other_kpi_candidates=None):
    """other_kpi_candidates: optional {day_offset: set(kpi_names)} of candidates from
    OTHER KPIs' runs, so this KPI's relationship-context evidence (Layer 4) can see
    same-day co-occurrence. Callers running both KPIs should run one first, pass its
    candidate days in, for the other."""
    if day_range is None:
        day_range = range(_fetch_n_days(cur, episode_id))
    day_range = list(day_range)
    other_kpi_candidates = other_kpi_candidates or {}

    timeline = ingest.load_kpi_timeline(cur, episode_id, kpi_name, day_range)
    elig = eligibility.assess_eligibility(timeline)

    if elig == eligibility.INSUFFICIENT_DATA:
        return [
            StageTwoResult(
                episode_id=episode_id, day_offset=d, kpi_name=kpi_name,
                analysis_status="INSUFFICIENT_DATA", confidence="LOW",
            )
            for d in day_range
        ]

    history_confidence = _ELIGIBILITY_TO_HISTORY_CONFIDENCE[elig]
    residuals = compute_residuals(timeline)
    scores = unusualness.score_unusualness(residuals)
    candidate_days = candidate_selection.select_candidates(scores)
    score_by_day = dict(scores)

    relevance_by_day = {}
    results_by_day = {}
    for day_offset in day_range:
        score = score_by_day.get(day_offset)
        if day_offset not in candidate_days:
            relevance_by_day[day_offset] = False
            results_by_day[day_offset] = StageTwoResult(
                episode_id=episode_id, day_offset=day_offset, kpi_name=kpi_name,
                analysis_status="ANALYZED", confidence=history_confidence,
                unusualness_score=score, unusualness_basis=unusualness.BASIS if score is not None else None,
                history_confidence=history_confidence,
            )
            continue

        other_candidates_today = other_kpi_candidates.get(day_offset, set())
        importance_level, importance_evidence = business_importance.assess_importance(
            kpi_name, other_candidates_today
        )
        has_relationship_context = any(e["type"] == "KNOWN_RELATIONSHIP" for e in importance_evidence)
        relevance_level, priority_tier = relevance.resolve_relevance(
            score, importance_level, has_relationship_context
        )
        related_candidates = [e["target"] for e in importance_evidence if e["type"] == "KNOWN_RELATIONSHIP"]
        cluster_id = f"cluster_{episode_id}_{kpi_name}_{day_offset}" if related_candidates else None

        relevance_by_day[day_offset] = relevance_level != "NOT_RELEVANT"
        results_by_day[day_offset] = StageTwoResult(
            episode_id=episode_id, day_offset=day_offset, kpi_name=kpi_name,
            analysis_status="ANALYZED", confidence=history_confidence,
            unusualness_score=score, unusualness_basis=unusualness.BASIS,
            history_confidence=history_confidence,
            business_importance_level=importance_level, business_importance_evidence=importance_evidence,
            cluster_id=cluster_id, related_candidates=related_candidates,
            relevance_level=relevance_level, priority_tier=priority_tier,
        )

    trajectory = classification.classify_trajectory(
        day_range, [relevance_by_day.get(d, False) for d in day_range]
    )
    for day_offset, state, evidence in trajectory:
        results_by_day[day_offset].classification_state = state
        results_by_day[day_offset].classification_evidence = evidence

    return [results_by_day[d] for d in day_range]


def main():
    parser = argparse.ArgumentParser(description="Run Stage 2 relevance extraction + classification.")
    parser.add_argument("--episode-id", type=int, required=True)
    parser.add_argument("--kpi", choices=ingest.KPI_NAMES, default="revenue")
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            for r in run_stage2(cur, args.episode_id, args.kpi):
                print(r)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
