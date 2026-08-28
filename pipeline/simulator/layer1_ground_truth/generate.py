"""Layer 1 ground-truth generator.

Fills the 7-table Postgres schema (schema.sql) with simulated episodes: real-data
-grounded (Olist-bootstrapped) customers/products/seasonality, driven day-by-day
through the structural equations, with 0-N injected causal events per episode
(including reactive chaining and volatility regimes). See the design doc:
docs/02-stage-design-reports/simulator-layer1-ground-truth-design.md

Usage:
    python generate.py --n-episodes 400 --n-days 120 --seed 42 [--reset]
"""

import argparse
import os
from datetime import date, timedelta

import numpy as np
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from bootstrap import load_olist_stats, sample_region, sample_product, seasonality_factor, reliability_noise_std

# --- knobs (design doc §4 / §1.2-1.3 — tune once the classifiers are training against this) ---
BASE_MARKETING_SPEND = 5000.0
BASE_TRAFFIC_PER_SPEND = 0.4
BASE_CONVERSION_RATE = 0.03
BASE_COMPETITOR_ACTIVITY = 0.1
BASE_CHURN_RATE = 0.01
# Real Olist customers average ~1.03 orders each -- one-time-buyer-dominated. Most orders
# here go to a brand-new customer instead of reusing the same active pool over and over,
# so the RFM segment split (New/Returning/VIP) reflects genuine repeat behavior instead of
# an artifact of always sampling from a small pool. Not a literal match to Olist's lifetime
# 1.03 (that's a multi-year marketplace average) -- a directional correction, still a knob.
REPEAT_PURCHASE_PROB = 0.25
# churn is scoped to customers who've already shown repeat behavior (Returning/VIP) --
# a one-time buyer who doesn't return isn't "churn" in any meaningful sense for e-commerce,
# it's just the base rate of e-commerce being mostly one-and-done. See design doc discussion.
CHURN_ELIGIBLE_SEGMENTS = ("Returning", "VIP")

EVENT_TYPES = ["product_outage", "marketing_cut", "competitor_launch", "inventory_shortage"]
SEVERITY_WEIGHTS = {"minor": 0.3, "moderate": 0.5, "severe": 0.2}
SEVERITY_MAGNITUDE = {"minor": (0.05, 0.15), "moderate": (0.15, 0.35), "severe": (0.35, 0.65)}
TYPICAL_ONSET = {
    "marketing_cut": "step",
    "product_outage": "ramp",
    "competitor_launch": "ramp",
    "inventory_shortage": "step",
}
ONSET_TYPES = ["step", "ramp", "spike_decay", "delayed"]
EVENT_COUNT_WEIGHTS = {0: 0.35, 1: 0.40, 2: 0.20, 3: 0.05}

RAMP_DAYS = 10
DELAY_DAYS = 7
DECAY_HALF_LIFE = 10


# --- event effect curve (design doc §1.3, §3) ---

def effect_fraction(day_offset, event):
    """Fraction (0..1) of an event's full magnitude active on a given day."""
    if day_offset < event["start_day_offset"]:
        return 0.0
    t = day_offset - event["start_day_offset"]
    onset = event["onset_type"]
    if onset == "step":
        base = 1.0
    elif onset == "ramp":
        base = min(1.0, t / RAMP_DAYS)
    elif onset == "delayed":
        base = 0.0 if t < DELAY_DAYS else min(1.0, (t - DELAY_DAYS) / RAMP_DAYS)
    elif onset == "spike_decay":
        base = 0.5 ** (t / DECAY_HALF_LIFE)
    else:
        base = 1.0

    mitigation_day = event["mitigation_day_offset"]
    end = event["end_day_offset"]
    if mitigation_day is not None and day_offset >= mitigation_day:
        floor = 1.0 - (event["mitigation_completeness"] or 0.0)
        progress = min(1.0, (day_offset - mitigation_day) / RAMP_DAYS)
        base = base * (1 - progress) + base * floor * progress
    elif end is not None and day_offset >= end:
        progress = min(1.0, (day_offset - end) / RAMP_DAYS)
        base = base * (1 - progress)

    return max(0.0, base)


