"""Broad Candidate Selection (design doc §8). Percentile-threshold strategy --
recall-oriented on purpose, "candidate" doesn't mean "significant," just "unusual
enough to investigate further." target_candidate_rate is the one knob (design
doc's recommended `candidate_selection.strategy: percentile` interface).
"""

# Empirically calibrated against real injected events (episode 137's clean, isolated
# marketing_cut -- no overlapping volatility regime), not picked arbitrarily: daily
# revenue/active_customers in this simulator (small per-episode customer counts,
# Poisson order counts) is noisy enough day-to-day that 0.15 combined with
# classification.py's 3-consecutive-day persistence rule essentially never fires,
# even for a genuine ~50% sustained revenue drop -- too many single-day noise dips
# break the streak before it can accumulate. 0.30 is the rate that reliably lets a
# real sustained shift register. See test_stage2.py's live scoring check.
DEFAULT_TARGET_CANDIDATE_RATE = 0.30


def select_candidates(unusualness_scores, target_candidate_rate=DEFAULT_TARGET_CANDIDATE_RATE):
    """unusualness_scores: [(day_offset, score_or_None), ...]. Returns the set of
    day_offsets whose score is at or above the (1 - target_candidate_rate) quantile
    of the available scores."""
    scored = sorted(s for _, s in unusualness_scores if s is not None)
    if not scored:
        return set()
    cutoff_idx = max(0, int(len(scored) * (1 - target_candidate_rate)) - 1)
    threshold = scored[cutoff_idx]
    return {day_offset for day_offset, s in unusualness_scores if s is not None and s >= threshold}
