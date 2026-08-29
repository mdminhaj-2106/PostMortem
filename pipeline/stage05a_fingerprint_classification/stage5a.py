"""Stage 5a orchestrator -- (StageThreeResult, DecompositionResult) -> FingerprintResult.
See .claude/plans/stage5a-fingerprint-classification.md.

Usage:
    python stage5a.py --episode-id 1
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

import classifier
import onset_fetcher
import signatures
from models import FingerprintResult

# Onset only discriminates marketing_cut/product_outage (signatures.onset_lean) --
# pick whichever non-customer KPI is actually in this cluster to read its onset shape.
_ONSET_KPI_PREFERENCE = ("revenue", "orders_count", "units_sold", "avg_order_value")


def _pick_onset_kpi(kpi_names):
    for kpi in _ONSET_KPI_PREFERENCE:
        if kpi in kpi_names:
            return kpi
    return next((k for k in kpi_names if k != "active_customers_purchased_30d"), "revenue")


def run_stage5a(cur, episode_id, stage3_result, decomposition_result):
    product_signal = signatures.product_concentration(decomposition_result)

    window_start = stage3_result.window_start_day_offset
    window_end = stage3_result.window_end_day_offset
    day_range = range(window_start, window_end + 8)  # +8: onset_lean needs window_start+7

    customers_series = onset_fetcher.fetch_residual_series(
        cur, episode_id, "active_customers_purchased_30d", day_range
    )
    orders_series = onset_fetcher.fetch_residual_series(cur, episode_id, "orders_count", day_range)
    revenue_series = onset_fetcher.fetch_residual_series(cur, episode_id, "revenue", day_range)
    kpi_shift_signal = signatures.dominant_kpi_shift(
        customers_series, orders_series, revenue_series, window_start, window_end
    )

    onset_kpi = _pick_onset_kpi(stage3_result.kpi_names)
    onset_series = {"orders_count": orders_series, "revenue": revenue_series}.get(
        onset_kpi
    ) or onset_fetcher.fetch_residual_series(cur, episode_id, onset_kpi, day_range)
    onset_signal = signatures.onset_lean(onset_series, window_start)

    cause_scores, confidence, top_cause, signals_used = classifier.classify(
        product_signal, kpi_shift_signal, onset_signal
    )
    return FingerprintResult(
        episode_id=episode_id, cluster_id=stage3_result.cluster_id,
        cause_scores=cause_scores, top_cause=top_cause,
        confidence=confidence, signals_used=signals_used,
    )


def main():
    import stage3_bridge  # imported lazily -- CLI-only, same as stage4.py's own bridge import
    import stage4_bridge

    parser = argparse.ArgumentParser(description="Run Stage 5a fingerprint classification.")
    parser.add_argument("--episode-id", type=int, required=True)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            stage3_results = stage3_bridge.run_stage3(cur, args.episode_id)
            if not stage3_results:
                print(f"no Stage 3 results for episode {args.episode_id}")
                return
            stage3_result = stage3_results[0]
            decomposition_result = stage4_bridge.run_stage4(cur, args.episode_id, stage3_result)
            print(f"classifying: {stage3_result}")
            result = run_stage5a(cur, args.episode_id, stage3_result, decomposition_result)
            print(result)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
