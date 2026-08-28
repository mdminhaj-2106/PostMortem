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

ZONES = ("auto_merge", "auto_reject", "ambiguous")


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
