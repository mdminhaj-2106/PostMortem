"""Stage 1 self-check -- offline invariant checks (no DB) + live-DB checks against the
real Neon dataset, mirroring test_generate.py/test_views.py's split.

Run: .venv/bin/python test_reconcile.py
"""

import os
from datetime import date

import psycopg2
from dotenv import load_dotenv

import calendar_dimension
import identity_resolution
import materiality
import semantic_contract
from models import ReconciledValue
import reconcile as reconcile_module
from reconcile import (
    _fetch_billing_revenue,
    _fetch_episode_start_date,
    reconcile_calendar_misaligned_active_customers,
    reconcile_conflicting_values,
    reconcile_definitional_active_customers,
    reconcile_partial_gap_revenue,
)


# --- offline ---

def test_materiality_gate():
    assert not materiality.is_material(100.0, 103.0, "revenue")  # 3% < 5% threshold
    assert materiality.is_material(100.0, 120.0, "revenue")  # 20% > 5% threshold
    assert not materiality.is_material(100.0, 108.0, "active_customers")  # 8% < 10%


def test_calendar_bucket_daily():
    assert calendar_dimension.bucket_day(42, "daily", date(2024, 1, 1)) == 42


def test_calendar_bucket_iso_week():
    # 2024-01-01 is a Monday, so day_offset 0 is already a week start.
    assert calendar_dimension.bucket_day(0, "iso_week", date(2024, 1, 1)) == 0
    assert calendar_dimension.bucket_day(3, "iso_week", date(2024, 1, 1)) == 0
    assert calendar_dimension.bucket_day(10, "iso_week", date(2024, 1, 1)) == 7


def test_calendar_bucket_billing_cycle_month():
    assert calendar_dimension.bucket_day(10, "billing_cycle_month", date(2024, 1, 1)) is None
    assert calendar_dimension.bucket_day(15, "billing_cycle_month", date(2024, 1, 1)) == 0
    assert calendar_dimension.bucket_day(44, "billing_cycle_month", date(2024, 1, 1)) == 0
    assert calendar_dimension.bucket_day(45, "billing_cycle_month", date(2024, 1, 1)) == 1


def test_bias_correction_matches_views_sql():
    # views.sql: CASE WHEN day_offset < n_days / 2 THEN 0.87 ELSE 0.80 END
    corrected = semantic_contract.apply_bias_correction("marketing_system", "attributed_revenue", 87.0, 0, 120)
    assert round(corrected, 2) == 100.0
    corrected = semantic_contract.apply_bias_correction("marketing_system", "attributed_revenue", 80.0, 100, 120)
    assert round(corrected, 2) == 100.0
    # no declared bias -- passes through
    assert semantic_contract.apply_bias_correction("billing_system", "revenue", 50.0) == 50.0


def test_bias_correction_is_read_from_the_contract_not_hardcoded():
    """Audit finding F8. The factor used to live in module constants beside a prose
    description in SEMANTIC_CONTRACT -- two sources of truth hand-synced. Editing the
    contract must now change the arithmetic; if it doesn't, the hardcoded branch is back."""
    entry = semantic_contract.SEMANTIC_CONTRACT["marketing_system"]["metrics"]["attributed_revenue"]
    original = entry["bias_factor"]
    try:
        entry["bias_factor"] = {"before_midpoint": 0.5, "from_midpoint": 0.5}
        assert semantic_contract.apply_bias_correction(
            "marketing_system", "attributed_revenue", 100.0, day_offset=0, n_days=100
        ) == 200.0, "apply_bias_correction ignored the contract"
    finally:
        entry["bias_factor"] = original

    # A metric with no declared bias passes through untouched...
    assert semantic_contract.apply_bias_correction("billing_system", "revenue", 42.0) == 42.0
    # ...and an undeclared pair raises instead of silently assuming "no bias" (F9 class).
    try:
        semantic_contract.apply_bias_correction("billing_system", "not_a_metric", 1.0)
        raise AssertionError("expected KeyError for an undeclared source/metric")
    except KeyError:
        pass