# --- event sampling (design doc §1.2, §1.3) ---

def _sample_onset(rng, event_type):
    typical = TYPICAL_ONSET[event_type]
    weights = np.array([0.55 if o == typical else 0.15 for o in ONSET_TYPES])
    return str(rng.choice(ONSET_TYPES, p=weights / weights.sum()))


def _sample_one_event(rng, n_days, n_products):
    event_type = str(rng.choice(EVENT_TYPES))
    severity = str(rng.choice(list(SEVERITY_WEIGHTS), p=list(SEVERITY_WEIGHTS.values())))
    lo, hi = SEVERITY_MAGNITUDE[severity]
    magnitude = float(rng.uniform(lo, hi))
    onset_type = _sample_onset(rng, event_type)
    start = int(rng.integers(15, max(16, n_days - 30)))
    persists = event_type == "marketing_cut" and rng.random() < 0.5
    duration = int(rng.integers(10, 40))
    end = None if persists else min(n_days, start + duration)
    mitigation_day, mitigation_completeness = None, None
    if end is not None and rng.random() < 0.6:
        mitigation_day = min(end, start + int(rng.integers(5, duration + 1)))
        mitigation_completeness = float(rng.uniform(0.5, 1.0))
    affected_segment, segment_multiplier = None, 1.0
    if rng.random() < 0.4:
        affected_segment = str(rng.choice(["New", "Returning", "VIP"]))
        segment_multiplier = float(rng.uniform(1.5, 4.0))
    affected_product_idx = int(rng.integers(0, n_products)) if event_type == "inventory_shortage" else None
    return {
        "event_type": event_type, "severity": severity, "onset_type": onset_type,
        "start_day_offset": start, "end_day_offset": end,
        "mitigation_day_offset": mitigation_day, "mitigation_completeness": mitigation_completeness,
        "magnitude": magnitude, "segment_multiplier": segment_multiplier,
        "affected_segment": affected_segment, "affected_product_idx": affected_product_idx,
        "triggered_by_idx": None,
        "description": f"{severity} {event_type}, {onset_type} onset, starting day {start}",
    }


def _sample_reactive_marketing_cut(rng, trigger_event, n_days, triggered_by_idx):
    # design doc §1.2: outage -> panic pause on ad spend while the team firefights.
    # Only chaining implemented into an existing event_type (schema has no "pricing_change" type).
    start = min(n_days - 5, trigger_event["start_day_offset"] + int(rng.integers(3, 10)))
    magnitude = float(rng.uniform(*SEVERITY_MAGNITUDE["minor"]))
    return {
        "event_type": "marketing_cut", "severity": "minor", "onset_type": "step",
        "start_day_offset": start, "end_day_offset": None,
        "mitigation_day_offset": None, "mitigation_completeness": None,
        "magnitude": magnitude, "segment_multiplier": 1.0,
        "affected_segment": None, "affected_product_idx": None,
        "triggered_by_idx": triggered_by_idx,
        "description": f"reactive marketing pullback following the outage starting day {trigger_event['start_day_offset']}",
    }


def sample_events(rng, n_days, n_products):
    counts, weights = zip(*EVENT_COUNT_WEIGHTS.items())
    n_events = int(rng.choice(counts, p=weights))
    events = [_sample_one_event(rng, n_days, n_products) for _ in range(n_events)]
    chained = [
        _sample_reactive_marketing_cut(rng, ev, n_days, i)
        for i, ev in enumerate(events)
        if ev["event_type"] == "product_outage" and rng.random() < 0.6
    ]
    events.extend(chained)
    return events


def gen_volatility_series(rng, n_days, block_len=21):
    values = []
    day = 0
    while day < n_days:
        mult = float(rng.choice([1.0, 2.0, 3.0], p=[0.7, 0.2, 0.1]))
        length = min(block_len, n_days - day)
        values.extend([mult] * length)
        day += length
    return values[:n_days]


# --- episode generation (design doc §3, §3a) ---

