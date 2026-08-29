"""Stage 1 escalation-ladder pipeline. See docs/02-stage-design-reports/stage1-reconciliation-design.md
and .claude/plans/stage1-reconciliation-ingestion.md for scope (Scenarios 1, 2, 4-partial, 5, 6
in this slice; 3 and 4-total/7 deferred -- see the plan's Risks).

Usage:
    python reconcile.py --episode-id 1 --day-offset 10 --kpi revenue
"""

import argparse
import os

import psycopg2
from dotenv import load_dotenv

import calendar_dimension
import materiality
import semantic_contract
from models import ReconciledValue


# --- DB fetch helpers ---

def _fetch_billing_revenue(cur, episode_id, day_offset):
    cur.execute(
        "SELECT revenue FROM v_billing_daily_revenue WHERE episode_id=%s AND day_offset=%s",
        (episode_id, day_offset),
    )
    row = cur.fetchone()
    return float(row[0]) if row else None


def _fetch_marketing_attributed_revenue(cur, episode_id, day_offset):
    cur.execute(
        "SELECT attributed_revenue FROM v_marketing_daily_attributed_revenue WHERE episode_id=%s AND day_offset=%s",
        (episode_id, day_offset),
    )
    row = cur.fetchone()
    return float(row[0]) if row else None


def _fetch_n_days(cur, episode_id):
    cur.execute("SELECT n_days FROM episodes WHERE episode_id=%s", (episode_id,))
    return cur.fetchone()[0]


def _fetch_episode_start_date(cur, episode_id):
    cur.execute("SELECT start_date FROM episodes WHERE episode_id=%s", (episode_id,))
    return cur.fetchone()[0]


