# Remediation Plan — Audit Findings, Fix Work-Orders, and Deadline Triage

**Written:** 2026-08-29. **Deadline:** 2026-08-30 23:59.
**Deliverables due:** recorded demo video + PPT + report + public GitHub repo.

**How to use this document:** it is written to be executed by a session with **no prior
context**. Read §0 first (it tells you the exact state of the working tree — some fixes are
already applied and uncommitted). Each finding in §2-§5 is a self-contained work order with:
reproduction command → exact fix → verification command → effort. Work top-down through §8's
triage order, not through the finding numbers.

**Evidence standard:** every finding was verified by running code or querying live Neon.
Findings marked **[CONFIRMED]** have real reproduction output recorded inline. Nothing was
inferred from reading code alone.

---

## 0. STATE OF THE WORKING TREE — READ THIS FIRST

**Branch:** `feature/remediation-tier1` (created off `develop`). **Nothing is committed yet.**

```bash
git branch --show-current     # → feature/remediation-tier1
git status --short
```

### Already applied and verified ✅

| Finding | Files changed | Verified? |
|---|---|---|
| **F1** ranking bug | `stage03_cross_kpi_correlation/priority.py`, `test_stage3.py` | ⚠️ code written, `test_stage3.py` **not yet run** |
| **F2** ID collision | `simulator/layer2_observed_sources/views.sql` | ✅ **fully verified live** — see below |
| **F9** materiality keys | `stage01_reconciliation_ingestion/materiality.py` | ✅ `test_reconcile.py` → OK |

**F2 was applied to the LIVE shared Neon database** (`psql -f views.sql`). Teammates share that
DB — tell them. Verified result: synthetic-duplicate collisions **348,123 → 0**, intentional
near-misses **25,013 preserved**.

### Half-done — FINISH THIS FIRST ⚠️

| Finding | Files changed | State |
|---|---|---|
| **F3** dead relationship graph | `stage03_cross_kpi_correlation/stage2_bridge.py`, `stage3.py` | Code written, **never executed or verified**. The verification run was interrupted. |

**Your first action in the new chat** is to run F3's verification (§2, F3) and confirm
`KNOWN_RELATIONSHIP` evidence now appears. If it doesn't, the fix is wrong and must be debugged
before anything else — everything in Stage 2's Layer 4/5 depends on it.

### Test status after the current edits

```
test_reconcile.py   → OK   (run after the materiality change)
test_stage2.py      → OK   (run after the materiality change)
test_stage3.py      → NOT RUN since F1/F3 edits   ← run this
test_stage4.py      → NOT RUN since F2 edit       ← run this
```

### Known regression introduced by F3 — decide before committing

F3's fix makes Stage 3 call `run_stage2` **three times** per episode instead of twice (upstream
pass → downstream with context → upstream re-scored with context). Combined with the two
`load_dollar_residuals` calls that's **5 full ingestion passes**, up from 4 — roughly **25%
slower**. A 40-day Stage 3 run measured **~50 s before** the change; expect ~65 s after.

This makes **F13 (timeline caching)** matter more than its P4 label suggests — if the demo feels
slow on camera, do F13. Alternative: drop the third pass (upstream re-scored) and accept
one-directional relationship evidence; halves the added cost, still fixes the dead path.

### Untracked file that is NOT mine and is STALE

`docs/02-stage-design-reports/stage5a-implementation-plan.md` (257 lines, untracked) predates the
real build and repeats **exactly the stale assumptions** already documented for the Stage 4
design report: a `conversion` KPI that has never existed, `North`/`Enterprise` taxonomy that does
not match the real schema (`New/Returning/VIP`, 27 Brazilian state codes, 4 Olist categories),
and ISO-date windows where the real contract uses integer `day_offset`s. It also references
`stage4-implementation-plan.md`, a filename that does not exist in this repo.

**Do not implement Stage 5a from that document as written.** Treat it the way
`.claude/plans/stage4-dimensional-decomposition.md` treated the Stage 4 design report: mechanism
useful, specifics wrong.

---

## 1. Where we stand vs. the brief, and the time budget

From `docs/00-brief-and-topology/round2-topology-and-brief.md` §1 — the brief's **minimum
prototype checklist**:

| Brief requirement | Required | Built | Status |
|---|---|---|---|
| KPIs | 3-5 | **2** | ❌ **below minimum** |
| Sources | 2-3 | 3 | ✅ |
| Semantic contract | yes | exists but not wired to logic (F8) | ⚠️ |
| Personas | 2+ | **0** | ❌ |
| Specific test scenarios | yes | per-stage `test_*.py` + live-DB checks | ✅ |
| LLM-vs-non-LLM cost/call breakdown | yes | **none** | ❌ |
| Runtime telemetry | yes | **none** | ❌ |

**Pipeline: 4 of 11 stages built.** Stages 5a, 5b, 5c, 6, 7, 8, 9, 10, 11 do not exist.

### Time budget — three of four deliverables are not code

| Block | Hours | Notes |
|---|---|---|
| Code (Tier 1 + Tier 2) | ~9 | hard stop |
| Report | ~2.5 | §10 |
| PPT | ~2 | §10 |
| Video record + edit | ~2.5 | §9 gives the exact run order |
| Buffer / sleep | rest | |

**The strategic call, from the brief's own §3 differentiation analysis:** every team reading this
brief converges on the same architecture, so "we thought of the shape" is not a differentiator.
The named separation levers are (a) real numbers instead of prompt-faked ML, (b) depth on
**Stage 5b (confounded-cause decomposition)** which one-week teams skip, (c) an original demo
scenario, (d) a judge-directed demo.

**Nine shallow stages serve none of those and create nine surfaces for a judge to poke.** Four
genuinely-working stages plus an honest status table scores higher. §8 triages accordingly.

---

## 2. P0 / P1 — bugs and dead code (work orders)

### F1 — Prioritization ranked the worst incidents last **[CONFIRMED]** — *fix written, unverified*

**File:** `pipeline/stage03_cross_kpi_correlation/priority.py:37`

**Root cause:** `priority_score` is a **signed** dollar delta (`sum(residuals)`), so a collapse is
a large negative and an upward blip is a small positive. `sorted(..., reverse=True)` on the raw
signed value puts the catastrophe last.

**Reproduction before fix (actually run):**
```
RANKING ORDER (should be worst-impact first):
  1. nothingburger   priority_score=+900.0
  2. catastrophe     priority_score=-500000.0
```

**Why it matters:** brief objective #1 is literally *"detect and **prioritize** material KPI
movement."* Live episode 8 already emits `priority_score=-16975.45`.

**Fix applied:** rank by `abs(priority_score)`; new `direction()` helper returns `DROP`/`SPIKE`
so the sign is carried forward rather than lost.

**Verify:**
```bash
cd pipeline/stage03_cross_kpi_correlation && .venv/bin/python test_stage3.py   # must print OK
```
The new `test_rank_puts_biggest_dollar_impact_first_regardless_of_sign` asserts the collapse
outranks the blip.

**Follow-on (not yet done):** nothing consumes `direction()` yet. Stage 11 narration (§6) should
use it so the story says "dropped" vs "spiked" instead of quoting a signed number.

---

### F2 — Synthetic duplicate customer IDs collided with real ones **[CONFIRMED]** — *fixed & verified*

**File:** `pipeline/simulator/layer2_observed_sources/views.sql` (`v_crm_customer_mapping`)

**Root cause:** `900000 + c.customer_id`. Real `customer_id` runs **1..1,237,910**, so the fake
"second account" id landed inside the real id range.

**Reproduction before fix (live SQL):** `348123` colliding ids.

**Why it matters:** this view exists to demonstrate Scenario 6 (entity/join-key mismatch). Its
answer key was corrupt — any identity-resolution logic would have been scored against garbage.

**Fix applied:** derive the offset from `MAX(customer_id)` instead of hardcoding, so it stays
correct as the dataset grows.

**Verified after fix:**
```
duplicate_rows_colliding_with_real_customers = 0        (was 348,123)
intentional_near_misses                      = 25,013   (preserved — these SHOULD point at a
                                                         real different customer; that IS the scenario)
```

**Note:** the live shared DB has already been updated. Anyone else on this DB gets the new view.

---

### F3 — Stage 2's Relationship Graph (Layer 5) is structurally dead **[CONFIRMED]** — *fix written, UNVERIFIED*

**Files:** `stage02_significance_detection/stage2.py:37` (the `other_kpi_candidates` parameter),
`stage03_cross_kpi_correlation/stage2_bridge.py:46`, `stage3.py`

