"""Scores one completed run's Stage 7 hypotheses against that episode's held-out
injected_events -- the only place in the whole system allowed to query that table,
and only after a run is already complete (CONSTITUTION.md non-negotiable: the running
pipeline itself never sees it). See
.claude/plans/api-backend-orchestration-and-verification.md.

The day-range-overlap matching logic (_overlap_days/_match_event/_fetch_events) is
copied, not imported, from
pipeline/stage05a_fingerprint_classification/eval_against_ground_truth.py. That file's
own top-level imports (stage3_bridge, stage4_bridge, stage5a) would drag in a second,
redundant Stage 3/4/5a bridge chain if imported directly here -- this run already has
those results in hand. The three functions below are a deliberate, small, stated copy
of that file's real logic, not a re-derivation -- keep them in sync if that file's
matching rule ever changes.

counterfactual_mae is deliberately None in this slice: no code anywhere in this repo
re-derives Layer 1's true counterfactual with an injected event suppressed (design
report's stated new-math gap) -- returning a fabricated number here would violate the
same "never invent" discipline Stage 10/11's fact sheet already enforces.
"""

_PERSISTING_EVENT_HORIZON = 9999  # end_day_offset is None for an event that never recovers


def _overlap_days(a_start, a_end, b_start, b_end):
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def _fetch_events(cur, episode_id):
    cur.execute(
        "SELECT event_type, start_day_offset, end_day_offset FROM injected_events WHERE episode_id=%s",
        (episode_id,),
    )
    return [
        (event_type, start, end if end is not None else start + _PERSISTING_EVENT_HORIZON)
        for event_type, start, end in cur.fetchall()
    ]


def _match_event(window_start, window_end, events):
    """The injected event whose day range overlaps this window the most -- None if no
    real event ever touched this window (a legitimate false-causality-rate signal, not
    an error)."""
    best_type, best_overlap = None, 0
    for event_type, e_start, e_end in events:
        ov = _overlap_days(window_start, window_end, e_start, e_end)
        if ov > best_overlap:
            best_type, best_overlap = event_type, ov
    return best_type


def score_run(cur, episode_id, stage3_result, stage7_result):
    """top1_hit/top3_hit are None (not False) when there's nothing to score --
    stage7 abstained, or no real event ever overlapped this window (a legitimate
    'no story here' outcome, same as eval_against_ground_truth.py's own
    `if true_type is None: continue`)."""
    events = _fetch_events(cur, episode_id)
    matched_event_type = _match_event(
        stage3_result.window_start_day_offset, stage3_result.window_end_day_offset, events
    )

    top1_hit = top3_hit = None
    if matched_event_type is not None and not stage7_result.abstained and stage7_result.hypotheses:
        ranked = sorted(stage7_result.hypotheses, key=lambda h: h.rank if h.rank is not None else 999)
        top1_hit = matched_event_type in ranked[0].member_causes
        top3_hit = any(matched_event_type in h.member_causes for h in ranked[:3])

    return {
        "matched_event_type": matched_event_type,
        "top1_hit": top1_hit,
        "top3_hit": top3_hit,
        "counterfactual_mae": None,
    }
