"""Identity Resolution Graph (design doc §3.3, Scenario 6) -- the one genuinely new
cross-cutting component from Stage 1's design. Full Fellegi-Sunter scoring needs
multiple imperfect identifying fields (email, phone, billing ID, ...); Layer 2 only
gives us one (crm_account_id vs customer_id) -- a documented hackathon-scale limitation
(design doc §8, plan Risk #2), not an oversight.

With a single field, agreement/disagreement is the whole signal: there's no second
field to separate "this mismatch is a stray duplicate account" from "this mismatch is a
wrong-customer near-miss," so any disagreement lands in the ambiguous zone rather than
being guessed either direction -- under-merging is the documented safer default (an
over-merge silently contaminates evidence indistinguishably from a correct match).
"""

# "auto_reject" used to be declared here and was unreachable: score_match can only
# return two of the three (audit finding F4). Rejecting a match outright requires
# positive evidence that two records are DIFFERENT people, which needs a second
# identifying field to disagree on -- with one field, disagreement is exactly the
# ambiguous case. Declaring a zone the code cannot produce overstates the machinery.
ZONES = ("auto_merge", "ambiguous")


def score_match(customer_id, crm_account_id):
    if crm_account_id == customer_id:
        return "auto_merge"
    return "ambiguous"


def resolve_customer_identities(cur, episode_id):
    cur.execute(
        "SELECT customer_id, crm_account_id FROM v_crm_customer_mapping WHERE episode_id=%s",
        (episode_id,),
    )
    return [
        {"customer_id": customer_id, "crm_account_id": crm_account_id, "zone": score_match(customer_id, crm_account_id)}
        for customer_id, crm_account_id in cur.fetchall()
    ]


def summarize(cur, episode_id):
    """Episode-level identity-quality report: how much of crm's account mapping cannot
    be resolved to a billing customer with confidence (audit finding F4).

    This deliberately does NOT adjust any KPI's confidence. Verified against the schema:
    `crm_account_id` appears in no view except v_crm_customer_mapping itself --
    v_crm_weekly_active_customers counts DISTINCT customer_id straight off orders and
    support_tickets, never joining through the mapping. So identity ambiguity cannot
    corrupt a KPI value in this dataset, and wiring it into confidence would assert a
    dependency that does not exist. It is reported as a data-quality signal about the
    join surface, which is what it honestly is.

    Report it, say on camera that nothing downstream joins through it yet, and that the
    hook is where a real second identifying field would plug in.
    """
    resolutions = resolve_customer_identities(cur, episode_id)
    counts = {zone: 0 for zone in ZONES}
    for r in resolutions:
        counts[r["zone"]] += 1
    total = len(resolutions)
    return {
        "episode_id": episode_id,
        "total_mappings": total,
        "counts": counts,
        "ambiguous_rate": counts["ambiguous"] / total if total else 0.0,
    }