# segment is an RFM-style value tier, not company size — Olist customers are individual
# consumers, so it's computed from actual order behavior, not assigned as a fixed label.
SEGMENT_VIP_SPEND = 500.0
SEGMENT_RETURNING_ORDERS = 2
# day-0 pool represents customers with pre-episode history we can't observe directly, so
# their starting tier is declared from a realistic prior instead of computed from nothing.
INITIAL_SEGMENT_PRIORS = {"New": 0.40, "Returning": 0.45, "VIP": 0.15}
INITIAL_SEED_STATS = {"New": (0, 0.0), "Returning": (2, 150.0), "VIP": (4, 650.0)}


def _customer_segment(n_orders, total_spend):
    # VIP requires both repeat orders and high spend -- a single big-ticket cart
    # shouldn't count as "VIP" on its own, that's not sustained engagement.
    if n_orders >= SEGMENT_RETURNING_ORDERS and total_spend >= SEGMENT_VIP_SPEND:
        return "VIP"
    if n_orders >= SEGMENT_RETURNING_ORDERS:
        return "Returning"
    return "New"


def _new_customer(rng, stats, initial=False):
    if initial:
        prior = str(rng.choice(list(INITIAL_SEGMENT_PRIORS), p=list(INITIAL_SEGMENT_PRIORS.values())))
        n_orders, total_spend = INITIAL_SEED_STATS[prior]
    else:
        n_orders, total_spend = 0, 0.0
    return {
        "segment": _customer_segment(n_orders, total_spend),
        "region": str(sample_region(rng, stats)),
        "signup_day_offset": None,  # set by caller
        "churned_day_offset": None,
        "n_orders": n_orders,      # generation-time scratch state, not persisted (see schema §4)
        "total_spend": total_spend,
    }


