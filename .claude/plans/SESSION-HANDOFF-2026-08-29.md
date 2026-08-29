# Session Handoff — 2026-08-29

**Read this with `.claude/plans/remediation-audit-and-fix-plan.md`.** That file is the audit;
this file is what actually got done, what is half-done, and exactly where to resume.

**Deadline:** 2026-08-30 23:59. Deliverables: recorded demo video + PPT + report + public repo.

---

## 0. EXACT STATE OF THE TREE — READ FIRST

**Branch:** `feature/remediation-tier1`. **PR #16** open against `develop`:
https://github.com/mdminhaj-2106/PostMortem/pull/16 — **not merged, deliberately** (user's call).

### Committed and pushed (7 commits, all on origin)

```
41a93b9  fix: Stage 4 must not report unmeasured slices as measured zeros (F10)   <- last pushed
7159d0a  fix: make Scenario 6 identity resolution actually run; drop unreachable zone (F4a)
4e64e09  fix: route Scenario 5 (calendar misalignment) into the pipeline (F5)
edbfc11  feat: complete Scenario 2 — expose active_customers_interacted_30d (KPI 6)
38c9816  feat: parameterized reconciliation + machine-readable contract + KPIs 2->5 (F7/F8/F14)
edfd454  perf: memoize reconciled days (F13) — Stage 3 111.3s -> 49.9s
b955182  fix: remediation Tier 1 — dead relationship graph, ranking, ID collision, telemetry
```

Everything through `41a93b9` is pushed. Commit messages are detailed — read them, they carry
the reasoning.

### ⚠️ UNCOMMITTED AND UNVERIFIED — THIS IS WHERE YOU RESUME

```
 M pipeline/stage03_cross_kpi_correlation/dag.py
 M pipeline/stage03_cross_kpi_correlation/grouping.py
 M pipeline/stage03_cross_kpi_correlation/stage3.py
 M pipeline/stage03_cross_kpi_correlation/test_stage3.py
```

This is **Task 5 (Stage 3 iterates the DAG)**, written but **`test_stage3.py` has NOT been run
since the new tests were added**. See §3 for the exact resume step.

### Untracked, deliberately NOT committed

`docs/02-stage-design-reports/stage5a-implementation-plan.md` — stale, predates the real build,
not written by this project. Audit §0 says do not implement Stage 5a from it. Leave it alone.

---

## 1. Live database changes (SHARED Neon — tell teammates)

Two changes were applied to the shared DB this session. Both are `CREATE OR REPLACE VIEW`,
applied by executing `views.sql` via psycopg2 (**`psql` is NOT installed on this machine** —
exit 126; use the python path below).

1. **F2** (pre-existing, from before this session) — `v_crm_customer_mapping` duplicate-account
   offset derived from `MAX(customer_id)` instead of hardcoded `900000`.
2. **F14 (this session)** — `v_billing_daily_revenue` gained a `units_sold` column
   (`SUM(o.quantity)`), appended last because `CREATE OR REPLACE VIEW` can only append.

To re-apply views:
```bash
cd pipeline/stage04_dimensional_decomposition && .venv/bin/python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv('../../.env')
sql = open('../../pipeline/simulator/layer2_observed_sources/views.sql').read()
conn = psycopg2.connect(os.environ['DATABASE_URL']); cur = conn.cursor()
cur.execute(sql); conn.commit(); print('applied')"
```

---

## 2. What was done, by task

### Tier 1 (audit §8) — COMPLETE

| Finding | Status | Notes |
|---|---|---|
| **F3** dead relationship graph | ✅ | **The audit's fix was only half the bug.** Threading worked but `related_kpis("revenue")` returned `[]` because `RELATIONSHIPS` declared only forward edges. Fixed by deriving the reverse edge inside `related_kpis` so one declaration serves both directions. Live ep8 d40-72: `KNOWN_RELATIONSHIP` absent → present, `cluster_id` days 0 → 4. |
| **F1** ranking | ✅ | ranks by `abs(priority_score)`; `direction()` carries DROP/SPIKE. |
| **F2** ID collision | ✅ | was already applied to live DB. |
| **F9** materiality keys | ✅ | unknown names now raise. |
| **F16** telemetry | ✅ | `demo/telemetry.py`, measured from the **caller** so no stage needs a 5th sys.path hack. Prints `0 LLM calls in Stages 1-4`. |
| **F13** caching | ✅ | `ingest.load_kpi_timeline` memoized **per day** (not per range, so overlapping windows hit). Stage 3 **111.3s → 49.9s**; demo 174.6s → 112.8s. |

