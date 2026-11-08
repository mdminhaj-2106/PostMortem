"""Step 11 (design doc §28, §54): ABSTAIN when nothing defensible survives. Ranked
candidates are still emitted regardless (design doc's explicit requirement) --
this only sets a flag, never truncates the hypothesis list.
"""


def determine_abstention(ranked_hypotheses):
    if not ranked_hypotheses:
        return True, ["NO_DEFENSIBLE_HYPOTHESIS"]
    if all(rh.confidence_bucket == "UNKNOWN" for rh in ranked_hypotheses):
        return True, ["NO_DEFENSIBLE_HYPOTHESIS"]

    top_rank = ranked_hypotheses[0].rank
    top_bucket = ranked_hypotheses[0].confidence_bucket
    tied_at_top = [rh for rh in ranked_hypotheses if rh.rank == top_rank]
    # A tie at the top is only fatal when the leading tier itself is weak
    # (POSSIBLE) -- two tied KNOWN/LIKELY hypotheses are still a defensible,
    # informative result (design doc §54's "two candidates tied... potentially
    # abstain", not "always").
    if top_bucket == "POSSIBLE" and len(tied_at_top) > 1:
        return True, ["UNRESOLVED_TIE_AT_TOP"]

    return False, []
