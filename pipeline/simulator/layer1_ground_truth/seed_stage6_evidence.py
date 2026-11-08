"""Seeds a real-text support_tickets demo corpus (design doc §3, plan step 2) for one
demo episode+cluster Stage 5a has already found and verified live: episode 15,
cluster_15_93_94 (window day 93-94), a real inventory_shortage event (day 78-109,
severe, step onset, product_id 42 = category 'auto', no affected_segment) whose
`auto` share of |deviation_pct| clears the product-concentration bar cleanly (see
pipeline/stage05a_fingerprint_classification/test_stage5a.py's
test_run_stage5a_detects_inventory_shortage_on_a_real_episode). Reused rather than
re-derived -- this is the one real (kpi, dimension) fingerprint this project's
generator actually produces (only inventory_shortage ever touches `product`; segment
concentration was checked live for this same cluster and does not clear the bar,
since this event's affected_segment is unset -- verified, not assumed).

Only `product` is a real flagged facet here, so this corpus is scoped around it:
customers who ordered category 'auto' this episode (real evidence + same-customer-
unrelated-topic decoys) vs. customers who never did (wrong-scope decoys) vs. a
uniformly random background slice. With only 2 product categories in this episode
(`auto`/`bed_bath_table`, ~42%/58% of all customers), Filter 1 (entity_scope_filter)
narrows less dramatically than a many-category dimension would -- an honest property
of this specific episode's real data, not a scripting shortcut; Filter 3 (semantic
relevance) is what actually isolates the real evidence, and does so here.

This script is fixture construction, not pipeline logic: it reads injected_events
and the episode's real order history to build a realistic corpus. run_stage6.py and
every other Stage 6 module never queries injected_events (plan Risk #3).

Usage:
    python seed_stage6_evidence.py --episode-id 15
"""

import argparse
import os
import random

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

_SEED = 6  # deterministic corpus across reruns
_PAGE_SIZE = 500  # CONSTITUTION.md: never execute_values' silent page_size=100 default

WINDOW_START_DAY_OFFSET = 93  # cluster_15_93_94 -- see module docstring

N_BACKGROUND = 150
N_DECOY_WRONG_PRODUCT = 20
N_DECOY_SAME_CUSTOMER_UNRELATED = 15
N_REAL_EVIDENCE = 3

_BACKGROUND_TEXT = [
    ("bug", "The app took a while to load this morning, but it recovered fine."),
    ("shipping", "My order arrived a day later than the estimate, no big deal."),
    ("billing", "Could you clarify the tax line on my last invoice?"),
    ("other", "Loving the new checkout flow, much faster than before!"),
    ("other", "Any plans to add a dark mode to the mobile app?"),
    ("billing", "I was charged twice for one order, please refund the duplicate."),
    ("shipping", "Package tracking hasn't updated in two days."),
    ("bug", "Search results look a bit off for some queries."),
    ("other", "Great customer service on my last call, thank you!"),
    ("shipping", "Can I change my delivery address after placing an order?"),
]

# Wrong scope: similar-sounding stock complaints, but about the OTHER category --
# proves the product filter is doing real work, not semantic ranking alone.
_WRONG_PRODUCT_TEXT = [
    "The bath towels I wanted are sold out everywhere, so frustrating.",
    "My favorite shower curtain set is backordered with no ETA.",
    "Tried to reorder our bedding set three times, always out of stock.",
]

# Same (auto-buying) customers, unrelated topic -- proves semantic ranking is doing
# real work, not "right customer = assume relevant."
_UNRELATED_SAME_CUSTOMER_TEXT = [
    ("billing", "Quick question about my last statement, the total looks off."),
    ("shipping", "When will my last package ship? It's been a few days."),
    ("other", "Is there a loyalty program for frequent shoppers?"),
]

# Real evidence: genuine inventory_shortage complaints, auto-category, before the window.
_REAL_EVIDENCE_TEXT = [
    "I've been trying to reorder my usual auto accessories for two weeks, everything shows out of stock.",
    "The car phone mount I wanted got cancelled -- apparently no stock available anywhere.",
    "Auto parts I need are all backordered indefinitely, no ETA given by support.",
]


