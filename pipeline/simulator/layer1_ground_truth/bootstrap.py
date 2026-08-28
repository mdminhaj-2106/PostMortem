"""Real-data grounding for the Layer 1 generator.

Loads `olist_stats.json` — aggregate statistics (region distribution, product
categories/prices, day-of-week and month seasonality, delivery slippage)
derived once from the real Olist Brazilian e-commerce dataset. See
docs/02-stage-design-reports/simulator-layer1-ground-truth-design.md §1.1.

We vendor the derived stats, not the raw ~104MB dataset: smaller, no runtime
network dependency, and this is all the generator actually needs.
"""

import json
from pathlib import Path

import numpy as np

STATS_PATH = Path(__file__).parent / "olist_stats.json"


def load_olist_stats():
    with open(STATS_PATH) as f:
        return json.load(f)


def sample_region(rng, stats):
    states = list(stats["region_weights"].keys())
    weights = np.array(list(stats["region_weights"].values()))
    return rng.choice(states, p=weights / weights.sum())  # rounded weights in the JSON don't sum to exactly 1


def sample_product(rng, stats):
    """Returns (category, unit_cost, base_price) for a new product, real-price-distributed."""
    categories = stats["categories"]
    weights = np.array([c["weight"] for c in categories])
    cat = categories[rng.choice(len(categories), p=weights / weights.sum())]
    price = max(5.0, rng.normal(cat["mean_price"], cat["std_price"]))
    cost = price * rng.uniform(0.4, 0.7)  # margin isn't in Olist data, a reasonable assumption
    return cat["name"], round(cost, 2), round(price, 2)


def seasonality_factor(stats, date):
    """Relative order-volume multiplier for a given date, from real day-of-week + month shape."""
    dow = stats["dow_multipliers"][date.weekday()]
    month = stats["month_multipliers"][date.month - 1]
    return dow * month


def reliability_baseline(stats):
    """(mean, std) days of delivery slippage — negative mean = delivered early on average.
    Used as the real-world noise floor for product_reliability, so an injected outage is a
    departure from genuine baseline flakiness, not from an invented perfect baseline."""
    return stats["delivery_slippage"]["mean_days"], stats["delivery_slippage"]["std_days"]