**Root cause:** `run_stage2(..., other_kpi_candidates=None)` defaults to `{}` and **no caller
anywhere passed it.** Stage 2's own docstring (lines 38-41) asks callers to thread it through;
nobody implemented the caller side.

**Consequence chain:** `other_candidates_today` always empty → `business_importance` can never
emit `KNOWN_RELATIONSHIP` → `has_relationship_context` always `False` → `cluster_id` always
`None` → `related_candidates` always `[]`. One whole input axis of `relevance.resolve_relevance`'s
decision matrix is permanently constant.

**Reproduction before fix (live, episode 8, 32 days):**
```
total days analyzed: 32
days with a cluster_id (relationship detected): 0
days with related_candidates: 0
distinct business_importance_evidence types seen: {'KNOWN_BUSINESS_CRITICALITY'}
```

**Fix applied (unverified):** `stage2_bridge.load_stage2_results` now forwards
`other_kpi_candidates`; new `stage2_bridge.candidate_days_by_day()` builds the
`{day: {kpi}}` map; `stage3.run_stage3` does a two-pass wiring so both KPIs see each other.

**⚠️ VERIFY THIS FIRST — the exact command that was interrupted:**
```bash
cd pipeline/stage03_cross_kpi_correlation && .venv/bin/python -c "
import os, psycopg2
from dotenv import load_dotenv
load_dotenv('../../.env')
conn = psycopg2.connect(os.environ['DATABASE_URL']); cur = conn.cursor()
import stage2_bridge
first = stage2_bridge.load_stage2_results(cur, 8, 'active_customers_purchased_30d', list(range(40,72)))
cands = stage2_bridge.candidate_days_by_day(first)
print('upstream candidate days threaded through:', len(cands))
rev = stage2_bridge.load_stage2_results(cur, 8, 'revenue', list(range(40,72)), other_kpi_candidates=cands)
print('evidence types now seen:', {e['type'] for r in rev for e in r.business_importance_evidence})
print('days with cluster_id:', sum(1 for r in rev if r.cluster_id))
conn.close()"
```

**Pass criterion:** `evidence types` must include `'KNOWN_RELATIONSHIP'` and `days with
cluster_id` must be `> 0`. If it is still 0, debug before proceeding — check that
`candidate_days_by_day`'s filter (`business_importance_level != "NONE"`) actually matches how
Stage 2 marks a candidate day.

**Then add a permanent regression test** to `test_stage3.py` asserting `KNOWN_RELATIONSHIP`
appears at least once on a real episode — the absence of exactly this test is why the bug
survived. Add it to the `__main__` block.

---

### F4 — Identity Resolution never runs in the pipeline **[CONFIRMED]** — *not fixed*

**File:** `pipeline/stage01_reconciliation_ingestion/identity_resolution.py`

Only caller is its own test file. `reconcile.py` never imports it; no stage invokes it. Combined
with F2 (corrupt input data, now fixed), Scenario 6 was never demonstrated end to end.

Also: `ZONES = ("auto_merge", "auto_reject", "ambiguous")` declares three outcomes but
`score_match` can only return two — `auto_reject` is unreachable dead code.

**Two options, pick by time:**
- **(a) ~30 min** — call it from `reconcile.py` so it actually runs and its ambiguous-zone count
  appears in output; delete the unreachable `auto_reject`. Honest and small.
- **(b) ~3 h** — add a second identifying field to Layer 1 (synthetic email/phone with realistic
  typos) so Fellegi-Sunter scoring has something real to weigh. This is what the design doc
  intended and is genuinely demo-worthy. **Requires regenerating data — do not start this after
  hour 6.**

**Recommendation: (a).** With one identifying field there is genuinely no probabilistic matching
to do; the module docstring already says so honestly. Say that on camera rather than faking it.

---

### F5 — Calendar-misalignment reconciliation never reaches Stages 2-4 **[CONFIRMED]** — *not fixed*

**File:** `reconcile.py:171` `reconcile_calendar_misaligned_active_customers`

Called only from `test_reconcile.py` and the Stage 1 CLI. The real pipeline entry point
(`stage02_significance_detection/ingest.py:54-59`) only ever calls
`reconcile_conflicting_values` and `reconcile_definitional_active_customers`. Scenario 5's
calendar alignment never enters the data the rest of the pipeline analyzes.

