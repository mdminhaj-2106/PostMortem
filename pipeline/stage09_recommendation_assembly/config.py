"""Declared config -- plain module-level dicts, same pattern as every other
stage's config.py/cause_config.py (not the design doc's YAML files -- no other
stage in this repo loads YAML config). See
.claude/plans/stage9-recommendation-assembly.md.

One declared lever per mechanism (plan finding #5/#8) -- Stage 3's real KPI DAG
is a single 2-KPI edge, nothing to structurally filter multiple levers against,
and this project's real 4-cause vocabulary doesn't need branching generality yet.
"""

# The real 4 injectable causes (pipeline/simulator/layer1_ground_truth/generate.py's
# EVENT_TYPES), same closed vocabulary stage05a/stage05b/stage07 already declare.
CAUSE_MECHANISMS = {
    "product_outage": "reliability_degradation",
    "marketing_cut": "reduced_acquisition",
    "competitor_launch": "competitive_pressure",
    "inventory_shortage": "product_unavailability",
}

# "seasonal" can appear as a joint hypothesis member (Stage 5b's basis includes it
# alongside the 4 real causes -- stage07's own README, correction #5, confirms a
# live FULLY_MERGED bucket containing all 5). It is not a business lever: nothing
# a company can "fix" the way it can repair an outage or restock inventory. No
# mechanism/lever/action/owner is resolved for it -- it stays in `driver` for
# provenance but contributes nothing else to the built action.
NON_ACTIONABLE_CAUSES = ("seasonal",)

MECHANISM_LEVERS = {
    "reliability_degradation": "restore_reliability",
    "reduced_acquisition": "restore_marketing_spend",
    "competitive_pressure": "investigate_competitor_activity",
    "product_unavailability": "replenish_inventory",
}

# {lever: (atomic_action, default_owner, risk_tier)}. Owner/risk_tier are real
# declared domain knowledge, not verified against an org chart -- a one-line
# config edit if a teammate objects to the specific team names (plan Risk #3).
LEVER_ACTIONS = {
    "restore_reliability": ("REPAIR", "engineering", "LOW_REGRET"),
    "restore_marketing_spend": ("INCREASE", "marketing", "HIGH_COMMITMENT"),
    "investigate_competitor_activity": ("INVESTIGATE", "marketing", "LOW_REGRET"),
    "replenish_inventory": ("REPLENISH", "supply_chain", "LOW_REGRET"),
}

# Design doc §38-42. Starts empty: none of the 4 real causes' default actions
# oppose each other (repair reliability / restore marketing spend / investigate
# competitor / replenish inventory are naturally compatible) -- stated plainly
# rather than populated with unused hypothetical pairs (plan finding #8). The
# compatibility check itself is still real, see compatibility.py.
ACTION_COMPATIBILITY_CONFLICTS = {}

# Company capability -- stubbed AVAILABLE for every declared owner team (plan
# finding #4: no company-capability service exists anywhere in this repo).
CAPABILITY_AVAILABLE = {"engineering": True, "marketing": True, "supply_chain": True}

# Design doc §69's decision matrix, collapsed to what's real (plan step 7).
CONFIDENCE_POLICY = {
    "KNOWN": "ACT",
    "LIKELY": "ACT",
    "POSSIBLE": None,  # resolved by risk_tier -- see intent_resolver.py
    "UNKNOWN": "INVESTIGATE",
}
