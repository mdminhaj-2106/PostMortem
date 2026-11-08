"""Declared config -- plain module-level constants, same pattern as Stage 4's
dimension_config.py. See docs/02-stage-design-reports/stage5b-confounded-cause-decomposer-revised.md.
"""

# The real 4 injectable causes (pipeline/simulator/layer1_ground_truth/generate.py's
# EVENT_TYPES). Must equal that list exactly -- test_stage5b.py asserts this so the
# label space can't silently drift if the simulator ever changes.
CAUSE_FAMILIES = ("product_outage", "marketing_cut", "competitor_launch", "inventory_shortage")

SEASONAL = "seasonal"
UNEXPLAINED = "unexplained"

# generate.py's _sample_reactive_marketing_cut: start = trigger.start + rng.integers(3, 10).
# A product_outage -> marketing_cut pair whose onsets fall inside this lag is the SAME
# causal chain (one caused the other), not two independent contributors -- merge by
# declaration, never fit NNLS between them (Stage 3 design report §6's shared-node rule).
DEPENDENT_PAIRS = {("product_outage", "marketing_cut"): (3, 10)}

# Candidate causes below this floor in Stage 5a's cause_scores are dropped before fitting.
PROBABILITY_FLOOR = 0.05

# Empirical separability gate (identifiability.py): |cosine(basis_a, basis_b)| above this
# merges the pair into one joint component -- collinear bases can't be told apart by NNLS.
COSINE_MERGE_THRESHOLD = 0.95

# Basis-learning window length (days) and shape-vector slice-profile size (top-K slices).
BASIS_WINDOW_DAYS = 14
TOP_K_SLICES = 5
