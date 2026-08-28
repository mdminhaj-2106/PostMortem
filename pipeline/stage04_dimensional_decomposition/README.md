# Stage 4 — Dimensional Decomposition

**Job:** break a flagged movement (or cluster) down by region/segment/product/channel. Purely descriptive, no cause-guessing yet.

**Status:** Implementation plan ready — exact I/O schemas, config, module breakdown, build order, and test plan are all specified. Blocked on confirming Stage 2's function interface (plan §4/§7, item 2) before `decomposer.py` can be started.

**Implementation plan:** [`docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md`](../../docs/02-stage-design-reports/stage4-dimensional-decomposition-implementation-plan.md)

**Planned module layout** (from the implementation plan §6 — not yet created as code, listed here for reference):

```
config/dimension_applicability.yaml
config/taxonomy.yaml
taxonomy_mapper.py     # maps raw source columns -> canonical slice values
slice_fetcher.py       # pulls per-slice historical series from Stage 1's canonical timeline
stage2_adapter.py      # thin wrapper around imported Stage 2 functions
decomposer.py          # main loop
output_schema.py       # pydantic/dataclass model + validation
run_stage4.py          # entrypoint
```

**Input contract (from Stage 3):** `cluster_id`, `kpis`, `priority_score`, `stage2_confidence_tag`, `window` — see plan §1.

**Output contract (→ Stage 5a):** a decomposition matrix of KPI × dimension × slice, each slice carrying expected/observed/deviation_pct/unusualness_percentile/eligibility/imputation_flag. `unusualness_percentile: null` on `LIMITED_HISTORY` slices is the signal that routes a slice to Stage 5c instead of Stage 5a. See plan §5 for the exact schema and its free-text-rejection validation rule.

**Golden regression test:** the {revenue, conversion} × {North/South/East/West, Enterprise/SMB/Consumer, Product A/B/C} worked example from the design chat — see plan §8.2. Check this in as a permanent fixture once the module exists.

**Build order:** plan §7 — finalize taxonomy/applicability config and confirm Stage 2's function signatures first (both blocking); `taxonomy_mapper.py` and `slice_fetcher.py` can then be built in parallel with `stage2_adapter.py`.

No code yet — this is the most implementation-ready stage in the pipeline; start here once Stage 2's interface is confirmed.
