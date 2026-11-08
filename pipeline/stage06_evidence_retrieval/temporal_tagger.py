"""Step 2 (design doc §6): BEFORE/DURING/AFTER vs window_start_day_offset. A single
int day_offset comparison -- support_tickets.day_offset and Stage 4's
window_start/end_day_offset already live in the same day-offset space, so no date
lookup or Calendar Dimension is needed here (unlike a real ISO changepoint_date --
plan header's correction #3).

Same-day boundary (plan step 5, design doc §12.1): a ticket dated exactly on
window_start_day_offset is DURING, not BEFORE -- declared explicitly, not left
ambiguous.
"""

TEMPORAL_TAGS = ("BEFORE", "DURING", "AFTER")


def tag(day_offset, window_start_day_offset, window_end_day_offset):
    """None day_offset (a corrupted/missing timestamp) returns None -- caller excludes
    it from temporal tagging with a logged reason, never silently defaults to BEFORE
    (plan step 9 / design doc §12.3)."""
    if day_offset is None:
        return None
    if day_offset < window_start_day_offset:
        return "BEFORE"
    if day_offset <= window_end_day_offset:
        return "DURING"
    return "AFTER"