def test_source_registry_covers_every_declared_kpi():
    """Audit finding F7/F14. Every KPI in the registry needs a materiality threshold and
    a contract entry for each of its sources, or it silently misbehaves at runtime."""
    for kpi_name, entries in reconcile_module.SOURCES.items():
        assert kpi_name in materiality.DEFAULT_THRESHOLDS, f"no materiality threshold for {kpi_name}"
        assert entries, f"{kpi_name} declares no sources"
        for source_name, view, column in entries:
            contract = semantic_contract.metric_contract(source_name, column)
            assert "bias_factor" in contract, f"{source_name}.{column} has no bias_factor declared"
            assert view.startswith("v_"), f"{view} does not look like a Layer 2 view"


def test_reconciled_value_validates_tier():
    ReconciledValue(1, 0, "revenue", 100.0, "exact", ["billing_system"])  # must not raise
    try:
        ReconciledValue(1, 0, "revenue", 100.0, "made_up_tier", ["billing_system"])
        assert False, "expected ValueError for invalid confidence_tier"
    except ValueError:
        pass


def test_identity_resolution_zones():
    assert identity_resolution.score_match(5, 5) == "auto_merge"
    assert identity_resolution.score_match(5, 6) == "ambiguous"  # near-miss
    assert identity_resolution.score_match(5, 900005) == "ambiguous"  # duplicate


# --- live DB ---

def test_scenario1_agreeing_day(cur):
    cur.execute("SELECT episode_id FROM episodes ORDER BY episode_id LIMIT 1")
    episode_id = cur.fetchone()[0]
    for day_offset in range(0, 10):
        billing = _fetch_billing_revenue(cur, episode_id, day_offset)
        if billing is None:
            continue
        rv = reconcile_conflicting_values(cur, episode_id, day_offset)
        assert rv.confidence_tier in ("exact", "aggregated"), (
            f"expected bias-corrected marketing to agree with billing on day {day_offset}, got {rv.confidence_tier}"
        )
        assert abs(rv.value - billing) / billing < 0.05
        return
    raise AssertionError("no usable billing day found in first 10 days of episode 1")


