# Stage 5c — Cold-Start / Analogy Handler
## Implementation Plan — PS3 BusinessIntelligence.ai, Round 2 (AIC 2026)

**Companion to:** `stage4-implementation-plan.md` (source of the `LIMITED_HISTORY`/`INSUFFICIENT_DATA` trigger) and `stage5a-implementation-plan.md` (the router that decides whole-cluster vs. mixed-cluster invocation). This document is execution-focused.

**Two decisions made explicitly below in the absence of a team answer, flagged for override:** the analog-similarity mechanism (declared, not learned) and the scope cut on cause-prior borrowing (stretch goal, not MVP).

**Golden example used throughout:** Product A, -21% deviation, 4 months of history, `LIMITED_HISTORY` per Stage 4. Product B — same price tier, same category, launched earlier — is the declared analog.

---

## 1. Trigger & Scope

**Trigger (already exists, no new detection logic):** Stage 4's per-slice eligibility tag. Stage 5a's own router (per `stage5a-implementation-plan.md` §2, §6) checks this before running the classifier.

**Two invocation modes, both must be supported:**
- **Whole-cluster cold-start:** every flagged rare slice in the cluster is `LIMITED_HISTORY`/`INSUFFICIENT_DATA` → 5a is skipped entirely, 5c handles the whole cluster.
- **Mixed cluster (the team's actual running example):** some flagged slices are solid (North, Enterprise → 5a runs normally), one is thin (Product A → 5c runs in parallel, on just that slice). **Both results are emitted separately and forwarded together — never merged into one confidence number.** This is the harder case and the one to build for, since it's the team's own real scenario.

---

## 2. Exact Input Contract

Consumes:
- The specific slice(s) from Stage 4's output tagged `LIMITED_HISTORY` or `INSUFFICIENT_DATA` (see `stage4-implementation-plan.md` §5 — the `eligibility` field per slice).
- The full historical series for that slice (short as it is) — via the same `slice_fetcher` module Stage 4 already built. No new data-access code.

```json
{
  "cluster_id": "cluster_2026_08_c17",
  "window": {"start": "2026-08-01", "end": "2026-08-31"},
  "thin_slices": [
    {
      "kpi": "revenue",
      "dimension": "product",
      "slice_value": "Product A",
      "observed": 198000,
      "expected": 250000,
      "deviation_pct": -0.21,
      "eligibility": "LIMITED_HISTORY",
      "history_available": ["2026-05", "2026-06", "2026-07", "2026-08"]
    }
  ]
}
```

---

## 3. Step 1 — Analog Selection

**Mechanism: declared, not learned — consistent with "declare, don't infer" used everywhere else in this build.** With only 3-5 KPIs and a handful of slices per dimension, a learned similarity model is real over-engineering for what's actually a short manual lookup.

### 3.1 Config (lives in the Semantic Contract, same service as everything declared so far)

```yaml
analogy_groups:
  product:
    Product A:
      analog: Product B
      basis: "same price tier, same category, launched within 6 months of each other"
  region:
    # populated only if a region-level cold-start case is deliberately built into the simulator
  segment:
    # same
```

**Team task, not a code task:** decide, once, for each slice you deliberately design as a cold-start case in your simulator, which existing slice is its declared analog and why. This is a business judgment call, not a computation.

### 3.2 Optional validation (sanity-check only, not the selection mechanism)

If the thin slice and its analog *do* share any overlapping history (e.g., 2 months where both existed), compute a simple correlation as a cheap red-flag check — not to pick the analog, only to catch an obviously bad declared pairing before the demo:

```python
def validate_analog_similarity(thin_series: pd.Series, analog_series: pd.Series) -> Optional[float]:
    """Pearson correlation over the overlapping window, if any exists.
    Returns None if there's no overlap to check against — that's expected
    for a genuine cold-start case, not an error."""
```

If this comes back low or negative, flag it in output for the team to notice — do not auto-swap to a different analog; that would be inferring where you decided to declare.

---

## 4. Step 2 — Borrowing the Volatility Profile (the core mechanism)

**Reuse target, explicitly:** the exact same percentile-computation function from Stage 2's Layer 3 (`unusualness_percentile`), already imported by Stage 4. This is now the third stage reusing this one function — worth stating plainly in the report as a sign of a coherent architecture, not a coincidence.

**The actual computation:**
1. Compute the analog's own historical distribution of *relative* (%) deviations — not absolute dollar swings, since Product A and Product B likely sit at different revenue scales. Relative terms are what make the borrow valid across two different-sized products.
2. Feed Product A's own `-21%` deviation into that borrowed distribution and get a percentile back — using the identical function Stage 2/4 already use, just handed a different (borrowed) reference distribution instead of the slice's own.

```python
def borrowed_percentile(thin_slice_deviation_pct: float, analog_series: pd.Series) -> float:
    analog_relative_swings = compute_relative_swings(analog_series)  # same method as Stage 2 Layer 2/3
    return unusualness_percentile(thin_slice_deviation_pct, analog_relative_swings)  # imported, not reimplemented
```

**Result for the worked example:** if Product B's own history shows it rarely swings past ±8%, then Product A's -21% — evaluated against *that* distribution — comes back around **0.91: genuinely rare, borrowed.**

---

## 5. Step 3 (Stretch Goal, Not MVP) — Borrowing Cause-History Priors

**Explicit scope cut, stated honestly:** if the declared analog (Product B) has a past resolved diagnosis in the Learning & Memory service with a similarly-shaped anomaly, that diagnosis could seed a weighted prior over cause labels for Product A — "when Product B dropped this way before, it turned out to be a pricing change." This is a real, valuable extension, but it depends on Learning & Memory already having accumulated history, which likely won't exist early in a hackathon build (the memory itself has a cold-start problem). **Build Step 4's output (the percentile) first and confirm it works end-to-end before attempting this — do not block the MVP on it.**

If time permits:
```python
def borrow_cause_priors(analog_slice_value: str, learning_memory) -> Optional[dict]:
    """Looks up past investigations tagged to the analog slice with a similar
    fingerprint shape. Returns a soft prior distribution over cause labels,
    or None if no matching history exists yet — None is the expected, honest
    answer for most of a hackathon's runtime."""
```

---

## 6. Output Contract (to Stage 6/7 — kept separate from Stage 5a's output, never merged)

```json
{
  "cluster_id": "cluster_2026_08_c17",
  "window": {"start": "2026-08-01", "end": "2026-08-31"},
  "borrowed_attributions": [
    {
      "kpi": "revenue",
      "dimension": "product",
      "slice_value": "Product A",
      "analog_used": "Product B",
      "analog_basis": "declared: same price tier + category (Semantic Contract)",
      "analog_similarity_check": null,
      "borrowed_percentile": 0.91,
      "cause_priors": null,
      "confidence_tier": "BORROWED"
    }
  ]
}
```

**Downstream contract note, not this stage's implementation but a direct consequence of it:** Stage 7's hypothesis debate must treat any hypothesis carrying `confidence_tier: BORROWED` as structurally capped below `Known`/`Likely` — at most `Possible` — regardless of what raw score it produces. This should be written into Stage 7's design explicitly when that stage is built, so the tag isn't just decoration that nothing downstream actually respects.

**Hard rule, same as every other stage's output schema:** no free-text fields except the fixed-enum ones (`confidence_tier`, `analog_basis` as a short declared string, not a generated explanation).

---

## 7. Module Breakdown

```
stage5c/
├── config/
│   └── analogy_groups.yaml
├── analog_selector.py        # Section 3 — declared lookup + optional correlation sanity-check
├── borrowed_percentile.py    # Section 4 — wraps Stage 2's Layer 3 function, reused not reimplemented
├── cause_prior_lookup.py     # Section 5 — stretch goal, queries Learning & Memory
├── output_schema.py          # validation, Section 6
└── run_stage5c.py             # entrypoint: thin slices in, borrowed_attributions out
```

---

## 8. Build Order

1. **Declare `analogy_groups.yaml`** for every cold-start case deliberately built into the simulator — team decision, blocking, needs to happen before any code here runs meaningfully.
2. **Confirm the exact import path for Stage 2's `unusualness_percentile`** — same dependency Stage 4 already resolved; reuse that adapter rather than re-confirming from scratch.
3. **Build `analog_selector.py`** — pure lookup function, trivial to unit test alone.
4. **Build `borrowed_percentile.py`** — depends on step 2's confirmed import.
5. **Build `output_schema.py`**.
6. **Wire `run_stage5c.py`**, and confirm Stage 5a's router actually calls it in parallel for `LIMITED_HISTORY` slices in a mixed cluster (per Section 1) — this is the integration point most likely to be silently skipped if not tested explicitly.
7. **(Stretch) Build `cause_prior_lookup.py`** only after 1-6 are working end-to-end.

---

## 9. Test Plan

### 9.1 Unit tests
- `analog_selector`: returns the declared analog correctly for a known slice; **declines (does not guess) when no analog is declared** — reuse of the abstention principle, tested explicitly, not left to hope.
- `borrowed_percentile`: given a synthetic analog series with a known distribution, returns the correct percentile for a given deviation — hand-computable, verify by hand.

### 9.2 Integration / golden-path test
Using the Product A / Product B worked numbers: assert `borrowed_percentile` comes back materially high (≥0.85), `confidence_tier == "BORROWED"`, and `analog_used == "Product B"`.

### 9.3 Edge cases
- No declared analog exists for a flagged thin slice → system declines to fingerprint that slice at all, rather than silently picking an arbitrary one.
- Mixed-cluster case (the team's own real scenario): confirm Stage 5a's output (for North/Enterprise) and Stage 5c's output (for Product A) both arrive at Stage 6/7, tagged distinctly, with no code path that accidentally averages or merges them into one number.

---

## 10. Explicit Non-Goals for This Implementation

- No learned/ML similarity scoring between candidate analogs — declared pairs only, a team decision made once per cold-start case.
- No automatic discovery of which slices need cold-start handling beyond what Stage 4's eligibility gate already flags.
- No merging of `BORROWED` and native (`HIGH`/`MEDIUM`) confidence results into a single blended number, at this stage or any downstream one.
- Cause-prior borrowing (Section 5) is a stretch goal — the MVP is the borrowed percentile alone, and that alone already solves the primary problem (Product A gets a usable, honestly-tagged signal instead of nothing).
