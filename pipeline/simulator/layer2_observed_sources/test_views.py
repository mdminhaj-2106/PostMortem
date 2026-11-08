"""Smoke check for the Layer 2 views -- requires a live DATABASE_URL with Layer 1 +
Layer 2 (schema_layer2.sql, views.sql, inject_outages.py) already applied.

Run: .venv/bin/python test_views.py
"""

import os

import psycopg2
from dotenv import load_dotenv


def test_total_gap_suppresses_rows(cur):
    cur.execute(
        "SELECT episode_id, start_day_offset, end_day_offset FROM source_outages "
        "WHERE source_name = 'billing_system' AND metric_name IS NULL LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        return  # no billing outage in this dataset run -- nothing to check
    episode_id, start, end = row
    cur.execute(
        "SELECT count(*) FROM v_billing_daily_revenue WHERE episode_id=%s AND day_offset BETWEEN %s AND %s",
        (episode_id, start, end),
    )
    assert cur.fetchone()[0] == 0, "total-gap outage window should have zero rows, not zeroed values"


def test_marketing_bias_matches_drift_boundary(cur):
    cur.execute("SELECT episode_id, n_days FROM episodes LIMIT 1")
    episode_id, n_days = cur.fetchone()
    drift_day = n_days // 2
    cur.execute(
        "SELECT b.attributed_revenue::numeric / o.revenue::numeric FROM "
        "v_marketing_daily_attributed_revenue b JOIN v_billing_daily_revenue o "
        "ON o.episode_id=b.episode_id AND o.day_offset=b.day_offset "
        "WHERE b.episode_id=%s AND b.day_offset = %s", (episode_id, max(0, drift_day - 5)),
    )
    ratio_before = cur.fetchone()
    cur.execute(
        "SELECT b.attributed_revenue::numeric / o.revenue::numeric FROM "
        "v_marketing_daily_attributed_revenue b JOIN v_billing_daily_revenue o "
        "ON o.episode_id=b.episode_id AND o.day_offset=b.day_offset "
        "WHERE b.episode_id=%s AND b.day_offset = %s", (episode_id, min(n_days - 1, drift_day + 5)),
    )
    ratio_after = cur.fetchone()
    if ratio_before and ratio_after:
        assert round(float(ratio_before[0]), 2) == 0.87
        assert round(float(ratio_after[0]), 2) == 0.80


def test_entity_mismatch_present(cur):
    cur.execute("SELECT episode_id FROM episodes LIMIT 1")
    episode_id = cur.fetchone()[0]
    cur.execute(
        "SELECT count(*) FILTER (WHERE crm_account_id >= 900000) AS dupes, "
        "count(*) FILTER (WHERE crm_account_id != customer_id AND crm_account_id < 900000) AS mismatches "
        "FROM v_crm_customer_mapping WHERE episode_id=%s", (episode_id,),
    )
    dupes, mismatches = cur.fetchone()
    assert dupes > 0, "expected some synthetic duplicate crm_account_ids"
    assert mismatches > 0, "expected some near-miss (wrong-customer) crm_account_ids"


def test_grains_differ(cur):
    cur.execute("SELECT episode_id FROM episodes LIMIT 1")
    episode_id = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM v_billing_daily_revenue WHERE episode_id=%s", (episode_id,))
    n_daily = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM v_crm_weekly_active_customers WHERE episode_id=%s", (episode_id,))
    n_weekly = cur.fetchone()[0]
    assert n_weekly < n_daily, "weekly grain should produce far fewer buckets than daily"


if __name__ == "__main__":
    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            test_total_gap_suppresses_rows(cur)
            test_marketing_bias_matches_drift_boundary(cur)
            test_entity_mismatch_present(cur)
            test_grains_differ(cur)
    finally:
        conn.close()
    print("OK")