def test_scenario1_partial_gap_graceful(cur):
    cur.execute(
        "SELECT episode_id, start_day_offset, end_day_offset FROM source_outages "
        "WHERE source_name='marketing_system' AND metric_name='attributed_revenue' LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        return  # no marketing partial-gap outage in this dataset run -- nothing to check
    episode_id, start, end = row
    day_offset = (start + end) // 2
    billing = _fetch_billing_revenue(cur, episode_id, day_offset)
    if billing is None:
        return  # billing also dark this day -- not the case this test targets

    rv = reconcile_conflicting_values(cur, episode_id, day_offset)
    assert rv.confidence_tier == "estimated"
    assert rv.imputation_flag == "partially_imputed"
    assert rv.value == billing, "partial-gap value should be billing-derived directly"


def test_scenario4_partial_gap_direct(cur):
    cur.execute(
        "SELECT episode_id, start_day_offset, end_day_offset FROM source_outages "
        "WHERE source_name='marketing_system' AND metric_name='attributed_revenue' LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        return
    episode_id, start, end = row
    day_offset = (start + end) // 2
    billing = _fetch_billing_revenue(cur, episode_id, day_offset)
    if billing is None:
        return

    rv = reconcile_partial_gap_revenue(cur, episode_id, day_offset)
    assert rv.imputation_flag == "partially_imputed"
    assert rv.imputation_method == "triangulated_from_billing_direct"
    assert rv.value == billing


def test_scenario2_definitional_two_rows(cur):
    cur.execute("SELECT episode_id FROM episodes ORDER BY episode_id LIMIT 1")
    episode_id = cur.fetchone()[0]
    start_date = _fetch_episode_start_date(cur, episode_id)

    rows = reconcile_definitional_active_customers(cur, episode_id, 35, start_date)
    kpi_names = {r.kpi_name for r in rows}
    assert kpi_names, "expected at least one row"
    assert kpi_names <= {"active_customers_purchased_30d", "active_customers_interacted_30d"}
    for r in rows:
        if r.kpi_name == "active_customers_purchased_30d":
            assert r.source_provenance == ["billing_system"]
        if r.kpi_name == "active_customers_interacted_30d":
            assert r.source_provenance == ["crm_system"]


def test_weekly_snapshot_marks_carried_forward_days(cur):
    """crm snapshots active_customers ONCE per ISO week; the other six days carry that
    value forward. Declaring all seven 'untouched' made Stage 2 score a weekly metric at
    HIGH history_confidence, identical to exact daily billing data, because eligibility
    only inspects imputation_flag. Exactly one observed day per week, the rest flagged."""
    cur.execute("SELECT episode_id FROM episodes ORDER BY episode_id LIMIT 1")
    episode_id = cur.fetchone()[0]
    start_date = _fetch_episode_start_date(cur, episode_id)

    flags_by_day = {}
    for day_offset in range(35, 56):  # three full ISO weeks
        for r in reconcile_definitional_active_customers(cur, episode_id, day_offset, start_date):
            if r.kpi_name == "active_customers_interacted_30d":
                flags_by_day[day_offset] = r.imputation_flag

    assert flags_by_day, "expected crm rows in this window"
    observed = sorted(d for d, f in flags_by_day.items() if f == "untouched")
    assert observed, "no day was marked as an actual observation"
    assert all(f in ("untouched", "partially_imputed") for f in flags_by_day.values())
    # snapshot days are exactly one ISO week apart
    assert all(b - a == 7 for a, b in zip(observed, observed[1:])), observed
    # and the carried-forward days dominate, which is what should cost it confidence
    assert len(observed) < len(flags_by_day) / 2


def test_scenario5_calendar_alignment(cur):
    cur.execute("SELECT episode_id FROM episodes ORDER BY episode_id LIMIT 1")
    episode_id = cur.fetchone()[0]
    start_date = _fetch_episode_start_date(cur, episode_id)

    day_offset = 40
    cycle_idx = calendar_dimension.bucket_day(day_offset, "billing_cycle_month", start_date)
    assert cycle_idx is not None

    cur.execute(
        "SELECT count(*) FROM v_marketing_monthly_active_customers WHERE episode_id=%s AND billing_cycle_index=%s",
        (episode_id, cycle_idx),
    )
    assert cur.fetchone()[0] == 1, "calendar_dimension's bucket must match the live view's own grouping"

    rv = reconcile_calendar_misaligned_active_customers(cur, episode_id, day_offset, start_date)
    assert rv.confidence_tier in ("exact", "aggregated", "triangulated")

    # any day inside the same cycle must resolve to the same cycle_end_day snapshot --
    # the marketing view only snapshots once per cycle, not once per day.
    rv2 = reconcile_calendar_misaligned_active_customers(cur, episode_id, 15, start_date)
    assert rv2.day_offset == rv.day_offset
    assert rv2.value == rv.value


def test_scenario6_identity_flags(cur):
    cur.execute("SELECT episode_id FROM episodes ORDER BY episode_id LIMIT 1")
    episode_id = cur.fetchone()[0]
    results = identity_resolution.resolve_customer_identities(cur, episode_id)

    duplicates = [r for r in results if r["crm_account_id"] >= 900000]
    near_misses = [r for r in results if r["crm_account_id"] != r["customer_id"] and r["crm_account_id"] < 900000]
    exact = [r for r in results if r["crm_account_id"] == r["customer_id"]]

    assert duplicates, "expected some synthetic duplicate crm_account_ids"
    assert near_misses, "expected some near-miss crm_account_ids"
    assert all(r["zone"] == "ambiguous" for r in duplicates), "duplicates must not be silently auto-merged"
    assert all(r["zone"] == "ambiguous" for r in near_misses), "near-misses must not be silently trusted"
    assert all(r["zone"] == "auto_merge" for r in exact)


if __name__ == "__main__":
    test_materiality_gate()
    test_calendar_bucket_daily()
    test_calendar_bucket_iso_week()
    test_calendar_bucket_billing_cycle_month()
    test_bias_correction_matches_views_sql()
    test_bias_correction_is_read_from_the_contract_not_hardcoded()
    test_source_registry_covers_every_declared_kpi()
    test_reconciled_value_validates_tier()
    test_identity_resolution_zones()

    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            test_scenario1_agreeing_day(cur)
            test_scenario1_partial_gap_graceful(cur)
            test_scenario4_partial_gap_direct(cur)
            test_scenario2_definitional_two_rows(cur)
            test_weekly_snapshot_marks_carried_forward_days(cur)
            test_scenario5_calendar_alignment(cur)
            test_scenario6_identity_flags(cur)
    finally:
        conn.close()
    print("OK")
