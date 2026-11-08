"""Stage 5b orchestrator -- (FingerprintResult, DecompositionResult) -> ConfoundedAttributionResult.
See docs/02-stage-design-reports/stage5b-confounded-cause-decomposer-revised.md.

Usage:
    python stage5b.py --episode-id 15
"""

import argparse
import json
import os

import numpy as np
import psycopg2
from dotenv import load_dotenv

import attribution
import deviation_matrix
import identifiability
import shape_features
from cause_config import PROBABILITY_FLOOR, SEASONAL, UNEXPLAINED
from models import CauseContribution, ConfoundedAttributionResult

_ARTIFACT_PATH = os.path.join(os.path.dirname(__file__), "basis", "artifacts", "bases.json")
_KPI_PREFERENCE = ("revenue", "orders_count", "units_sold", "avg_order_value", "active_customers_purchased_30d")


def _load_bases():
    with open(_ARTIFACT_PATH) as f:
        artifact = json.load(f)
    if artifact["feature_version"] != shape_features.FEATURE_VERSION:
        raise RuntimeError(
            f"bases.json was built with feature_version={artifact['feature_version']!r}, "
            f"runtime shape_features is {shape_features.FEATURE_VERSION!r} -- rerun build_bases.py"
        )
    return artifact


def _pick_kpi(decomposition_result):
    names = {s.kpi_name for s in decomposition_result.slices}
    return next((k for k in _KPI_PREFERENCE if k in names), next(iter(names)))


def run_stage5b(cur, episode_id, stage5a_result, decomposition_result):
    if not decomposition_result.slices:
        raise ValueError("empty decomposition_result -- nothing to attribute")

    window_start = decomposition_result.slices[0].window_start_day_offset
    window_end = decomposition_result.slices[0].window_end_day_offset
    kpi_name = _pick_kpi(decomposition_result)

    artifact = _load_bases()
    candidates = [c for c, s in stage5a_result.cause_scores.items() if s >= PROBABILITY_FLOOR]
    bases = {c: np.array(artifact["bases"][c]["basis"]) for c in candidates if c in artifact["bases"]}
    sample_counts = {c: artifact["bases"][c]["n"] for c in bases}
    if SEASONAL in artifact["bases"]:
        bases[SEASONAL] = np.array(artifact["bases"][SEASONAL]["basis"])
        sample_counts[SEASONAL] = artifact["bases"][SEASONAL]["n"]

    matrix = deviation_matrix.build(cur, episode_id, kpi_name, window_start, window_end)
    x_obs = shape_features.build_shape_vector(matrix, window_start, window_end)
    magnitude = sum(
        abs(residual)
        for (dimension, _slice_value), residuals in matrix.items() if dimension == "region"
        for day, _expected, residual in residuals
        if residual is not None and window_start <= day <= window_end
    )

    # Onset-based declared-pair merging needs per-cause onset days 5a doesn't carry in this
    # slice's FingerprintResult -- the empirical cosine gate (identifiability.assess with no
    # onsets) still catches genuinely collinear bases, just not the declared-pair-by-lag path.
    # ponytail: declared-pair lag check deferred until 5a's contract carries per-cause onsets.
    groups, verdict = identifiability.assess(list(bases), bases)

    fit_bases, group_by_fit_name = {}, {}
    for group in groups:
        if len(group) == 1:
            fit_bases[group[0]] = bases[group[0]]
            group_by_fit_name[group[0]] = group
        else:
            joint_name = "+".join(sorted(group))
            fit_bases[joint_name] = np.mean([bases[c] for c in group], axis=0)
            group_by_fit_name[joint_name] = group

    raw_contributions, unexplained_amount, fit_quality = attribution.fit(x_obs, fit_bases, magnitude)
    total = sum(raw_contributions.values()) + unexplained_amount

    contributions = []
    for name, amount in raw_contributions.items():
        group = group_by_fit_name[name]
        is_joint = len(group) > 1
        contributions.append(CauseContribution(
            cause=name,
            contribution=amount,
            share=(amount / total) if total > 0 else 0.0,
            basis_provenance="SEASONAL_BASELINE" if name == SEASONAL else "LEARNED",
            basis_sample_count=min(sample_counts[c] for c in group),
            identifiability="NON_IDENTIFIABLE_JOINT" if is_joint else "IDENTIFIED",
            member_causes=group if is_joint else None,
        ))
    contributions.append(CauseContribution(
        cause=UNEXPLAINED,
        contribution=unexplained_amount,
        share=(unexplained_amount / total) if total > 0 else 1.0,
        basis_provenance="RESIDUAL",
        basis_sample_count=None,
        identifiability="IDENTIFIED",
    ))

    return ConfoundedAttributionResult(
        episode_id=episode_id, cluster_id=stage5a_result.cluster_id, kpi_name=kpi_name,
        window_start_day_offset=window_start, window_end_day_offset=window_end,
        observed_deviation=magnitude, contributions=contributions,
        unexplained_share=(unexplained_amount / total) if total > 0 else 1.0,
        fit_quality=fit_quality, identifiability_verdict=verdict,
    )


def main():
    import pipeline_bridge  # imported lazily -- CLI-only, same as other stages' own bridges
    import stage5a_bridge

    parser = argparse.ArgumentParser(description="Run Stage 5b confounded-cause decomposer.")
    parser.add_argument("--episode-id", type=int, required=True)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            stage3_results = pipeline_bridge.run_stage3(cur, args.episode_id)
            if not stage3_results:
                print(f"no Stage 3 results for episode {args.episode_id}")
                return
            stage3_result = stage3_results[0]
            decomposition_result = pipeline_bridge.run_stage4(cur, args.episode_id, stage3_result)
            stage5a_result = stage5a_bridge.run_stage5a(cur, args.episode_id, stage3_result, decomposition_result)
            print(f"5a: {stage5a_result}")
            result = run_stage5b(cur, args.episode_id, stage5a_result, decomposition_result)
            print(result)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
