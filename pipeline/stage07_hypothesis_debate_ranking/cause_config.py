"""Declared config -- plain module-level constants, same pattern as Stage 5b's
cause_config.py. See .claude/plans/stage7-hypothesis-debate-ranking.md.
"""

CANDIDATE_PROBABILITY_FLOOR = 0.05

# A BORROWED hypothesis (Stage 5c) can never resolve above this bucket without
# independent native (Stage 6) evidence -- design doc §12/§30.
BORROWED_MAX_BUCKET = "POSSIBLE"

# relevance_score bucket edges, calibrated against Stage 6's own live episode-15
# run (stage06_evidence_retrieval/README.md: real evidence scored 0.39-0.55,
# decoys 0.05-0.33, retrieval floor 0.35 -- nothing reaches Stage 6 below that).
# Re-confirmed against this stage's own live run in test_stage7.py.
STRENGTH_STRONG_FLOOR = 0.45
STRENGTH_MODERATE_FLOOR = 0.35

# Support-level thresholds against stage5a_probability / stage5b_share.
HIGH_CLASSIFIER_SUPPORT_FLOOR = 0.5
HIGH_CONTRIBUTION_SHARE_FLOOR = 0.5

# Same declared relationship Stage 5b's identifiability.py already consumes
# (pipeline/stage05b_confounded_cause_decomposer/cause_config.py) -- Stage 7 only
# reads it to explain a joint hypothesis's structural plausibility, never to build
# a new compound from it (plan finding #6 -- that would double-count the same
# relationship Stage 5b already used to produce the joint bucket in the first
# place). test_stage7.py asserts this stays equal to 5b's own copy.
DEPENDENT_PAIRS = {("product_outage", "marketing_cut"): (3, 10)}
