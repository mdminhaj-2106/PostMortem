"""End-to-end pipeline demo: Layer1/2 -> Stage1 -> Stage2 -> Stage3 -> Stage4,
against a real episode with a real injected event, cross-checked at the end
against injected_events (offline scoring only -- never fed to the pipeline).

Episode 8: severe marketing_cut, day_offset 52 onward (no end -- persists),
magnitude~0.50, applies evenly across segments -- a real ground-truth-labeled
event this pipeline was never told about.

Run from pipeline/stage04_dimensional_decomposition/ with its own .venv:
    .venv/bin/python /path/to/e2e_demo.py
"""
import importlib
import os
import sys

import psycopg2
from dotenv import load_dotenv

import telemetry

# Derived from this file's location (demo/run_demo.py), not hardcoded -- the absolute
# path this started life with only worked on one machine, and the repo is a graded
# public deliverable.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE1_DIR = os.path.join(REPO, "pipeline", "stage01_reconciliation_ingestion")

load_dotenv(os.path.join(REPO, ".env"))
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

EPISODE_ID = 8
EVENT_START = 52


def hr(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------------------
hr(f"LAYER 1 -- ground truth (held out), raw orders on day {EVENT_START} (real event onset)")
cur.execute("SELECT COUNT(*), SUM(quantity*unit_price) FROM orders WHERE episode_id=%s AND day_offset=%s", (EPISODE_ID, EVENT_START))
print(f"orders_count, revenue on day {EVENT_START}:", cur.fetchone())

hr("LAYER 2 -- v_billing_daily_revenue (what the pipeline actually ingests) around the event")
cur.execute("""SELECT day_offset, revenue, orders_count FROM v_billing_daily_revenue
               WHERE episode_id=%s AND day_offset BETWEEN %s AND %s ORDER BY day_offset""",
            (EPISODE_ID, EVENT_START - 3, EVENT_START + 4))
for row in cur.fetchall():
    print(row)

# ---------------------------------------------------------------------------
hr(f"STAGE 1 -- reconciliation, revenue on day {EVENT_START} (billing vs marketing cross-check)")
sys.path.insert(0, STAGE1_DIR)
reconcile = importlib.import_module("reconcile")
with telemetry.stage("Stage 1 - reconciliation"):
    rv = reconcile.reconcile_conflicting_values(cur, EPISODE_ID, EVENT_START)
print(rv)

# All registry-declared KPIs through the ONE parameterized reconciler (F7/F14) -- adding
# a KPI is a row in reconcile.SOURCES, not another bespoke function.
print(f"\nAll {len(reconcile.SOURCES)} registry-declared KPIs reconciled on day {EVENT_START} "
      f"(+ active_customers_purchased_30d via Scenario 2 = 5 KPIs):")
print(f"  {'kpi':<20} {'value':>12}  {'tier':<14} sources")
for kpi_name in reconcile.SOURCES:
    r = reconcile.reconcile(cur, EPISODE_ID, EVENT_START, kpi_name)
    print(f"  {kpi_name:<20} {r.value:>12.2f}  {r.confidence_tier:<14} {r.source_provenance}")
sys.path.remove(STAGE1_DIR)
for name in ("reconcile", "models", "materiality", "calendar_dimension", "semantic_contract"):
    sys.modules.pop(name, None)

# ---------------------------------------------------------------------------
hr("STAGE 2 -- significance detection, revenue & active_customers classification around the event")
sys.path.insert(0, os.path.join(REPO, "pipeline", "stage02_significance_detection"))
stage2 = importlib.import_module("stage2")
DAY_RANGE = range(EVENT_START - 15, EVENT_START + 20)
with telemetry.stage("Stage 2 - significance detection"):
    s2_revenue = stage2.run_stage2(cur, EPISODE_ID, "revenue", day_range=DAY_RANGE)
    s2_active = stage2.run_stage2(cur, EPISODE_ID, "active_customers_purchased_30d", day_range=DAY_RANGE)
for r in s2_revenue:
    print(f"day {r.day_offset:3d}  revenue  state={r.classification_state:11s} "
          f"unusualness={r.unusualness_score} confidence={r.confidence}")
print()
for r in s2_active:
    print(f"day {r.day_offset:3d}  active_customers  state={r.classification_state:11s} "
          f"unusualness={r.unusualness_score} confidence={r.confidence}")
for name in ("models", "ingest", "baseline", "eligibility", "unusualness",
             "candidate_selection", "business_importance", "relationship_graph",
             "relevance", "classification", "stage2"):
    sys.modules.pop(name, None)
sys.path.remove(os.path.join(REPO, "pipeline", "stage02_significance_detection"))

# ---------------------------------------------------------------------------
hr("STAGE 3 -- cross-KPI correlation & prioritization")
sys.path.insert(0, os.path.join(REPO, "pipeline", "stage03_cross_kpi_correlation"))
stage3 = importlib.import_module("stage3")
with telemetry.stage("Stage 3 - cross-KPI correlation"):
    s3_results = stage3.run_stage3(cur, EPISODE_ID, day_range=DAY_RANGE)
for r in s3_results:
    print(r)
for name in ("models", "dag", "grouping", "priority", "stage2_bridge", "stage3"):
    sys.modules.pop(name, None)
sys.path.remove(os.path.join(REPO, "pipeline", "stage03_cross_kpi_correlation"))

# pick the cluster/result overlapping the real event onset (day 52, no end -- persists)
target = next(
    (r for r in s3_results if r.window_end_day_offset >= EVENT_START),
    s3_results[0] if s3_results else None,
)
print("\n>> decomposing:", target)
if target is None:
    print("Stage 2/3 found nothing significant in this window -- 'normal variation, no story.' Exiting.")
    conn.close()
    sys.exit(0)

# ---------------------------------------------------------------------------
hr("STAGE 4 -- dimensional decomposition (segment breakdown)")
sys.path.insert(0, os.path.join(REPO, "pipeline", "stage04_dimensional_decomposition"))
import stage4  # noqa: E402
with telemetry.stage("Stage 4 - dimensional decomposition"):
    result = stage4.run_stage4(cur, EPISODE_ID, target)

print(f"{'KPI':<32} {'dim':<8} {'slice':<10} {'expected':>10} {'observed':>10} {'dev%':>8} {'pctile':>8} {'eligibility'}")
for s in sorted(result.slices, key=lambda s: (s.dimension, s.kpi_name, s.slice_value)):
    dev = f"{s.deviation_pct*100:.1f}" if s.deviation_pct is not None else "n/a"
    pct = f"{s.unusualness_percentile:.2f}" if s.unusualness_percentile is not None else "None"
    print(f"{s.kpi_name:<32} {s.dimension:<8} {s.slice_value:<10} {s.expected:>10.1f} {s.observed:>10.1f} {dev:>8} {pct:>8} {s.eligibility}")

# ---------------------------------------------------------------------------
hr("GROUND TRUTH CROSS-CHECK (offline scoring only -- injected_events, never fed to pipeline)")
cur.execute("""SELECT event_type, severity, onset_type, start_day_offset, end_day_offset,
                      magnitude, affected_segment, affected_product_id
               FROM injected_events WHERE episode_id=%s""", (EPISODE_ID,))
for row in cur.fetchall():
    print(row)

print("\nThe real event has no affected_segment (applies ~evenly) -- checking Stage 4 agrees,")
print("i.e. no segment is spuriously singled out as the cause:")
segment_slices = [s for s in result.slices if s.dimension == "segment"]
for s in sorted(segment_slices, key=lambda s: (s.kpi_name, -(s.deviation_pct or -999))):
    dev = f"{s.deviation_pct*100:+.1f}%" if s.deviation_pct is not None else "n/a"
    print(f"  {s.kpi_name:<32} {s.slice_value:<10} deviation={dev:>8}  eligibility={s.eligibility}")

print("\nRegion-level deviation_pct, biggest movers first (this event applies company-wide,")
print("so we expect the deviation to track region SIZE, not single out one region as special):")
region_slices = [s for s in result.slices if s.dimension == "region"]
for s in sorted(region_slices, key=lambda s: -(s.deviation_pct or -999))[:8]:
    dev = f"{s.deviation_pct*100:+.1f}%" if s.deviation_pct is not None else "n/a"
    print(f"  {s.kpi_name:<32} {s.slice_value:<10} observed={s.observed:>9.1f} deviation={dev:>8}  eligibility={s.eligibility}")

# ---------------------------------------------------------------------------
hr("TELEMETRY & LLM COST LEDGER (audit finding F16)")
telemetry.print_summary()

conn.close()