### Sequential Stage 1-4 completion (user asked to go in order)

| # | Task | Status |
|---|---|---|
| 1 | Expose `active_customers_interacted_30d` (KPI 6) | ✅ `edbfc11` |
| 2 | **F5** route calendar misalignment into pipeline | ✅ `4e64e09` |
| 3 | **F4a** identity resolution runs + drop `auto_reject` | ✅ `7159d0a` |
| 4 | **F10** Stage 4 unmeasured ≠ zero | ✅ `41a93b9` |
| 5 | **Stage 3 iterates the DAG** | ⚠️ **WRITTEN, UNVERIFIED — RESUME HERE** |
| 6 | Stage 4 slices the new KPIs (needs 3 more sliced views) | ❌ not started |

---

## 3. RESUME HERE — Task 5 verification

The code is written. **The only thing not done is running the test.**

```bash
cd pipeline/stage03_cross_kpi_correlation && .venv/bin/python -u test_stage3.py   # must print OK
```

If it passes, run the other three suites, then commit. If it fails, debug before anything else.

### What Task 5 changed

- **`dag.py`** — 1 edge → **5 edges**, plus new `edges()` and `kpis()` helpers.
  Lag reflects edge *kind*: arithmetic composition (`revenue = orders × AOV`, `units_sold`)
  gets `(0, 1)`; behavioural drive (`customers → orders`) keeps `(0, 3)`.
- **`grouping.py`** — new `windows_link(a_window, a_res, b_window, b_res, dag_entry)` returning
  `(linked, adjacent)`. `adjacent` is reported separately so "nothing was near it" is
  distinguishable from "something was near it and the evidence refuted it". `attempt_cluster`
  is unchanged and still passes its tests.
