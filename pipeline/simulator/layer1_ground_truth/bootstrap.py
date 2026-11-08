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


def reliability_noise_std(stats, baseline=0.10):
    """Daily noise std for the abstract 0-1 product_reliability score.

    There's no literal unit conversion from "days of delivery slippage" to a 0-1
    reliability score, so this doesn't try to fake one. Instead it uses the *relative*
    volatility of real delivery timing (std/|mean| of slippage days) to scale a small
    baseline noise level -- real data informs how noisy reliability should be relative
    to itself, not a precise unit-for-unit conversion.
    """
    mean_days, std_days = reliability_baseline(stats)
    relative_volatility = std_days / max(1.0, abs(mean_days))
    return baseline * relative_volatility
