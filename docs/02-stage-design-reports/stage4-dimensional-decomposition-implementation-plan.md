# Stage 4 — Dimensional Decomposition
## Implementation Plan — PS3 BusinessIntelligence.ai, Round 2 (AIC 2026)

**Companion to:** `stage4-dimensional-decomposition-report.md` (architecture rationale — not yet written/added to this project; this implementation plan is the only Stage 4 doc currently in the project). This document is execution-focused — exact schemas, module breakdown, build order, and tests. Rationale is not repeated here except where needed to justify an implementation choice.

**Golden example used throughout:** the {revenue, conversion} cluster worked through end-to-end in chat (North region -15%/-14% unusualness, Enterprise segment similarly rare, Product A large but low-confidence due to limited history). This same example is the regression test at the end of this doc.

---

## 1. Exact Input Contract (from Stage 3)

```json
{
  "cluster_id": "cluster_2026_08_c17",
  "kpis": ["revenue", "conversion_rate"],
  "priority_score": {
    "value": 130000,
    "unit": "USD_equivalent",
    "basis": "observed"
  },
  "stage2_confidence_tag": "SIGNIFICANT",
  "window": {
    "start": "2026-08-01",
    "end": "2026-08-31"
  }
}
```

Stage 4 does not re-validate `priority_score` or `stage2_confidence_tag` — it only reads `kpis` and `window` to know what to decompose and over what period.

---

## 2. Config Needed Before Stage 4 Can Run

### 2.1 KPI → Dimension Applicability Map
Not every KPI gets every dimension (conversion has no product breakdown in this business). This is declared config, not inferred:

```yaml
dimension_applicability:
  revenue: [region, segment, product]
  conversion_rate: [region, segment]
  active_customers: [region, segment]
```

### 2.2 Shared Dimension Taxonomy (lives in the KPI Semantic Contract)
```yaml
taxonomy:
  region:
    values: [North, South, East, West]
    source_mapping:
      revenue_table: "billing_region"
      conversion_table: "geo_ip_region"
  segment:
    values: [Enterprise, SMB, Consumer]
    source_mapping:
      revenue_table: "account_tier"
      conversion_table: "account_tier"
  product:
    values: [Product A, Product B, Product C]
    source_mapping:
      revenue_table: "sku_family"
```
Every raw source's own column gets mapped to this canonical value set at load time — this is the mechanism that prevents the taxonomy-mismatch failure mode from the design report (Section 3).

---

## 3. Pipeline Steps (implementation order)

```
Step 1 — Load cluster + window from Stage 3 output
Step 2 — For each KPI in cluster:
           Step 2a — Look up applicable dimensions (Section 2.1)
           Step 2b — For each applicable dimension:
             Step 2b-i  — Look up canonical slice values + source mapping (Section 2.2)
             Step 2b-ii — For each slice value:
                Step 2b-ii-a — Fetch this slice's historical series from Stage 1's canonical timeline
                Step 2b-ii-b — Run Layer 1: Eligibility Gate (imported from Stage 2 module)
                Step 2b-ii-c — Run Layer 2: Expected Behavior baseline (imported from Stage 2 module)
                Step 2b-ii-d — Compute deviation = current_value - expected_value
                Step 2b-ii-e — Run Layer 3: Self-Normalized Unusualness percentile (imported from Stage 2 module)
                Step 2b-ii-f — Attach inherited flags from Stage 1 (imputation_flag, provenance)
                Step 2b-ii-g — Emit slice record
Step 3 — Assemble full matrix (all KPIs × dimensions × slices)
Step 4 — Validate output against schema (Section 5) — reject any free-text/narrative field
Step 5 — Emit to Stage 5a
```

**Critical dependency, flag to teammate building Stage 2:** Steps 2b-ii-b, c, e require Stage 2's Layer 1/2/3 logic to exist as **importable functions**, not just a spec in a doc. Stage 4 should not reimplement eligibility-gating or baseline computation — that would violate the reuse principle and risk the two stages silently drifting out of sync. Confirm with your teammate the exact function signatures early (see Section 4 for the expected interface Stage 4 will call).

---

## 4. Expected Function Interface (to confirm with Stage 2's owner)

```python
# Expected to be importable from the Stage 2 module — confirm exact names/signatures
def eligibility_gate(series: pd.Series, min_history_points: int = 30) -> EligibilityTag:
    """Returns one of: ELIGIBLE, LIMITED_HISTORY, LOW_CONFIDENCE, INSUFFICIENT_DATA"""

def expected_behavior(series: pd.Series, eligibility: EligibilityTag) -> ExpectedBaseline:
    """Adaptive: trend+seasonality if eligible & history supports it, else rolling median."""

def unusualness_percentile(current_value: float, expected: ExpectedBaseline,
                             historical_residuals: pd.Series) -> float:
    """Returns 0-1 percentile of current deviation vs. this series' own residual history."""
```

If Stage 2's actual functions differ, this is the adapter layer to write — do not fork the logic.

---

## 5. Exact Output Schema (to Stage 5a)