def _fetch_billing_active_customers(cur, episode_id, day_offset):
    cur.execute(
        "SELECT active_customers FROM v_billing_active_customers WHERE episode_id=%s AND day_offset=%s",
        (episode_id, day_offset),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def _fetch_crm_weekly_active_customers(cur, episode_id, week_start_day_offset):
    if week_start_day_offset is None:
        return None
    cur.execute(
        "SELECT active_customers FROM v_crm_weekly_active_customers WHERE episode_id=%s AND week_start_day_offset=%s",
        (episode_id, week_start_day_offset),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def _fetch_marketing_cycle_active_customers(cur, episode_id, billing_cycle_index):
    if billing_cycle_index is None:
        return None
    cur.execute(
        "SELECT active_customers FROM v_marketing_monthly_active_customers WHERE episode_id=%s AND billing_cycle_index=%s",
        (episode_id, billing_cycle_index),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


# --- Scenario 4 (partial gap only) ---

def reconcile_partial_gap_revenue(cur, episode_id, day_offset, billing_revenue=None):
    """marketing_system's attributed_revenue is dark for this day but billing's revenue
    is present -- they're the same underlying fact, just biased, so triangulate straight
    from billing rather than leaving a null."""
    if billing_revenue is None:
        billing_revenue = _fetch_billing_revenue(cur, episode_id, day_offset)
    if billing_revenue is None:
        raise ValueError("reconcile_partial_gap_revenue requires billing to be present")
    return ReconciledValue(
        episode_id=episode_id, day_offset=day_offset, kpi_name="revenue", value=billing_revenue,
        confidence_tier="estimated", source_provenance=["billing_system"],
        imputation_flag="partially_imputed", imputation_method="triangulated_from_billing_direct",
        uncertainty_width=0.0,
    )


# --- Scenario 1 (conflicting values), parameterized ---

# kpi_name -> source entries, AUTHORITATIVE FIRST. Each entry is
# (source_name, view, column); the column name doubles as the metric's key in the
# Semantic Contract, so bias metadata is looked up rather than branched on.
#
# Audit finding F7: this was three bespoke functions with view and column names baked
# into private per-source fetch helpers, so adding a KPI or a source meant copy-pasting
# another one. There is still exactly ONE real conflict pair in this dataset (revenue:
# billing vs marketing) -- verified, it is the only construct two sources both report --
# which is why the hardcoded version survived; a registry is what let KPIs 3-5 land as
# data instead of code (F14).
SOURCES = {
    "revenue": (
        ("billing_system", "v_billing_daily_revenue", "revenue"),
        ("marketing_system", "v_marketing_daily_attributed_revenue", "attributed_revenue"),
    ),
    "orders_count": (
        ("billing_system", "v_billing_daily_revenue", "orders_count"),
    ),
    "avg_order_value": (
        ("billing_system", "v_billing_daily_revenue", "avg_order_value"),
    ),
    "units_sold": (
        ("billing_system", "v_billing_daily_revenue", "units_sold"),
    ),
}


def _fetch_metric(cur, view, column, episode_id, day_offset):
    """view/column come only from SOURCES above -- declared constants, never user input,
    so the f-string is not an injection surface. episode_id/day_offset stay parameters."""
    cur.execute(
        f"SELECT {column} FROM {view} WHERE episode_id=%s AND day_offset=%s",
        (episode_id, day_offset),
    )
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else None


def reconcile(cur, episode_id, day_offset, kpi_name):
    """One reconciler for every registry-declared KPI (F7). Same escalation ladder the
    hardcoded revenue path used: authoritative source anchors, declared bias is corrected
    off the others, the materiality gate decides average-vs-anchor, and an unresolvable
    conflict declines rather than propagating a made-up number."""
    if kpi_name not in SOURCES:
        raise ValueError(
            f"unknown kpi_name: {kpi_name!r} -- declare its sources in SOURCES rather "
            f"than adding another bespoke reconcile_* function (F7). "
            f"Known: {tuple(SOURCES)}"
        )
    entries = SOURCES[kpi_name]
    authoritative_source, auth_view, auth_column = entries[0]

    authoritative = _fetch_metric(cur, auth_view, auth_column, episode_id, day_offset)
    if authoritative is None:
        # Authoritative source dark. Total-gap forecast reconciliation is out of scope
        # for this slice (needs Stage 2's changepoint engine -- plan Risk #1); decline
        # rather than propagate a shakier bias-corrected-only estimate.
        return ReconciledValue(
            episode_id=episode_id, day_offset=day_offset, kpi_name=kpi_name, value=None,
            confidence_tier="declared_unresolved", source_provenance=[], imputation_flag="fully_imputed",
        )

    corroborators = []
    for source_name, view, column in entries[1:]:
        raw = _fetch_metric(cur, view, column, episode_id, day_offset)
        if raw is None:
            continue
        n_days = _fetch_n_days(cur, episode_id)
        corroborators.append((
            source_name,
            semantic_contract.apply_bias_correction(source_name, column, raw, day_offset, n_days),
        ))

    if len(entries) == 1:
        # Only one source declared for this KPI -- nothing to disagree with. Not an
        # imputation and not a gap: billing is contract-declared ground-truth-equivalent.
        return ReconciledValue(
            episode_id=episode_id, day_offset=day_offset, kpi_name=kpi_name, value=authoritative,
            confidence_tier="exact", source_provenance=[authoritative_source],
            imputation_flag="untouched",
        )

    if not corroborators:
        # A corroborating source IS declared but is dark today (partial gap, Scenario 4).
        # Same fact, just unconfirmed -- triangulate straight from the authoritative
        # source rather than leaving a null.
        return ReconciledValue(
            episode_id=episode_id, day_offset=day_offset, kpi_name=kpi_name, value=authoritative,
            confidence_tier="estimated", source_provenance=[authoritative_source],
            imputation_flag="partially_imputed", imputation_method="triangulated_from_billing_direct",
            uncertainty_width=0.0,
        )

    provenance = [authoritative_source] + [s for s, _ in corroborators]
    spread = max(abs(authoritative - corrected) for _, corrected in corroborators)
    disagrees = any(
        materiality.is_material(authoritative, corrected, kpi_name)
        for _, corrected in corroborators
    )

    if not disagrees:
        values = [authoritative] + [corrected for _, corrected in corroborators]
        return ReconciledValue(
            episode_id=episode_id, day_offset=day_offset, kpi_name=kpi_name,
            value=sum(values) / len(values),
            confidence_tier="exact" if spread < 1e-6 else "aggregated",
            source_provenance=provenance, imputation_flag="untouched", uncertainty_width=spread,
        )

    # Bias correction alone doesn't explain the remaining gap. The authoritative source is
    # declared ground-truth-equivalent (Semantic Contract) -- anchor on it and widen
    # uncertainty rather than average through a real disagreement. Full cross-signal
    # triangulation across a DAG of 30-50 KPIs is out of scope for this slice.
    return ReconciledValue(
        episode_id=episode_id, day_offset=day_offset, kpi_name=kpi_name, value=authoritative,
        confidence_tier="triangulated", source_provenance=provenance,
        imputation_flag="untouched", imputation_method="bias_corrected_cross_check",
        uncertainty_width=spread,
    )


def reconcile_conflicting_values(cur, episode_id, day_offset):
    """Kept as the name Stage 2's ingest and the demo already call. Thin alias, not a
    second code path."""
    return reconcile(cur, episode_id, day_offset, "revenue")


# --- Scenario 2 (definitional mismatch) ---

def reconcile_definitional_active_customers(cur, episode_id, day_offset, start_date):
    """billing's purchase-based and crm's interaction-based 'active' are genuinely
    different constructs (design doc Scenario 2) -- emit both, never collapsed."""
    rows = []
    billing_val = _fetch_billing_active_customers(cur, episode_id, day_offset)
    if billing_val is not None:
        rows.append(ReconciledValue(
            episode_id=episode_id, day_offset=day_offset, kpi_name="active_customers_purchased_30d",
            value=billing_val, confidence_tier="exact", source_provenance=["billing_system"],
        ))

    week_bucket = calendar_dimension.bucket_day(day_offset, "iso_week", start_date)
    crm_val = _fetch_crm_weekly_active_customers(cur, episode_id, week_bucket)
    if crm_val is not None:
        rows.append(ReconciledValue(
            episode_id=episode_id, day_offset=day_offset, kpi_name="active_customers_interacted_30d",
            value=crm_val, confidence_tier="aggregated", source_provenance=["crm_system"],
            imputation_method="calendar_bucketed_weekly_snapshot",
        ))
    return rows


# --- Scenario 5 (calendar misalignment) ---

def reconcile_calendar_misaligned_active_customers(cur, episode_id, day_offset, start_date):
    """billing's daily and marketing's billing-cycle active_customers share the same
    definition (design doc Scenario 5) -- align via Calendar Dimension, don't materialize
    a third grain.

    v_marketing_monthly_active_customers snapshots once per cycle, at that cycle's last
    day (cycle_end_day) -- not once per day. So the emitted value is "as of
    cycle_end_day", regardless of which day within the cycle was requested; comparing
    billing's trailing-30-day value at any other day would compare two different
    30-day windows, not a genuine value conflict.
    """
    cycle_idx = calendar_dimension.bucket_day(day_offset, "billing_cycle_month", start_date)
    if cycle_idx is None:
        billing_val = _fetch_billing_active_customers(cur, episode_id, day_offset)
        if billing_val is None:
            return ReconciledValue(
                episode_id=episode_id, day_offset=day_offset, kpi_name="active_customers", value=None,
                confidence_tier="declared_unresolved", source_provenance=[], imputation_flag="fully_imputed",
            )
        return ReconciledValue(
            episode_id=episode_id, day_offset=day_offset, kpi_name="active_customers", value=billing_val,
            confidence_tier="exact", source_provenance=["billing_system"],
        )

    n_days = _fetch_n_days(cur, episode_id)
    cycle_end_day = calendar_dimension.billing_cycle_end_day(cycle_idx, n_days)
    billing_val = _fetch_billing_active_customers(cur, episode_id, cycle_end_day)
    marketing_val = _fetch_marketing_cycle_active_customers(cur, episode_id, cycle_idx)

    if billing_val is None and marketing_val is None:
        return ReconciledValue(
            episode_id=episode_id, day_offset=cycle_end_day, kpi_name="active_customers", value=None,
            confidence_tier="declared_unresolved", source_provenance=[], imputation_flag="fully_imputed",
        )
    if marketing_val is None:
        return ReconciledValue(
            episode_id=episode_id, day_offset=cycle_end_day, kpi_name="active_customers", value=billing_val,
            confidence_tier="exact", source_provenance=["billing_system"],
        )
    if billing_val is None:
        return ReconciledValue(
            episode_id=episode_id, day_offset=cycle_end_day, kpi_name="active_customers", value=marketing_val,
            confidence_tier="aggregated", source_provenance=["marketing_system"],
            imputation_method="calendar_bucketed_billing_cycle_snapshot",
        )

    spread = abs(billing_val - marketing_val)
    if not materiality.is_material(billing_val, marketing_val, "active_customers"):
        value = (billing_val + marketing_val) / 2
        tier = "exact" if spread == 0 else "aggregated"
    else:
        value = billing_val
        tier = "triangulated"
    return ReconciledValue(
        episode_id=episode_id, day_offset=cycle_end_day, kpi_name="active_customers", value=value,
        confidence_tier=tier, source_provenance=["billing_system", "marketing_system"],
        imputation_method="calendar_aligned_billing_cycle", uncertainty_width=spread,
    )


def _connect():
    load_dotenv()
    return psycopg2.connect(os.environ["DATABASE_URL"])


def main():
    parser = argparse.ArgumentParser(description="Run Stage 1 reconciliation for one episode/day.")
    parser.add_argument("--episode-id", type=int, required=True)
    parser.add_argument("--day-offset", type=int, required=True)
    parser.add_argument(
        "--kpi", choices=["revenue", "active_customers_definitional", "active_customers_calendar"],
        default="revenue",
    )
    args = parser.parse_args()

    conn = _connect()
    try:
        with conn.cursor() as cur:
            if args.kpi == "revenue":
                print(reconcile_conflicting_values(cur, args.episode_id, args.day_offset))
            elif args.kpi == "active_customers_definitional":
                start_date = _fetch_episode_start_date(cur, args.episode_id)
                for row in reconcile_definitional_active_customers(cur, args.episode_id, args.day_offset, start_date):
                    print(row)
            else:
                start_date = _fetch_episode_start_date(cur, args.episode_id)
                print(reconcile_calendar_misaligned_active_customers(cur, args.episode_id, args.day_offset, start_date))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