def _fetch_customer_pools(cur, episode_id):
    cur.execute(
        "SELECT DISTINCT o.customer_id FROM orders o JOIN products p ON p.product_id = o.product_id "
        "WHERE o.episode_id=%s AND p.category='auto'",
        (episode_id,),
    )
    auto_buyers = [row[0] for row in cur.fetchall()]

    cur.execute(
        "SELECT DISTINCT o.customer_id FROM orders o JOIN products p ON p.product_id = o.product_id "
        "WHERE o.episode_id=%s AND p.category != 'auto' AND o.customer_id NOT IN ("
        "  SELECT o2.customer_id FROM orders o2 JOIN products p2 ON p2.product_id = o2.product_id "
        "  WHERE o2.episode_id=%s AND p2.category='auto'"
        ")",
        (episode_id, episode_id),
    )
    non_auto_buyers = [row[0] for row in cur.fetchall()]

    cur.execute("SELECT customer_id FROM customers WHERE episode_id=%s", (episode_id,))
    all_customers = [row[0] for row in cur.fetchall()]

    return auto_buyers, non_auto_buyers, all_customers


def _build_rows(episode_id, n_days, auto_buyers, non_auto_buyers, all_customers, rng):
    rows = []  # (episode_id, day_offset, customer_id, category, text)

    for _ in range(N_BACKGROUND):
        category, text = rng.choice(_BACKGROUND_TEXT)
        rows.append((episode_id, rng.randint(0, n_days - 1), rng.choice(all_customers), category, text))

    for i in range(N_DECOY_WRONG_PRODUCT):
        text = _WRONG_PRODUCT_TEXT[i % len(_WRONG_PRODUCT_TEXT)]
        day_offset = rng.randint(WINDOW_START_DAY_OFFSET - 20, WINDOW_START_DAY_OFFSET + 1)
        rows.append((episode_id, day_offset, rng.choice(non_auto_buyers), "shipping", text))

    for i in range(N_DECOY_SAME_CUSTOMER_UNRELATED):
        category, text = _UNRELATED_SAME_CUSTOMER_TEXT[i % len(_UNRELATED_SAME_CUSTOMER_TEXT)]
        day_offset = rng.randint(WINDOW_START_DAY_OFFSET - 30, WINDOW_START_DAY_OFFSET - 1)
        rows.append((episode_id, day_offset, rng.choice(auto_buyers), category, text))

    for i in range(N_REAL_EVIDENCE):
        text = _REAL_EVIDENCE_TEXT[i % len(_REAL_EVIDENCE_TEXT)]
        day_offset = rng.randint(WINDOW_START_DAY_OFFSET - 18, WINDOW_START_DAY_OFFSET - 1)
        rows.append((episode_id, day_offset, rng.choice(auto_buyers), "shipping", text))

    return rows


def seed(cur, episode_id):
    cur.execute("SELECT n_days FROM episodes WHERE episode_id=%s", (episode_id,))
    row = cur.fetchone()
    if row is None:
        raise SystemExit(f"episode {episode_id} does not exist")
    n_days = row[0]

    auto_buyers, non_auto_buyers, all_customers = _fetch_customer_pools(cur, episode_id)
    if not auto_buyers or not non_auto_buyers:
        raise SystemExit(f"episode {episode_id} lacks both an 'auto' and a non-'auto' buyer pool")

    rng = random.Random(_SEED)
    rows = _build_rows(episode_id, n_days, auto_buyers, non_auto_buyers, all_customers, rng)

    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO support_tickets (episode_id, day_offset, customer_id, category, text) VALUES %s",
        rows,
        page_size=_PAGE_SIZE,
    )
    print(f"seeded {len(rows)} tickets for episode {episode_id}: "
          f"background={N_BACKGROUND} decoy_wrong_product={N_DECOY_WRONG_PRODUCT} "
          f"decoy_same_customer_unrelated={N_DECOY_SAME_CUSTOMER_UNRELATED} real_evidence={N_REAL_EVIDENCE}")


def main():
    parser = argparse.ArgumentParser(description="Seed Stage 6's demo evidence corpus.")
    parser.add_argument("--episode-id", type=int, default=15)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            seed(cur, args.episode_id)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