def generate_episode(rng, seed, n_days, start_date, stats, n_customers_initial, n_products):
    reliability_noise = reliability_noise_std(stats)

    customers = []
    for _ in range(n_customers_initial):
        c = _new_customer(rng, stats, initial=True)
        c["signup_day_offset"] = 0
        customers.append(c)

    products = []
    for _ in range(n_products):
        cat, cost, price = sample_product(rng, stats)
        products.append({"category": cat, "unit_cost": cost, "base_price": price})

    events = sample_events(rng, n_days, n_products)
    volatility = gen_volatility_series(rng, n_days)

    daily_state_rows, order_rows, ticket_rows = [], [], []
    satisfaction = 0.9  # EMA, persists across days -> what gives product_outage its delayed churn ramp

    for day in range(n_days):
        current_date = start_date + timedelta(days=day)
        vol = volatility[day]
        season = seasonality_factor(stats, current_date)

        mc_frac = sum(e["magnitude"] * effect_fraction(day, e) for e in events if e["event_type"] == "marketing_cut")
        marketing_spend = max(0.0, BASE_MARKETING_SPEND * (1 - min(0.95, mc_frac)) * (1 + rng.normal(0, 0.05) * vol))

        po_frac = sum(e["magnitude"] * effect_fraction(day, e) for e in events if e["event_type"] == "product_outage")
        reliability = max(0.05, 1.0 * (1 - min(0.95, po_frac)) + rng.normal(0, reliability_noise) * vol)

        cl_frac = sum(e["magnitude"] * effect_fraction(day, e) for e in events if e["event_type"] == "competitor_launch")
        competitor_activity = max(0.0, BASE_COMPETITOR_ACTIVITY * (1 + cl_frac) + rng.normal(0, 0.02) * vol)

        traffic = max(0.0, BASE_TRAFFIC_PER_SPEND * marketing_spend * season * (1 + rng.normal(0, 0.05) * vol))
        conversion_rate = max(0.001, BASE_CONVERSION_RATE * (0.5 + 0.5 * reliability) * (1 + rng.normal(0, 0.05) * vol))

        active_idxs = [
            i for i, c in enumerate(customers)
            if c["signup_day_offset"] <= day and (c["churned_day_offset"] is None or c["churned_day_offset"] > day)
        ]

        product_weights = np.ones(len(products))
        for e in events:
            if e["event_type"] == "inventory_shortage":
                product_weights[e["affected_product_idx"]] *= max(0.02, 1 - e["magnitude"] * effect_fraction(day, e))
        product_weights = product_weights / product_weights.sum()

        expected_orders = traffic * conversion_rate * vol
        n_orders = int(rng.poisson(max(0.1, expected_orders)))
        for _ in range(n_orders):
            # most orders are a first-time buyer, not a repeat draw from the active pool
            # -- see REPEAT_PURCHASE_PROB above for why.
            if not active_idxs or rng.random() > REPEAT_PURCHASE_PROB:
                c = _new_customer(rng, stats)
                c["signup_day_offset"] = day
                customers.append(c)
                cust_idx = len(customers) - 1
                active_idxs.append(cust_idx)
            else:
                cust_idx = int(rng.choice(active_idxs))
            prod_idx = int(rng.choice(len(products), p=product_weights))
            price = round(products[prod_idx]["base_price"] * max(0.5, 1 + rng.normal(0, 0.1)), 2)
            qty = int(rng.integers(1, 4))
            order_rows.append((day, cust_idx, prod_idx, qty, price))

            c = customers[cust_idx]
            c["n_orders"] += 1
            c["total_spend"] += price * qty
            c["segment"] = _customer_segment(c["n_orders"], c["total_spend"])

        # scales off traffic (visits that don't convert same-day), not off the existing
        # customer count -- that would compound into runaway exponential growth as the
        # order-driven acquisition above grows the customer base.
        n_new = int(rng.poisson(max(0.05, traffic * 0.005)))
        for _ in range(n_new):
            c = _new_customer(rng, stats)
            c["signup_day_offset"] = day
            customers.append(c)
            active_idxs.append(len(customers) - 1)

        expected_tickets = max(0.1, len(active_idxs) * 0.01 * (1.1 - reliability) * 5)
        n_tickets = int(rng.poisson(expected_tickets))
        for _ in range(n_tickets):
            cust_idx = int(rng.choice(active_idxs)) if active_idxs else 0
            cat = str(rng.choice(["bug", "shipping", "billing", "other"], p=[0.4, 0.3, 0.15, 0.15]))
            ticket_rows.append((day, cust_idx, cat))

        complaint_rate = n_tickets / max(1, len(active_idxs))
        satisfaction = 0.9 * satisfaction + 0.1 * max(0.0, 1 - complaint_rate * 10)

        churn_rate = max(0.0, min(0.3, BASE_CHURN_RATE * (1 + (1 - satisfaction)) * (1 + competitor_activity)))
        for idx in active_idxs:
            c = customers[idx]
            if c["segment"] not in CHURN_ELIGIBLE_SEGMENTS:
                continue  # a one-time buyer not returning isn't "churn" -- see design doc discussion
            mult = 1.0
            for e in events:
                if e["affected_segment"] == c["segment"]:
                    mult *= 1 + (e["segment_multiplier"] - 1) * effect_fraction(day, e)
            if rng.random() < min(0.5, churn_rate * mult):
                c["churned_day_offset"] = day

        daily_state_rows.append((
            day, current_date, marketing_spend, season, int(traffic), conversion_rate,
            reliability, satisfaction, competitor_activity, churn_rate, vol,
        ))

    return {
        "seed": seed, "n_days": n_days, "start_date": start_date,
        "customers": customers, "products": products, "events": events,
        "daily_state": daily_state_rows, "orders": order_rows, "tickets": ticket_rows,
    }


# --- DB write ---

