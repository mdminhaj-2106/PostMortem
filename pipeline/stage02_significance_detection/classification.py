"""Layer 7 -- Temporal Change Classification (design doc §16). Run as a full-episode
offline backtest: the simulator produces complete historical episodes, so there's no
need to model live/streaming incremental state for the prototype (plan Scope).

EMERGING -> SIGNIFICANT -> STRUCTURAL is driven by one counter: how many consecutive
days a KPI has stayed relevant. The exact day-counts are prototype knobs, not
empirically calibrated (design doc §14: "the exact policies can later be calibrated";
plan Risk #4) -- PELT/CUSUM/Bayesian changepoint detection are deliberately not used
here (§16.3, §19: "later, if the prototype demonstrates the need").
"""

DEFAULT_MIN_DAYS_FOR_SIGNIFICANT = 3
DEFAULT_MIN_DAYS_FOR_STRUCTURAL = 10


def classify_trajectory(
    day_offsets,
    is_relevant_sequence,
    min_days_for_significant=DEFAULT_MIN_DAYS_FOR_SIGNIFICANT,
    min_days_for_structural=DEFAULT_MIN_DAYS_FOR_STRUCTURAL,
):
    """day_offsets and is_relevant_sequence: parallel sequences, ordered by day.
    Returns [(day_offset, state, evidence_list), ...]."""
    results = []
    relevant_run = 0
    for day_offset, relevant in zip(day_offsets, is_relevant_sequence):
        if not relevant:
            relevant_run = 0
            results.append((day_offset, "NORMAL", []))
            continue

        relevant_run += 1
        if relevant_run >= min_days_for_structural:
            state = "STRUCTURAL"
            evidence = ["SUSTAINED_BEHAVIOR_SHIFT", "PERSISTENT_BEHAVIOR_SHIFT",
                        f"RELEVANT_FOR_{relevant_run}_CONSECUTIVE_DAYS"]
        elif relevant_run >= min_days_for_significant:
            state = "SIGNIFICANT"
            evidence = ["PERSISTENT_UNUSUAL_MOVEMENT", f"RELEVANT_FOR_{relevant_run}_CONSECUTIVE_DAYS"]
        else:
            state = "EMERGING"
            evidence = ["EARLY_UNUSUAL_MOVEMENT", f"RELEVANT_FOR_{relevant_run}_CONSECUTIVE_DAYS"]
        results.append((day_offset, state, evidence))
    return results
