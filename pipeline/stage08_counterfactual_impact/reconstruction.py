"""Step: per-day counterfactual trajectory. See
.claude/plans/stage8-counterfactual-impact-engine.md's central finding -- the only
validated quantitative mechanism in this codebase is Stage 5b's fitted contribution
share, applied against Stage 1/2's real baseline (never a per-cause mechanism class
re-simulating Layer 1 internals, which nothing downstream of Layer 2 may query).

counterfactual = observed - share * residual, where residual = observed - expected.
Removing `share`'s fraction of the shortfall/excess is sign-correct for both up-
and down-deviations without assuming "higher is better" -- direction is read off
the residual's own sign; impact.py separately labels the KPI's own orientation.

reconstruct_points is a pure function, no DB access -- directly unit-testable on a
small fixture (design doc §59-61's own unit tests, adapted to this reconstruction
instead of a mechanism class).
"""


def _is_intervened(day_offset, mode, intervention_day_offset):
    if mode == "EVENT_NEVER_OCCURRED":
        return True
    if mode == "REMOVE_FROM_TIME":
        return day_offset >= intervention_day_offset
    raise ValueError(f"unknown mode: {mode!r}")


def reconstruct_points(observed_by_day, expected_by_day, window_start, window_end, share, mode,
                        intervention_day_offset=None):
    """[{day_offset, observed_value, baseline_value, counterfactual_value,
    estimated_impact}, ...] for day_offset in [window_start, window_end]. A day
    with no observed value or no baseline (insufficient trailing history) gets
    counterfactual_value=None -- never fabricated, per the same "measured or not"
    discipline Stage 4's SliceResult already uses."""
    points = []
    for day_offset in range(window_start, window_end + 1):
        observed = observed_by_day.get(day_offset)
        expected = expected_by_day.get(day_offset)

        if observed is None or expected is None:
            points.append({
                "day_offset": day_offset, "observed_value": observed, "baseline_value": expected,
                "counterfactual_value": None, "estimated_impact": None,
            })
            continue

        residual = observed - expected
        intervened = _is_intervened(day_offset, mode, intervention_day_offset)
        counterfactual = observed - share * residual if intervened else observed
        points.append({
            "day_offset": day_offset, "observed_value": observed, "baseline_value": expected,
            "counterfactual_value": counterfactual, "estimated_impact": counterfactual - observed,
        })
    return points
