"""Populates source_outages -- the gap windows Layer 2's views suppress data for
(design doc §3, scenario 4). Run once after generate.py has populated Layer 1.

Usage:
    python inject_outages.py --seed 42
"""

import argparse
import os

import numpy as np
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

SOURCES = ["billing_system", "crm_system", "marketing_system"]
OUTAGE_PROB = 0.25
PARTIAL_PROB = 0.70  # vs total, and only marketing_system has a metric that can gap alone
PARTIAL_METRIC = {"marketing_system": "attributed_revenue"}


def sample_outages(rng, episode_id, n_days):
    rows = []
    for source in SOURCES:
        if rng.random() >= OUTAGE_PROB:
            continue
        partial = source in PARTIAL_METRIC and rng.random() < PARTIAL_PROB
        duration = int(rng.integers(5, 11)) if partial else int(rng.integers(3, 8))
        start = int(rng.integers(10, max(11, n_days - duration - 10)))
        end = min(n_days - 1, start + duration)
        metric = PARTIAL_METRIC[source] if partial else None
        rows.append((episode_id, source, metric, start, end))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Inject Layer 2 source outages.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE source_outages RESTART IDENTITY")
            cur.execute("SELECT episode_id, n_days FROM episodes ORDER BY episode_id")
            episodes = cur.fetchall()

            rng = np.random.default_rng(args.seed)
            all_rows = []
            for episode_id, n_days in episodes:
                all_rows.extend(sample_outages(rng, episode_id, n_days))

            if all_rows:
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO source_outages (episode_id, source_name, metric_name, start_day_offset, end_day_offset) "
                    "VALUES %s",
                    all_rows,
                )
        conn.commit()
        print(f"injected {len(all_rows)} outages across {len(episodes)} episodes")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
