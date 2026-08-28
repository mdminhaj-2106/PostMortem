"""Offline smoke check for the episode generator — no DB needed.

Run: .venv/bin/python test_generate.py
"""

from datetime import date

import numpy as np

from bootstrap import load_olist_stats
from generate import effect_fraction, generate_episode


def test_effect_fraction_shapes():
    step = {"start_day_offset": 10, "onset_type": "step", "end_day_offset": None,
            "mitigation_day_offset": None, "mitigation_completeness": None}
    assert effect_fraction(9, step) == 0.0
    assert effect_fraction(10, step) == 1.0
    assert effect_fraction(50, step) == 1.0

    ramp = {**step, "onset_type": "ramp"}
    assert effect_fraction(10, ramp) == 0.0
    assert 0 < effect_fraction(15, ramp) < 1.0
    assert effect_fraction(25, ramp) == 1.0

    mitigated = {**step, "mitigation_day_offset": 20, "mitigation_completeness": 1.0}
    assert effect_fraction(20, mitigated) == 1.0
    assert effect_fraction(35, mitigated) == 0.0  # fully mitigated -> decays to 0


def test_generate_episode_invariants():
    stats = load_olist_stats()
    rng = np.random.default_rng(123)
    ep = generate_episode(rng, seed=123, n_days=90, start_date=date(2024, 1, 1),
                           stats=stats, n_customers_initial=200, n_products=3)

    assert len(ep["daily_state"]) == 90
    assert [row[0] for row in ep["daily_state"]] == list(range(90))
    assert all(row[10] > 0 for row in ep["daily_state"])  # volatility_multiplier always positive

    n_customers, n_products = len(ep["customers"]), len(ep["products"])
    for (day, cust_idx, prod_idx, qty, price) in ep["orders"]:
        assert 0 <= day < 90
        assert 0 <= cust_idx < n_customers
        assert 0 <= prod_idx < n_products
        assert qty >= 1 and price > 0

    for c in ep["customers"]:
        if c["churned_day_offset"] is not None:
            assert c["churned_day_offset"] >= c["signup_day_offset"]
        assert c["segment"] in ("New", "Returning", "VIP")  # RFM tier, not SMB/Enterprise -- B2C data

    event_indices = set(range(len(ep["events"])))
    for i, ev in enumerate(ep["events"]):
        if ev["triggered_by_idx"] is not None:
            assert ev["triggered_by_idx"] in event_indices
            assert ev["triggered_by_idx"] < i  # trigger always generated before its reaction


if __name__ == "__main__":
    test_effect_fraction_shapes()
    test_generate_episode_invariants()
    print("OK")