**Fix:** route it through `ingest.py`, or explicitly document it as demonstrated-in-isolation.
Prefer routing — the brief explicitly grades "mismatched refresh cadences/grains."

**Effort:** ~45 min.

---

### The "built but not wired" summary — the honest scenario count

| Stage 1 Scenario | Code | Tested | **Runs in the pipeline** |
|---|---|---|---|
| 1 — Conflicting values | ✅ | ✅ | ✅ yes |
| 2 — Definitional mismatch | ✅ | ✅ | ✅ yes |
| 3 — Mutable history | ❌ | — | ❌ not built |
| 4 — Gaps (partial only) | ✅ | ✅ | ⚠️ only via the Scenario 1 path |
| 5 — Calendar misalignment | ✅ | ✅ | ❌ **orphaned (F5)** |
| 6 — Entity mismatch | ✅ | ✅ | ❌ **orphaned (F4)** |
| 7 — Silent drift | ❌ | — | ❌ not built |

**Headline: 2 of 7 scenarios are live in the pipeline, not 5.** Say this number honestly in the
report; do not claim 5.

---

## 3. P2 — architecture integrity

### F6 — Nothing is ever persisted **[CONFIRMED]**

```bash
grep -rn "INSERT INTO" pipeline/stage0*/*.py      # → no matches
```

Every stage reads, computes in memory, returns, discards. No `stage1_results`, no
`stage2_results`, no output table anywhere.