```json
{
  "cluster_id": "cluster_2026_08_c17",
  "window": {"start": "2026-08-01", "end": "2026-08-31"},
  "decomposition": [
    {
      "kpi": "revenue",
      "dimension": "region",
      "slices": [
        {
          "slice_value": "North",
          "expected": 400000,
          "observed": 340000,
          "deviation_pct": -0.15,
          "unusualness_percentile": 0.99,
          "eligibility": "ELIGIBLE",
          "imputation_flag": "none"
        },
        {
          "slice_value": "South",
          "expected": 200000,
          "observed": 195000,
          "deviation_pct": -0.025,
          "unusualness_percentile": 0.35,
          "eligibility": "ELIGIBLE",
          "imputation_flag": "partially_imputed"
        }
      ]
    },
    {
      "kpi": "revenue",
      "dimension": "product",
      "slices": [
        {
          "slice_value": "Product A",
          "expected": 250000,
          "observed": 198000,
          "deviation_pct": -0.21,
          "unusualness_percentile": null,
          "eligibility": "LIMITED_HISTORY",
          "imputation_flag": "none"
        }
      ]
    },
    {
      "kpi": "conversion_rate",
      "dimension": "region",
      "slices": [
        {
          "slice_value": "North",
          "expected": 0.030,
          "observed": 0.0255,
          "deviation_pct": -0.15,
          "unusualness_percentile": 0.97,
          "eligibility": "ELIGIBLE",
          "imputation_flag": "none"
        }
      ]
    }
  ]
}
```

**Schema validation rule (enforces the cause-language boundary structurally):** no field in this object may be a free-text string except `slice_value`, `eligibility`, and `imputation_flag`, all of which are drawn from fixed enums. Add a CI check or a simple assertion in code that rejects any output containing an unexpected string field — this is cheaper than a lint-on-words rule and closes the loophole completely rather than just discouraging it.

**Note on `unusualness_percentile: null`:** LIMITED_HISTORY slices emit `null` here rather than a fabricated number — this is what signals Stage 5a to route toward Stage 5c instead of trusting the percentile.

---

## 6. Module Breakdown (suggested file structure)

```
stage4/
├── config/
│   ├── dimension_applicability.yaml
│   └── taxonomy.yaml               # or pulled live from Semantic Contract service
├── taxonomy_mapper.py              # maps raw source columns -> canonical slice values
├── slice_fetcher.py                # pulls per-slice historical series from Stage 1 timeline
├── stage2_adapter.py               # thin wrapper around imported Stage 2 functions
├── decomposer.py                   # main loop: Section 3, steps 2-3
├── output_schema.py                # pydantic/dataclass model + validation (Section 5)
└── run_stage4.py                   # entrypoint: Stage 3 output in, Stage 5a input out
```

---

## 7. Build Order (task list)

1. **Finalize taxonomy + applicability config** (Section 2) — blocking everything else; needs a short sync with whoever owns the simulator's Layer 2 source views, since taxonomy mapping depends on knowing each source's raw column names.
2. **Confirm Stage 2's Layer 1/2/3 function signatures** with the teammate building Stage 2 (Section 4) — blocking; do not start decomposer.py until this is settled, or you'll be reworking the adapter layer later.
3. **Build `taxonomy_mapper.py`** — pure function, easy to unit test independently.
4. **Build `slice_fetcher.py`** — pulls a slice's historical series from Stage 1's canonical timeline given (kpi, dimension, slice_value, window).
5. **Build `stage2_adapter.py`** — wraps the imported eligibility/baseline/percentile functions; this isolates Stage 4 from any signature changes on Stage 2's side to one file.
6. **Build `decomposer.py`** — the main loop (Section 3, steps 2-3). Depends on 3-5.
7. **Build `output_schema.py`** — validation model, including the free-text rejection rule.
8. **Wire `run_stage4.py`** end-to-end.
9. **Run the regression test** (Section 8) before connecting to real Stage 3/Stage 5a interfaces.

Steps 3-5 can be built in parallel by different team members once steps 1-2 are settled, since they don't depend on each other.

---

## 8. Test Plan

### 8.1 Unit tests
- `taxonomy_mapper`: given a raw source value, returns the correct canonical slice; given an unmapped value, raises/flags rather than silently passing it through.
- `stage2_adapter`: given a synthetic series with known injected volatility, eligibility/baseline/percentile outputs match hand-computed expected values.
- `output_schema`: a payload with an extra free-text field is rejected; a valid payload passes.

### 8.2 Integration / golden-path regression test
Use the worked example from chat as fixed input/output:
- **Input:** synthetic revenue + conversion series for North/South/East/West, Enterprise/SMB/Consumer, Product A/B/C, matching the numbers in the worked example (North revenue $400k→$340k with ±3% normal swing, etc.)
- **Expected output:** North and Enterprise slices flagged with percentile ≥0.95 for both KPIs; South/East/West/SMB/Consumer near 0.3-0.6; Product A returns `eligibility: LIMITED_HISTORY` and `unusualness_percentile: null`.
- This test should be checked into the repo as a permanent regression fixture — if Stage 2's baseline logic changes later, this test catches whether Stage 4's numbers silently drift.

### 8.3 Edge cases to explicitly test
- A slice with zero historical observations (should hit INSUFFICIENT_DATA, not crash).
- A KPI with no applicable dimensions configured (should emit an empty decomposition list for that KPI, not error).
- A cluster of size 1 (single KPI, no Stage 3 grouping) — decomposition logic should behave identically to a multi-KPI cluster with one member.

---

## 9. Explicit Non-Goals for This Implementation

- No dimension beyond region/segment/product.
- No per-slice trajectory/time-series output — Stage 4 emits single-window snapshots only; Stage 5a is responsible for pulling short trailing windows itself, only for slices it flags as rare (per the design report, Section on onset shape).
- No narrative generation, even for internal debugging logs shown in the demo UI — use the structured fields directly in any debug view.
- No reimplementation of Stage 2's statistical logic under a different name "for Stage 4's convenience" — import or fail loudly if the interface isn't ready yet.