def insert_episode(conn, ep):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO episodes (seed, n_days, start_date) VALUES (%s,%s,%s) RETURNING episode_id",
            (ep["seed"], ep["n_days"], ep["start_date"]),
        )
        episode_id = cur.fetchone()[0]

        customer_rows = [
            (episode_id, c["segment"], c["region"], c["signup_day_offset"], c["churned_day_offset"])
            for c in ep["customers"]
        ]
        result = psycopg2.extras.execute_values(
            cur,
            "INSERT INTO customers (episode_id, segment, region, signup_day_offset, churned_day_offset) "
            "VALUES %s RETURNING customer_id",
            customer_rows, fetch=True,
        )
        customer_ids = [r[0] for r in result]

        product_rows = [(episode_id, p["category"], p["unit_cost"], p["base_price"]) for p in ep["products"]]
        result = psycopg2.extras.execute_values(
            cur,
            "INSERT INTO products (episode_id, category, unit_cost, base_price) VALUES %s RETURNING product_id",
            product_rows, fetch=True,
        )
        product_ids = [r[0] for r in result]

        daily_rows = [(episode_id, *row) for row in ep["daily_state"]]
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO daily_state (episode_id, day_offset, date, marketing_spend, seasonality_factor, "
            "traffic, conversion_rate, product_reliability, satisfaction, competitor_activity, churn_rate, "
            "volatility_multiplier) VALUES %s",
            daily_rows,
        )

        order_rows = [
            (episode_id, day, customer_ids[ci], product_ids[pi], qty, price)
            for (day, ci, pi, qty, price) in ep["orders"]
        ]
        if order_rows:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO orders (episode_id, day_offset, customer_id, product_id, quantity, unit_price) "
                "VALUES %s",
                order_rows, page_size=1000,
            )

        ticket_rows = [(episode_id, day, customer_ids[ci], cat) for (day, ci, cat) in ep["tickets"]]
        if ticket_rows:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO support_tickets (episode_id, day_offset, customer_id, category) VALUES %s",
                ticket_rows, page_size=1000,
            )

        event_db_ids = {}
        for i, ev in enumerate(ep["events"]):
            triggered_by_id = event_db_ids.get(ev["triggered_by_idx"]) if ev["triggered_by_idx"] is not None else None
            affected_product_id = (
                product_ids[ev["affected_product_idx"]] if ev["affected_product_idx"] is not None else None
            )
            cur.execute(
                "INSERT INTO injected_events (episode_id, event_type, severity, onset_type, start_day_offset, "
                "end_day_offset, mitigation_day_offset, mitigation_completeness, magnitude, segment_multiplier, "
                "affected_segment, affected_product_id, triggered_by_event_id, description) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING event_id",
                (episode_id, ev["event_type"], ev["severity"], ev["onset_type"], ev["start_day_offset"],
                 ev["end_day_offset"], ev["mitigation_day_offset"], ev["mitigation_completeness"],
                 ev["magnitude"], ev["segment_multiplier"], ev["affected_segment"], affected_product_id,
                 triggered_by_id, ev["description"]),
            )
            event_db_ids[i] = cur.fetchone()[0]

    conn.commit()
    return episode_id


def main():
    parser = argparse.ArgumentParser(description="Generate Layer 1 ground-truth episodes into Postgres.")
    parser.add_argument("--n-episodes", type=int, default=10)
    parser.add_argument("--n-days", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true", help="Truncate all 7 tables before generating.")
    args = parser.parse_args()

    load_dotenv()
    stats = load_olist_stats()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        if args.reset:
            with conn.cursor() as cur:
                cur.execute(
                    "TRUNCATE injected_events, support_tickets, orders, daily_state, products, "
                    "customers, episodes RESTART IDENTITY CASCADE"
                )
            conn.commit()

        rng = np.random.default_rng(args.seed)
        start_date = date(2024, 1, 1)
        for i in range(args.n_episodes):
            episode_seed = int(rng.integers(0, 2**31 - 1))
            episode_rng = np.random.default_rng(episode_seed)
            n_customers = int(episode_rng.integers(200, 500))
            n_products = int(episode_rng.integers(2, 5))
            ep = generate_episode(episode_rng, episode_seed, args.n_days, start_date, stats, n_customers, n_products)
            episode_id = insert_episode(conn, ep)
            print(
                f"episode {i + 1}/{args.n_episodes} -> db id {episode_id}, "
                f"{len(ep['customers'])} customers, {len(ep['orders'])} orders, {len(ep['events'])} events"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