**Consequences:** no cross-episode history → no learning/memory service (brief objective #7); no
"compare to past incidents" → **Stage 5c's cold-start analogy handler cannot function at all**;
every run recomputes from scratch (part of why a full sweep takes ~50 s); the demo cannot show
"last week vs today."

**Minimal fix (~2 h):** one table, JSONB payload, avoids designing four bespoke schemas tonight:

```sql
CREATE TABLE IF NOT EXISTS stage_outputs (
    run_id      UUID NOT NULL,
    episode_id  INTEGER NOT NULL REFERENCES episodes(episode_id),
    stage       TEXT NOT NULL,
    kpi_name    TEXT,
    day_offset  INTEGER,
    payload     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_stage_outputs_run   ON stage_outputs(run_id, stage);
CREATE INDEX IF NOT EXISTS idx_stage_outputs_ep    ON stage_outputs(episode_id, stage);
```

Thread a `run_id` through each stage entrypoint; write with `execute_values` and an explicit
`page_size` (project non-negotiable — the default 100 caused a 3.5× slowdown once already).

**CUT for the deadline** unless Tier 1+2 land early — it does not appear on camera.

---

### F7 — Reconciliation is hardcoded per source-pair, not parameterized

**File:** `reconcile.py:102`
```python
def reconcile_conflicting_values(cur, episode_id, day_offset):   # ← no kpi_name, no source args
    billing   = _fetch_billing_revenue(cur, episode_id, day_offset)
    marketing = _fetch_marketing_attributed_revenue(cur, episode_id, day_offset)
```

Three scenarios = three bespoke functions with source names baked into private fetch helpers.
Adding a source or KPI means writing another copy-pasted function.

**Context that makes this defensible-but-still-wrong:** there is exactly **one** real conflict
pair in the current data (revenue: billing vs marketing) — verified, it is the only KPI two
sources report the same construct for. That is *why* it was acceptable; it still blocks F14.

**Fix:** one `reconcile(cur, episode_id, day_offset, kpi_name)` driven by a source registry
mapping `(kpi, source) → (view, column, bias_factor, grain)`. **Do this together with F8 and
F14 — they are one coherent change, not three.**

**Effort:** ~2 h, prerequisite for F14.

---

### F8 — The Semantic Contract is documentation, not logic

`semantic_contract.py:10` describes each source's bias in **prose**
(`"undercounts by ~13% (0.87x)..."`), but `apply_bias_correction:74` hardcodes the numbers
separately:
```python
if source_name == "marketing_system" and metric_name == "attributed_revenue":
    factor = 0.87 if day_offset < n_days // 2 else 0.80
```
Two sources of truth, hand-synced. The brief lists "a semantic contract" as a checklist item;
right now it is a dict nothing reads.

**Fix:** add machine-readable `bias_factor` fields to the contract; have `apply_bias_correction`
read them. Falls out of F7's registry work. **~30 min if done with F7.**

---

### F9 — Materiality thresholds keyed on non-existent KPI names — *FIXED*

`materiality.py:12` keyed on `"active_customers"`, but real reconciled names are
`active_customers_purchased_30d` / `_interacted_30d`. Every call with a real name silently fell
through to `_FALLBACK_THRESHOLD = 0.05` instead of the intended `0.10`.

**Fix applied:** real KPI names added (plus the three new KPIs from F14); unknown names now
**raise** instead of silently defaulting. `test_reconcile.py` → OK.

---

## 4. P3 — quality issues (real, lower urgency)

- **F10 — Stage 4 conflates "no data in window" with "genuinely zero."**
  `decomposer.py:32-38`: a slice with no residuals inside the window reports
  `expected=0.0, observed=0.0` — identical to a slice that genuinely had zero revenue. Should
  emit `None` plus an explicit signal. (~30 min)
- **F11 — Stage 2 eligibility is one verdict for a whole timeline**, applied to every day
  (`stage2.py:48,59`). A KPI with a March gap is marked degraded in December. Acceptable for a
  prototype; **document it** rather than leave it implicit. (docs only)
- **F12 — Stage 3's `grouping_basis` attribution is asymmetric** — already documented in
  `stage03/README.md`. A lone `revenue` window gets a coarser reason than a lone
  `active_customers` window. (docs only)
- **F13 — Every KPI timeline is ingested twice (now 2.5×) per Stage 3 run.** Cause of the ~50 s
  (now ~65 s) runtime. **Promoted in importance by F3's regression** — do it if the demo drags.
  Fix: memoize `load_kpi_timeline` per `(episode_id, kpi, day_range)`. (~45 min)

---

## 5. P4 — scope gaps vs the brief

- **F14** — only 2 KPIs; minimum is 3-5. See §6.
- **F15** — 0 personas; brief requires 2+. See §6.
- **F16** — no telemetry, no LLM-vs-non-LLM cost breakdown. See §6.
- **F17** — Stages 5a-11 unbuilt (9 stage-units).
- **F18** — no frontend. The brief's deliverable is a video, not a dashboard — **do not build one.**

---

## 6. The three additions that clear brief checklist items

### 6.1 — F14: KPI expansion, 2 → 7

Grounded in what the database already contains. **KPIs 3-5 need no new reconciliation logic —
they come from views that already exist.**

| # | KPI | Formula | Work needed |
|---|---|---|---|
| 1 | `revenue` | `SUM(quantity * unit_price)` | ✅ exists |
| 2 | `active_customers_purchased_30d` | `COUNT(DISTINCT customer_id)` trailing 30d | ✅ exists |
| 3 | `orders_count` | `COUNT(*)` | ✅ **already a column in `v_billing_daily_revenue`** — just declare it |
| 4 | `avg_order_value` | `revenue / orders_count` | ✅ **already a column** (`avg_order_value`) |
| 5 | `units_sold` | `SUM(quantity)` | one column added to an existing view |
| 6 | `support_ticket_rate` | tickets per active customer, daily | one new view over `support_tickets` (765K rows, populated) |
| 7 | `conversion_rate` | `daily_state.conversion_rate` | one new view; **this is the KPI the original design docs assumed existed** |

**Where to declare each one** (all four must agree or you get F9-class silent bugs):
1. `stage02_significance_detection/ingest.py:39` — `KPI_NAMES`
2. `stage01_reconciliation_ingestion/materiality.py` — `DEFAULT_THRESHOLDS` (already seeded for 3-5)
3. `stage02_significance_detection/business_importance.py:9` — `CRITICALITY`
4. `stage04_dimensional_decomposition/dimension_config.py` — `DIMENSION_APPLICABILITY`

**The payoff beyond the checkbox:** it makes the relationship graph real. Today it has one edge
(and that edge was dead until F3). With these KPIs there is a genuine, defensible DAG:

```
conversion_rate ─┐
                 ├─→ orders_count ──→ revenue
active_customers ┘         │
                           └──→ units_sold
avg_order_value ───────────────→ revenue
support_ticket_rate ──→ (satisfaction) ──→ active_customers
```

Declare it in `stage02/relationship_graph.py` and `stage03/dag.py` (both currently hold one
edge). **This is also the precondition for Stage 5b** — a confounded-cause decomposer needs ≥2
candidate causes to disentangle, which a 2-KPI universe cannot produce.

**Dimensions are the one part that is not broken:** `region` (27 real Brazilian state codes),
`segment` (New/Returning/VIP), `product` (4 Olist categories) — real, live, tested in Stage 4.

**Effort:** ~2 h for KPIs 3-5 (meets the brief minimum at 5). +1.5 h for 6-7.

---

### 6.2 — F15/F17: Stage 11 (LLM narration) + Stage 10 (personas)

**Highest demo payoff per hour of anything left**, and clears two checklist items at once.

- Stage 11 is the **only** place an LLM is permitted (CONSTITUTION.md non-negotiable #4). It
  receives an already-decided structured result and writes prose. It must not decide
  significance, cause, or ranking.
- Stage 10 = same finding, two prompts: **Executive** (impact, action, owner) vs **Analyst**
  (method, confidence, caveats). The brief requires genuinely different narrative *and different
  recommended action* per role — not just more/less detail.

**Build shape:** `stage11_narration/narrate.py` takes a `DecompositionResult` +
`StageThreeResult`, renders a compact JSON fact-sheet, and asks the model to narrate **only from
those facts**. Include `direction()` from F1 so it says "dropped"/"spiked". Use the current
Claude model IDs; check the `claude-api` skill for exact IDs and pricing before writing the call.

**Guardrail to demo on camera:** run it once with the LLM disabled and show the pipeline still
produces the full structured diagnosis — proving the LLM is decoration, not the brain.

**Effort:** ~2.5 h for both.

---

### 6.3 — F16: telemetry + LLM cost ledger

Cheap *because* the count is currently zero, and it is the project's headline claim made
measurable: **0 LLM calls in Stages 1-4, N in Stage 11.**

Minimal: a `telemetry.py` with a module-level counter dict, incremented per stage entry, plus
`llm_calls` / `input_tokens` / `output_tokens` / `estimated_cost_usd` recorded by Stage 11. Print
a summary table at the end of the demo script.

**Effort:** ~45 min.

---

## 7. Demo script — build this, it IS the video

A working prototype is **already in the repo** at `demo/run_demo.py` (untracked — `git add` it).
It runs today and prints Layer 1 → Layer 2 → Stage 1 → Stage 2 → Stage 3 → Stage 4 →
ground-truth cross-check for episode 8.

Run it with Stage 4's venv (it imports across stages via the bridge modules):
```bash
cd pipeline/stage04_dimensional_decomposition && .venv/bin/python ../../demo/run_demo.py
```
Note it hardcodes `REPO = "/Users/sufi_spryzen/Knowledge Base/..."` — make that a relative path
before committing.

**Upgrade it to:**
1. Take `--episode-id` so a judge can pick a different episode live.
2. Show the reconciliation ladder resolving a **real** billing-vs-marketing conflict.
3. Show Stage 2 **declining** on a noise episode → "normal variation, no story" (brief objective
   #5, and one of the strongest things this system does).
4. Show Stage 3 clustering + the **corrected** ranking (F1).
5. Show Stage 4's slice table.
6. Show Stage 11's two persona narratives.
7. Print the telemetry/cost table.
8. Print the ground-truth cross-check **including where the pipeline missed** — see §9.

**Episode selection:** episode 8 has a severe `marketing_cut` at day 52 (no end) plus a
`competitor_launch` at days 77-100 affecting segment `New` — two overlapping causes, which is the
closest thing available to a Stage 5b story. Episode 21 has a severe `marketing_cut` at days
76-87 also affecting `New`. Verify current behaviour before scripting around either.

---

## 8. Triage order — what to do, in order

### Tier 1 — correctness (~3 h). Do all of it.
1. **Verify F3** (§2) — the interrupted step. If broken, fix before anything else.
2. Run `test_stage3.py` and `test_stage4.py`; both must print OK.
3. **F16** telemetry + cost ledger (45 min).
4. Commit, PR into `develop`, merge.

### Tier 2 — brief compliance (~5 h)
5. **F7 + F8 + F14 as one change** → parameterized reconciliation, machine-readable contract,
   KPIs 3-5. **Reaches the brief's 5-KPI minimum.**
6. **F14 continued** → KPIs 6-7 and the real DAG (also unblocks any 5b story).
7. **§6.2** Stage 11 + Stage 10 personas.

### Tier 3 — only if Tier 1+2 land clean
8. F13 caching (if the demo drags), F4(a), F5, F6 persistence, F10.

### Consciously cut — and say so out loud
Stages 5b, 5c, 6, 7, 8, 9; F4(b); any frontend.

---

## 9. How to present the gaps (this is what protects you)

Do **not** present 11 stages and hope nobody asks. Present:

- **4 stages built, tested, running on real data**, with live-verified findings — including bugs
  found *by querying live output rather than trusting the code*. This project has a real track
  record of exactly that: VIP-segment skew, reliability > 1.0, the active-customer definitional
  inconsistency, and now F1/F2/F3.
- **An honest build-status table** for stages 5-11. `.claude/reference/architecture.md` already
  maintains one — put it in the report verbatim.
- **The hard architectural rule, as a measured number:** 0 LLM calls in Stages 1-4.
- **A miss, shown deliberately.** In the episode-8 trace, Stage 2 flagged days 45-46 while the
  real injected event starts day 52 — the flag was ordinary volatility, and the real
  marketing-cut was *not* caught because it slowed growth rather than causing an absolute
  decline. Showing this, and explaining why the system correctly refused to claim a cause it
  could not evidence, is far stronger than a demo where everything conveniently works. It is
  also the honest form of brief objective #5 (communicate uncertainty / abstain).

**Threshold honesty.** Every threshold is a prototype knob except one. Do not claim otherwise:

| Threshold | Value | File | Origin |
|---|---|---|---|
| materiality (revenue / customers) | 0.05 / 0.10 | `materiality.py` | design-doc convention, untested |
| baseline window | 14 d | `baseline.py:10` | arbitrary reasonable default |
| eligibility minimums | 30 / 10 | `eligibility.py:12-13` | design-doc convention |
| **candidate rate** | **0.30** | `candidate_selection.py:15` | ✅ **empirically calibrated** against a real injected event (episode 137); 0.15 provably never fired on a genuine ~50% sustained drop |
| persistence day-counts | 3 / 10 | `classification.py:12-13` | design doc says outright "can later be calibrated" |
| relevance cutoffs | 0.98/0.90/0.70 | `relevance.py:5-7` | design-doc convention |

The defensible claim is: *"the machinery is calibratable, one threshold is already calibrated
against ground truth, the rest are labelled prototype defaults in the code itself."* Claiming
false precision is what actually loses marks.

---

## 10. Report & PPT outline (maps to the brief's 8 objectives)

**Report** — one section per objective, each stating *built / partial / not built* explicitly:
1. Detect & prioritize material KPI movement → Stages 2+3, **mention the F1 ranking fix**
2. Reconcile heterogeneous sources → Stage 1, **2 of 7 scenarios live** (§2 table)
3. Rank likely drivers → Stage 4 descriptive only; **5a-7 not built** — say so
4. Persona narratives → Stage 10/11 if §6.2 lands, else not built
5. Uncertainty / abstention → **strongest section**: eligibility gates, `PROJECTED_UNAVAILABLE`,
   `unusualness_percentile: None`, "normal variation, no story"
6. Actions grounded in levers/decision rights → not built
7. Learn from feedback → not built (needs F6)
8. Security / cost / latency / scalability → telemetry from §6.3; cost table; note the ~65 s
   full-episode runtime honestly

**PPT** ~10 slides: problem → architecture (the 11-stage mermaid from CONSTITUTION.md) → what's
built (status table) → the LLM boundary as a number → live demo screenshots → **the honest miss**
→ what we'd build next (5b first, and why) → threshold calibration story.

---

## 11. Process failures that caused this, recorded so they don't repeat

- Four stage plans were executed in sequence without ever re-checking the aggregate against the
  brief's own checklist. The KPI-count gap (F14) was visible in our own docs from day one.
- Scenarios 5 and 6 and identity resolution were built to passing tests and reported complete
  **without ever being wired into the pipeline.** F3/F4/F5 are all cases where the test passes
  and the code is dead. **A passing `test_*.py` is not evidence that a stage runs.**
- **Process fix, mandatory for every future stage plan:** an acceptance criterion of the form
  *"prove it runs end to end in the real pipeline, not just in its own test,"* and at least one
  live test asserting an output that only appears if the wiring is real (F3's
  `KNOWN_RELATIONSHIP` assertion is the template).
