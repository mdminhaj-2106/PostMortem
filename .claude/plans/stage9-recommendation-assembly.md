# Stage 9 — Recommendation Assembly & Action Selection (first slice, reduced scale)

**Design report:** `docs/02-stage-design-reports/stage9-recommendation-assembly-architecture.md`
**Branch:** `feature/stage9-recommendation-assembly` (off `develop`)
**Consumes:** Stage 8 (`Stage8Result`, which already carries a one-entry-per-hypothesis join with Stage 7), Stage 7 (`Stage7Result`, for reason-code/evidence provenance), Stage 4 (`DecompositionResult`, for real target-scope binding via Stage 6's own `flagged_facets`)

## Outcome

For episode 15's real cluster, Stage 9 emits a `Stage9Result` with one primary recommendation (`driver → mechanism → lever → action → owner → decision_intent → expected_impact → monitoring_plan → success_criteria`) plus any genuinely non-dominated alternatives, built entirely from Stage 7/8's real fields plus a small declared cause→mechanism→lever→action config — never a fabricated cost, owner, or historical-effectiveness number. `test_stage9.py` prints `OK` offline, plus one live-DB run against episode 15.

## Real contracts vs. the design doc

1. **Stage 8 already did the Stage 7↔Stage 8 join for you.** `Stage8Result.estimates` is already one `CounterfactualImpact` per Stage 7 `RankedHypothesis` (both `ESTIMATED` and `MECHANISM_UNAVAILABLE`/`UNAVAILABLE` ones — Stage 8's own `run_stage8` never drops a hypothesis, per its own output-schema invariant). Design doc §6/§28's `hypothesis_adapter.py` + a separate per-hypothesis Stage 8 lookup is therefore mostly redundant — **iterate `stage8_result.estimates` directly** as the primary per-hypothesis view; only fall back to `stage7_result.hypotheses` for the fields `CounterfactualImpact` doesn't carry (`confidence_reason_codes`, `supporting_evidence`/`contradicting_evidence`, `rank`/`rank_group`).
2. **"Mechanism" means two different things across Stage 8 and Stage 9 — do not conflate them.** Stage 8's `estimation_reason_codes` (`STAGE5B_QUANTITATIVE_CONSTRAINT`, `BASELINE_RECONSTRUCTION`) describe the *quantitative method used to compute the dollar figure*. Stage 9's own `mechanism` (design doc §13, e.g. `reliability_degradation`) describes *how the cause hurts the business*, used to pick a lever — a completely unrelated concept that happens to share the English word "mechanism." Design doc §7's "mechanism used" field maps to Stage 8's `estimation_reason_codes`, not to anything Stage 9 itself resolves from `mechanism_resolver.py`. State this distinction in the README so nobody merges the two later.
3. **No target-scope (product/region/segment) survives in either Stage 7 or Stage 8's output.** Design doc §17-18 wants every action bound to "the smallest validated scope that covers the diagnosed problem," but neither `RankedHypothesis` nor `CounterfactualImpact` carries a scope field — that information lives only in Stage 4's `DecompositionResult` and Stage 6's `entity_scope_filter.flagged_facets()`. **Fix: reuse Stage 6's real `flagged_facets(decomposition_result)` function directly** (already built, already the same signal Stage 5a's `product_concentration` and Stage 6's own scope filter use) rather than inventing a new scope-detection mechanism. Zero flagged facets is already a legitimate, handled Stage 6 outcome — Stage 9 emits `target_scope={}` (cluster-level, no narrower validated scope) in that case, not a fabricated "Global" scope.
4. **No Learning & Memory, Decision Rights, or company-capability service exists anywhere in this repo** (`architecture.md`: all three `❌ Not yet designed`). Design doc's own fallbacks already anticipate this (§63: missing Learning Memory → `historical_effectiveness=UNKNOWN`, works fine): `historical_effectiveness` is always `UNKNOWN` in this slice; `owner` comes from a small **declared** lever→team table (stated, real domain knowledge, not invented per-episode — see finding below); capability feasibility is a stated stub, always `AVAILABLE` (single-company hackathon demo, no multi-tenant capability system to query).
5. **No rich KPI structural graph exists to filter levers or expand monitored KPIs** — Stage 3's real DAG is a single 2-KPI edge (`architecture.md`'s Known Risks), not the doc's assumed `Traffic → Conversion → Orders → Revenue` chain. Reduced: **one declared lever per mechanism** (no "structural applicability" filtering step — nothing to filter against), and `monitoring.affected_kpis = [the one investigated kpi_name]`, not a propagated multi-KPI set.
6. **`expected_impact` resolves the earlier "is this forward- or backward-looking" question the design doc already answers, plainly: pass Stage 8's number through unchanged, honestly labeled.** §48-49 are explicit: "Stage 9 exposes both counterfactual KPI and estimated impact... never relabel this as guaranteed recovery... remains 'estimated impact'." No new forward-looking projection is built here — that would introduce an unvalidated assumption the design doc itself doesn't ask for. `impact_lower`/`impact_upper` are passed through from Stage 8 unchanged, never narrowed.
7. **`UNKNOWN`-confidence hypotheses do reach Stage 9.** Stage 8's own eligibility gate (`ALLOW_UNKNOWN=False`) excludes them from `ESTIMATED`, but still emits a `CounterfactualImpact` for them with `estimation_status="UNAVAILABLE"` and `stage7_confidence="UNKNOWN"` — Stage 8 never drops a hypothesis from its list. Stage 9's confidence policy must explicitly handle `UNKNOWN` → `INVESTIGATE` (per design doc §31), not assume it never appears.
8. **Multiple levers per mechanism (design doc §14, "intentionally broader than a single action") are out of scope for this slice.** With only 4 real causes, one declared canonical lever per mechanism is enough to demonstrate the full chain without unused branching generality; add more when a real second lever is actually needed for a cause. Action-compatibility conflicts (§38-42, e.g. `PRICE_INCREASE` vs `PRICE_DECREASE`) are **not reachable with this project's real cause vocabulary** — none of the 4 causes' default actions oppose each other (repair reliability / restore marketing spend / investigate competitor / replenish inventory are naturally compatible) — the compatibility check is still built (real, not stubbed out), but its declared conflict table starts empty, stated plainly rather than populated with unused hypothetical pairs.

## Scope

**In:** iterating `Stage8Result.estimates` (all statuses); declared cause→mechanism→lever→atomic-action config (4 rows, one lever each); real target-scope binding via Stage 6's `flagged_facets`; owner from a declared lever→team table; capability feasibility stubbed `AVAILABLE`, context feasibility real (scope-contradiction check); confidence-aware decision intent (`ACT`/`INVESTIGATE`/`MONITOR`, `DEFER` only if a real conflict is ever detected); `historical_effectiveness=UNKNOWN` always; monitoring plan from the one investigated KPI; success criteria `DERIVABLE`/`NOT_DERIVABLE` from Stage 8's `estimation_status`; primary + non-dominated alternatives via a real (if axis-reduced) dominance comparison; output-schema invariants (joint never split, no monetary cost field, no LLM import, Stage 7 ranking never altered).

**Out (stated, not hidden):** multiple levers per mechanism/cause; real historical action-effectiveness (no Learning & Memory to query); real company capability gating (no such service); structural KPI-graph-filtered lever applicability or multi-KPI monitoring propagation (Stage 3's real DAG is one edge); a populated action-compatibility conflict table (none of the 4 real causes' actions actually conflict); effort/time-to-impact metadata (stays `UNKNOWN`, never guessed); FastAPI wiring.

## Files to read first

- `docs/02-stage-design-reports/stage9-recommendation-assembly-architecture.md` — §2-3 locked decisions/principles, §11-46 (decision status, action construction, feasibility, ownership, expected-impact semantics), §69 decision matrix, §101 build order
- `pipeline/stage08_counterfactual_impact/models.py`, `stage8.py`, `stage7_bridge.py` — real `Stage8Result`/`CounterfactualImpact` fields, and the bridge-of-bridges pattern to extend one layer further
- `pipeline/stage07_hypothesis_debate_ranking/models.py` — real `RankedHypothesis` fields not carried onto `CounterfactualImpact` (reason codes, evidence lists, rank/rank_group)
- `pipeline/stage06_evidence_retrieval/entity_scope_filter.py` — the real `flagged_facets(decomposition_result)` function to reuse for target-scope binding
- `.claude/reference/architecture.md` — confirms Decision Rights/Learning & Memory/company-capability are all `❌ Not yet designed`, and the accumulating cross-import-bridge risks list (read before writing this stage's own bridge)

## Files to change/create

```
pipeline/stage09_recommendation_assembly/
├── README.md
├── requirements.txt          (same transitive chain as stage08's, since stage8_bridge.py
│                               re-derives the full upstream stack)
├── models.py                 (ActionCandidate, MonitoringPlan, SuccessCriteria,
│                               Recommendation, Stage9Result -- trimmed of
│                               effort/time_to_impact beyond UNKNOWN placeholders)
├── config.py                 (CAUSE_MECHANISMS, MECHANISM_LEVERS, LEVER_ACTIONS
│                               [atomic_action, default_owner, risk_tier],
│                               ACTION_COMPATIBILITY [starts empty, stated why],
│                               CONFIDENCE_POLICY -- plain Python dicts/tuples,
│                               matching every other stage's cause_config.py style,
│                               not the design doc's YAML files -- no other stage
│                               in this repo loads YAML config)
├── stage8_bridge.py           (re-exports Stage 8's run_stage8 plus its own
│                               transitive stage7_bridge chain -- one more layer
│                               of the same bridge-of-bridges pattern Stage 8
│                               used for Stage 7; same wide eviction-list
│                               discipline, given two real bare-module-name
│                               collisions already found and fixed at the
│                               Stage 7/8 layers this chain passes through)
├── mechanism_resolver.py     (cause -> mechanism, declared only)
├── lever_resolver.py         (mechanism -> the one declared lever, no
│                               structural-applicability filtering -- nothing
│                               real to filter against, see finding #5)
├── action_builder.py         (lever -> atomic action; scope via
│                               entity_scope_filter.flagged_facets, finding #3)
├── owner_resolver.py         (lever's declared default_owner -> primary_owner;
│                               joint hypotheses get every member cause's
│                               distinct owner as secondary_owners, per design
│                               doc §20, never implying a numeric split)
├── feasibility.py            (capability: stubbed AVAILABLE; context: real
│                               check that the bound scope isn't empty/contradicted)
├── intent_resolver.py        (stage7_confidence + estimation_status + action's
│                               declared risk_tier -> ACT/INVESTIGATE/MONITOR,
│                               per CONFIDENCE_POLICY; UNKNOWN -> INVESTIGATE
│                               always, finding #7)
├── monitoring.py             (affected_kpis=[kpi_name], expected_direction from
│                               impact.KPI_DIRECTION-equivalent, horizon=NOT_SPECIFIED)
├── success_criteria.py       (DERIVABLE iff estimation_status=="ESTIMATED", else
│                               NOT_DERIVABLE)
├── selection.py               (dominance over the real, reduced axis set --
│                               stage7_confidence, estimated_impact magnitude,
│                               context feasibility -- primary + non-dominated
│                               alternatives, stable tie-break on Stage 7 rank)
├── output_schema.py          (no joint split, no monetary-cost field anywhere,
│                               no LLM import in this package, Stage 7 hypothesis
│                               order never reordered as "the diagnosis",
│                               every recommendation traceable to a hypothesis_id)
├── stage9.py                  (orchestrator: run_stage9() + CLI entrypoint)
└── test_stage9.py
```

## Implementation steps

1. **`models.py` + `config.py`.** Declare `DECISION_INTENTS = ("ACT", "INVESTIGATE", "MONITOR", "DEFER")`, `ACTION_TYPES` (the 9-value vocabulary from design doc §16), `RISK_TIERS = ("LOW_REGRET", "HIGH_COMMITMENT")`. `CAUSE_MECHANISMS`: 4 rows (`product_outage→reliability_degradation`, `marketing_cut→reduced_acquisition`, `competitor_launch→competitive_pressure`, `inventory_shortage→product_unavailability`). `MECHANISM_LEVERS`: one lever each. `LEVER_ACTIONS`: `{lever: (atomic_action, default_owner, risk_tier)}`. `ActionCandidate`/`Recommendation`/`Stage9Result` dataclasses per design doc §29/§47, trimmed per scope. No DB needed.

2. **`stage8_bridge.py`.** Re-export `run_stage8` + Stage 8's own re-exported `run_stage3`/`run_stage4`/`run_stage5a_and_5c`/`load_reference`/`should_fork`/`run_stage5b`/`run_stage6`/`run_stage7` transitively. Eviction list must cover everything `stage8.py` imports at its own top level (`models`, `config`, `hypothesis_eligibility`, `impact`, `reconstruction`, `uncertainty`, `output_schema`, `canonical_bridge`, `stage8`) plus `stage7_bridge` itself — mirror Stage 8's own `stage7_bridge.py` list-building exactly, don't hand-derive a shorter one and risk a third bare-name collision. Test: import succeeds, every re-exported name is callable, no live DB needed for this check alone.

3. **`mechanism_resolver.py` + `lever_resolver.py`.** Pure dict lookups off `config.py`. Test: each of the 4 real causes resolves to its declared mechanism/lever; an undeclared cause (should never happen given Stage 7/8's closed vocabulary, but assert loudly if it does) raises rather than silently falling through.

4. **`action_builder.py`.** For a joint (`COMPOUND`) hypothesis, resolve mechanism/lever per member cause (deduplicated) and construct one combined action description listing every member (design doc §41's "joint remediation" pattern) — never implying a per-member split. Scope: call `entity_scope_filter.flagged_facets(decomposition_result)` once per Stage 9 run (not per hypothesis — the facets are cluster-level, not hypothesis-level) and attach whichever facets exist to every action's `target_scope`; empty facets → `target_scope={}`. Test against a synthetic `DecompositionResult`-shaped fixture with and without a flagged facet.

5. **`owner_resolver.py`.** `primary_owner` = the first member cause's lever's declared `default_owner`; `secondary_owners` = every other distinct member cause's owner (only for compound hypotheses, deduplicated, excluding the primary). Test the single-cause case (no secondaries) and the joint case (real secondary owner list, per design doc §20).

6. **`feasibility.py`.** `capability_feasibility` always `("AVAILABLE", [])` in this slice (state why in the docstring, not silently). `context_feasibility`: `FEASIBLE` unless the bound scope is internally contradictory (can't happen given step 4's single-source-of-truth scope binding, but keep the check real, not a rubber stamp, in case a future scope source is added). Test both branches on synthetic fixtures.

7. **`intent_resolver.py`.** Implement `CONFIDENCE_POLICY` per design doc §69's decision matrix, collapsed to what's real: `KNOWN`/`LIKELY` + `ESTIMATED` or `UNAVAILABLE` → `ACT`; `POSSIBLE` → `INVESTIGATE` unless the action's `risk_tier=="LOW_REGRET"` → `MONITOR`; `UNKNOWN` → `INVESTIGATE` always (finding #7). Test each cell of the reduced matrix, plus the `UNKNOWN`-reaches-Stage-9 case explicitly (a real fixture, not assumed away).

8. **`monitoring.py` + `success_criteria.py`.** `affected_kpis=[kpi_name]`, `expected_direction="UP"` (all 5 real KPIs are higher-is-better, per Stage 8's own `impact.py` finding — reuse that same fact, don't re-derive it), `monitoring_horizon="NOT_SPECIFIED"` (finding: no configured basis exists to invent one, design doc §45's own instruction). `success_criteria.status = "DERIVABLE"` iff `estimation_status=="ESTIMATED"` (a real trajectory exists to compare against), else `"NOT_DERIVABLE"`. Test both statuses.

9. **`selection.py`.** Dominance comparison over `(stage7_confidence rank, estimated_impact magnitude or None, context_feasibility)` — an action with `ESTIMATED` impact and `FEASIBLE` context is never dominated by one with `UNAVAILABLE` impact at the same confidence tier; ties broken by Stage 7's own `rank` (never a fabricated decimal). Primary = the top of this ordering among `ACT`/`INVESTIGATE`-eligible candidates; alternatives = non-dominated, materially different (different `hypothesis_id`) candidates, capped at a small stated number (2-3). Test: design doc §87's own golden case (higher-impact `POSSIBLE` hypothesis does NOT displace a lower-impact `LIKELY` one as primary — the exact test this project has run at every prior stage to prove diagnosis authority is preserved).

10. **`output_schema.py`.** Assert: `Stage9Result`'s primary/alternatives never reference a `hypothesis_id` outside `stage7_result.hypotheses`; no field anywhere is named or shaped like a monetary action cost; no `import` of any LLM/generative library anywhere in this package (a real, greppable regression test — design doc §96 asks for exactly this); a joint hypothesis's recommendation never carries a per-member-cause impact/owner split; every recommendation carries `hypothesis_id` + a `provenance` dict referencing the Stage 7/8 sources it came from.

11. **`stage9.py` + `test_stage9.py`.** Orchestrator: `run_stage9(stage7_result, stage8_result, decomposition_result)` → `Stage9Result`; if `stage8_result.abstained_upstream` (which already mirrors `stage7_result.abstained`), return `decision_status="NO_DEFENSIBLE_ACTION"` immediately, no candidates built (design doc §40/§53). CLI replays the full chain via `stage8_bridge` (mirroring `stage8.py`'s own `main()`, one layer deeper). Write every offline test first (steps 1-10's fixtures, no DB), run them, fix everything they catch, **then one single live-DB run against episode 15** to confirm the real chain produces a sane `Stage9Result` — not a diagnostic per module.

## Tests and validation gate

```bash
cd pipeline/stage09_recommendation_assembly
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m spacy download en_core_web_sm   # transitively needed via stage8_bridge -> ... -> stage6
.venv/bin/python test_stage9.py       # must print OK: offline fixtures (steps 1-10 cases)
                                       # + one live Stage 3->4->5a/5c->[5b]->6->7->8->9 run, episode 15
```

## Acceptance criteria

- [ ] `test_stage9.py` prints `OK`
- [ ] Stage 9 never reorders or replaces Stage 7's hypothesis ranking — the design doc's §87 golden test (higher-impact `POSSIBLE` does not displace a `LIKELY` primary) passes
- [ ] A joint (`NON_IDENTIFIABLE_JOINT`) hypothesis produces one combined action/impact/owner set, never a fabricated per-member split
- [ ] `UNKNOWN`-confidence hypotheses (which do reach Stage 9 via Stage 8's own output) resolve to `INVESTIGATE`, never `ACT`
- [ ] No monetary action-cost field exists anywhere in the output contract
- [ ] `historical_effectiveness` is `UNKNOWN` everywhere (no Learning & Memory to query, stated not hidden)
- [ ] `target_scope` comes from Stage 6's real `flagged_facets`, never fabricated as "Global" when evidence doesn't support it
- [ ] No LLM/generative-model import exists anywhere in this package (greppable regression test)
- [ ] `expected_impact`/`impact_lower`/`impact_upper` are Stage 8's real numbers, passed through unchanged and honestly labeled — never relabeled as guaranteed recovery, never a new forward-looking projection invented
- [ ] Stage 9 does not run (returns `NO_DEFENSIBLE_ACTION`) when Stage 7 abstained
- [ ] README states the 8 real-contract corrections above plainly

## Risks

- **Given most hypotheses will be `MECHANISM_UNAVAILABLE`/`UNAVAILABLE` from Stage 8** (the same finding Stage 8's own README states), most Stage 9 recommendations in a real run will carry `expected_impact=UNAVAILABLE` too — an honest, stated consequence flowing straight through, not a new gap introduced here.
- **The reduced one-lever-per-mechanism design means Stage 9 can never demonstrate the "multiple compatible parallel actions" or "conflicting actions" golden-path examples** (design doc §71-72/§88-89) with this project's real 4-cause vocabulary — those tests are structurally unreachable here, same "gated, not fabricated" category as Stage 3's Case 2 and Stage 5c's mixed-cluster case.
- **Owner assignment is real declared domain knowledge, not verified against any actual org chart** — if the hackathon's judges or a teammate object to the specific team names (`engineering`/`marketing`/`supply_chain`), it's a one-line config edit, not a re-architecture.
- **Scope-binding reuse of `entity_scope_filter.flagged_facets`** means Stage 9's own bridge chain must correctly thread `decomposition_result` through — confirm this doesn't hit a fourth bare-module-name collision given how deep this bridge-of-bridges-of-bridges chain now runs (Stage 9 → Stage 8 → Stage 7 → Stage 6/5b/5a/4/3).
- Time budget: Stages 10-11 still need to ship after this one for the stated EOD target.