- **`stage3.py`** — removed hardcoded `_UPSTREAM_KPI`/`_DOWNSTREAM_KPI`. Now:
  - `_score_all_kpis()` — symmetric **two-pass** candidate threading for N KPIs (pass 1 cold,
    pass 2 with the union of everyone else's candidates minus self). Replaces the 3-call
    upstream/downstream/upstream dance that only worked for exactly 2 KPIs.
  - **union-find** over `(kpi, window)` nodes; a confirmed DAG edge unions two windows.
    Connected components = incidents. This is what makes 3+-member clusters possible.
  - cluster confidence = **worst** among members (a cluster is only as good as its shakiest
    evidence).
  - singleton basis logic preserved: `SINGLE_KPI` / `SEPARATE_NO_ADJACENT_KPI` /
    `SEPARATE_NO_CORRELATION`.
- **`test_stage3.py`** — added 4 tests (2 offline, 2 live), all wired into `__main__`:
  - `test_dag_matches_stage2_relationship_graph` (offline) — pins `dag.py` against
    `stage02/relationship_graph.py` so the two copies of the graph can't drift (F9 class).
    Reaches stage2 via `stage2_bridge._stage2.business_importance.relationship_graph`.
  - `test_windows_link_requires_both_lag_and_direction` (offline)
  - `test_multi_member_cluster_on_a_real_episode` (live, **episode 118**, days 21-56)
  - `test_case2_projected_unavailable_occurs_on_real_data` (live, ep 41 / ep 137)
  - Also added `import dag` to the test file's imports.

### Already verified manually (before the test run was interrupted)

`stage3.run_stage3` was run live across 6 event episodes and produces the previously-unreachable
behaviours:

```
ep   8 event@ 52  results= 3  multi-member=0  biggest=1
ep  21 event@ 76  multi=1  ['active_customers_purchased_30d','revenue'] w=72-82 score=-27371.03
ep  41 event@ 71  multi=1  ['orders_count','units_sold'] w=73-73 score=None      <- Case 2!
ep  99 event@ 26  multi=1  ['orders_count','revenue','units_sold'] w=44-45       <- 3 members
ep 118 event@ 36  multi=2  ['active_customers_purchased_30d','orders_count','revenue'] w=29-36
                           ['orders_count','revenue','units_sold'] w=43-45
ep 137 event@ 19  multi=2  ['active_customers_purchased_30d','orders_count'] w=12-19 score=None
                           ['orders_count','revenue','units_sold'] w=20-21
```

Both things the audit called *structurally untestable* now occur on real data:
**3+ member clusters** and **Case 2 (`PROJECTED_UNAVAILABLE`)**.

`test_stage3.py` **did pass** on an earlier run of the rewritten `stage3.py` (before the 4 new
tests were added) — including `test_clusters_a_real_injected_event`, so clustering did not
regress.

---

## 4. Current KPI universe (6) and where each must be declared

`revenue`, `active_customers_purchased_30d`, `active_customers_interacted_30d`,
`orders_count`, `avg_order_value`, `units_sold`

**Four declaration sites must agree** or you get an F9-class silent bug. There is now a test
that enforces it: `test_stage2::test_every_declared_kpi_is_declared_everywhere`.

1. `stage02_significance_detection/ingest.py` → `KPI_NAMES`
2. `stage01_reconciliation_ingestion/reconcile.py` → `SOURCES` (registry; `active_customers_*`
   are exempt — they come from Scenario 2's definitional path, not the registry)
3. `stage01_reconciliation_ingestion/materiality.py` → `DEFAULT_THRESHOLDS`
4. `stage02_significance_detection/business_importance.py` → `CRITICALITY`

Plus, for Stage 4 slicing: `stage04_dimensional_decomposition/dimension_config.py` →
`DIMENSION_APPLICABILITY` (only the original 2 KPIs are declared; the rest return `[]` and are
**skipped cleanly, not crashed** — that is Task 6).

---

## 5. Decisions made this session that you should not silently reverse

- **Chow-Lin / temporal disaggregation is NOT needed and must not be built.** Verified: every
  Layer 2 view reads `FROM orders` or `FROM daily_state` — Layer 1 atomic tables. No view is
  built on another view, so a grain mismatch is always an exact re-bucket, never an estimate.
  The honest claim is *"we kept atomic-grain truth, so disaggregation never arises"* — NOT
  "we solved disaggregation."
- **Layer 2 is 11 SQL views, stored nowhere**, recomputed per query and fully deterministic
  (verified: identical md5 across repeated queries; `hashtext` is a hash, not RNG).
  `source_outages` is the one real Layer 2 table (outage windows can't be recomputed).
- **Stage 3's grouping is a sign-agreement + lag test, NOT a correlation coefficient.** Do not
  describe it as "correlation" in the report. Say *"DAG-constrained lag-and-direction
  co-movement test."*
- **Stage 2 has no STL / seasonal decomposition / changepoint detection.** It is a rolling
  median (14d, min 5), a causal expanding-window percentile, and a consecutive-day run counter.
  `docs/.../stage1-reconciliation-design.md` Scenario 4 implies STL exists — it does not.
- **`candidate_selection.py` computes its cutoff over the WHOLE episode** while
  `unusualness.py` is strictly causal. That is lookahead in a live setting. **Document it, do
  not fix it** — 0.30 is the only empirically calibrated threshold and re-tuning it before the
  demo is the way to break the one thing that works.
- **Identity resolution is reported, NOT applied to any KPI's confidence.** Verified against
  the schema: `crm_account_id` appears in no view except `v_crm_customer_mapping`, and
  `v_crm_weekly_active_customers` counts `DISTINCT customer_id` straight off orders. Wiring it
  into confidence would assert a dependency that does not exist.
- **Weekly/cycle-grain data must not score like daily data.** `active_customers_interacted_30d`
  lands `LOW` confidence by design (only 1 of 7 days is an observation; the rest are
  `partially_imputed`). It is still ANALYZED and reported — Stage 3 just declines to *rank* it.

---

## 6. Bugs found *in the tests themselves* this session

Both were tests asserting wrong behaviour, which is why the bugs survived:

1. `test_stage4::test_decompose_slice_eligible_and_insufficient` asserted
   `insufficient.expected == 0.0` — it **encoded the F10 bug**. Fixed.
2. `test_reconcile::test_scenario6_identity_flags` split duplicates at a hardcoded
   `crm_account_id >= 900000`, but F2 replaced that offset with `MAX(customer_id)` (~1,237,910).
   Real high-id customers would be miscounted as synthetic duplicates; it only passed because
   episode 1's ids sit below the old constant. Now derives the boundary like the view does.

**Process rule (audit §11), still mandatory:** a passing `test_*.py` is NOT evidence a stage
runs. Every fix needs a live test asserting an output that only exists if the wiring is real.

---

## 7. Remaining work, in order

| # | Task | Effort | Notes |
|---|---|---|---|
| 5 | **Verify + commit Task 5** | 15 min | §3. Code written, test unrun. |
| 6 | Stage 4 slices the new KPIs | ~1 h | needs 3 more sliced views (`_by_region/_segment/_product` for orders_count/units_sold), then declare in `DIMENSION_APPLICABILITY` + `slice_fetcher._VIEW_BY_KPI_DIMENSION` |
| — | **Stage 11 narration + Stage 10 personas** | ~2.5 h | audit §6.2. Highest demo payoff left; clears "personas 0 → 2". **Only place an LLM is allowed** (CONSTITUTION #4). Load the `claude-api` skill for current model IDs/pricing before writing the call — `telemetry.record_llm_call` takes rates as arguments precisely so no stale price is baked in. |
| — | Report + PPT + video | ~7 h | audit §9/§10. **Three of four deliverables are not code.** |

**Permanently cut** (say so out loud in the report): Scenario 3 (mutable history — needs
`returned_day_offset` in Layer 1 = regenerating 1.35M orders), Scenario 7 (silent drift),
F6 persistence, Stages 5b/5c/6/7/8/9, any frontend (F18 — the deliverable is a video).

---

## 8. Scenario status — the honest number for the report

| Stage 1 Scenario | Code | Tested | **Runs in pipeline** |
|---|---|---|---|
| 1 — Conflicting values | ✅ | ✅ | ✅ |
| 2 — Definitional mismatch | ✅ | ✅ | ✅ **(fixed this session — both halves now consumed)** |
| 3 — Mutable history | ❌ | — | ❌ not built |
| 4 — Partial gap | ✅ | ✅ | ✅ |
| 4 — Total gap | ❌ | — | ❌ not built |
| 5 — Calendar misalignment | ✅ | ✅ | ✅ **(fixed this session — F5)** |
| 6 — Entity mismatch | ✅ | ✅ | ⚠️ **runs & reports, but affects no KPI value — say this precisely** |
| 7 — Silent drift | ❌ | — | ❌ not built |

**Was 2 of 7 live at the start of this session. Now 4 of 7 fully live + 1 reporting-only.**
Do not claim 7. Do not claim 5 without the Scenario 6 caveat.

---

## 9. Environment gotchas that cost time

- **`psql` is not installed.** Exit 126. Use psycopg2 (§1).
- **`timeout` is not installed** (macOS). `timeout 900 ...` → exit 127, the command never runs.
- Test suites are slow (Neon round trips): `test_stage3` and `test_stage4` are several minutes
  each. Run with `python -u` and `run_in_background: true`; output only appears at completion
  when piped through `tail`.
- Each stage has its **own venv**: `pipeline/stageNN_*/.venv/bin/python`.
- The demo runs from Stage 4's venv:
  `cd pipeline/stage04_dimensional_decomposition && .venv/bin/python ../../demo/run_demo.py`

## 10. Full verification command set

```bash
cd pipeline/stage01_reconciliation_ingestion && .venv/bin/python -u test_reconcile.py   # OK
cd pipeline/stage02_significance_detection  && .venv/bin/python -u test_stage2.py       # OK
cd pipeline/stage03_cross_kpi_correlation   && .venv/bin/python -u test_stage3.py       # <- UNRUN
cd pipeline/stage04_dimensional_decomposition && .venv/bin/python -u test_stage4.py     # OK
cd pipeline/stage04_dimensional_decomposition && .venv/bin/python -u ../../demo/run_demo.py
```

All four printed OK as of commit `41a93b9`. Only `test_stage3.py` is unverified against the
uncommitted Task 5 changes.
