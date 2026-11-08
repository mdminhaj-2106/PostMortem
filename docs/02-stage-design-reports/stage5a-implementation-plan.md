# Stage 5a — Fingerprint / Cause-Signature Classification
## Implementation Plan — PS3 BusinessIntelligence.ai, Round 2 (AIC 2026)

**Companion to:** `stage4-dimensional-decomposition-report.md` and `stage4-implementation-plan.md` (defines the exact input this stage consumes). This document is execution-focused. Rationale for *why* a trained classifier rather than an LLM is used is covered in chat and not repeated here except where it affects an implementation choice.

**Golden example used throughout:** the same {revenue, conversion} cluster — North region and Enterprise segment rare in both KPIs, Product A large-but-low-confidence, gradual onset over ~21 days. Worked numbers from chat are the regression test in Section 9.

---

## 1. Exact Input Contract (from Stage 4)

Stage 5a consumes the exact output schema defined in `stage4-implementation-plan.md`, Section 5 — the KPI × dimension × slice matrix. No changes required to that schema; Stage 5a reads it as-is.

```json
{
  "cluster_id": "cluster_2026_08_c17",
  "window": {"start": "2026-08-01", "end": "2026-08-31"},
  "decomposition": [ /* ... full matrix from Stage 4, see stage4-implementation-plan.md Section 5 ... */ ]
}
```

---

## 2. Step 0 — Identify the Rare Slices (before any feature engineering)

Filter the incoming matrix down to slices worth fingerprinting:

```python
RARE_THRESHOLD = 0.90  # config-tunable

rare_slices = [
    slice for kpi_block in decomposition
    for slice in kpi_block["slices"]
    if slice["unusualness_percentile"] is not None
    and slice["unusualness_percentile"] >= RARE_THRESHOLD
]

limited_history_flagged = [
    slice for kpi_block in decomposition
    for slice in kpi_block["slices"]
    if slice["eligibility"] in ("LIMITED_HISTORY", "INSUFFICIENT_DATA")
]
```

**Routing pre-check:** if `rare_slices` is empty but `limited_history_flagged` is non-empty and material to the cluster's priority, this is a straight signal to skip the classifier and route directly to **Stage 5c** — there's nothing statistically confident enough to fingerprint. Otherwise, continue.

---

## 3. Step 1 — Feature Engineering (the "signature")

**Critical implementation rule: this exact code must be used both offline (training, Section 5) and online (runtime, Section 6).** Any divergence between the two is a classic train/serve skew bug — the model would be scored on features it was never actually trained to recognize. Build this as one shared module, imported by both.

### 3.1 Core mandatory features (computable directly from Stage 4's matrix)

```python
def normalized_entropy(magnitudes: list[float]) -> float:
    """Shannon entropy of |deviation| share across slices in one dimension,
    normalized by log2(n) so a 4-region and a 3-segment entropy are comparable."""
    total = sum(abs(m) for m in magnitudes)
    if total == 0:
        return None
    shares = [abs(m) / total for m in magnitudes]
    raw_entropy = -sum(p * log2(p) for p in shares if p > 0)
    return raw_entropy / log2(len(magnitudes))  # 0 = fully concentrated, 1 = fully spread
```

- `geo_spread_entropy` — from the `region` dimension's slice deviations.
- `segment_spread_entropy` — from the `segment` dimension's slice deviations. (Addition beyond the original architecture report's feature list — justified because Stage 4 already produces segment-level slices, and the team's own running example treats Enterprise-concentration as a primary signal, not a side note. Flagging this as a deliberate extension, not scope creep — no new data collection required, purely reusing what Stage 4 already computes.)
- `product_spread_entropy` — from the `product` dimension's slice deviations. **Nullable**: if the product dimension's relevant slices are `LIMITED_HISTORY` (as in the Product A case), emit `null` here rather than a number computed on shaky data, and let this feed the eligibility flag downstream instead of a false-confidence entropy value.

### 3.2 Features requiring a targeted trailing-window pull (not in Stage 4's snapshot)

Stage 4 emits single-window snapshots by design (see its non-goals). Onset shape and duration need a short trajectory — fetched here, only for the slices already identified as rare in Step 0, directly from Stage 1's canonical timeline. This keeps the expensive multi-day pull limited to a handful of slices, not every slice in the matrix.

```python
def onset_shape_ratio(daily_series: pd.Series) -> float:
    """day-1 abs change / day-7 cumulative abs change. Low ratio = gradual ramp,
    high ratio = sudden step. Requires the trailing 7 days for a rare slice."""
    day1 = abs(daily_series.iloc[0] - daily_series_baseline.iloc[0])
    day7_cumulative = abs(daily_series.iloc[6] - daily_series_baseline.iloc[6])
    if day7_cumulative == 0:
        return None
    return day1 / day7_cumulative

def duration_days(daily_series: pd.Series, threshold: float) -> int:
    """Consecutive days the deviation has remained beyond the significance
    threshold, counting back from the most recent day. Reuses Stage 2's own
    threshold definition — do not invent a second one here."""
    ...
```

### 3.3 Optional, conditional features (only if traffic/AOV exist as tracked KPIs in this build)

`visits_delta` and `spend_per_visit_delta` were in the original 8-feature design, but require traffic/AOV to be part of the 3-5 KPIs actually tracked in this prototype. **Explicit scope call:** include these only if traffic or AOV is already one of your chosen KPIs; do not stand up a new data source just to compute them. If absent, the classifier trains and runs on the 5 core features only — document this honestly as a scope cut, same spirit as dropping the `channel` dimension in Stage 4.

**Final signature for this build (5 mandatory + up to 2 optional):**
`geo_spread_entropy, segment_spread_entropy, product_spread_entropy (nullable), onset_shape_ratio, duration_days, [visits_delta], [spend_per_visit_delta]`

---

## 4. Cause Label Space (unchanged from original architecture report)

```yaml
cause_labels:
  - churn
  - marketing_reduction
  - product_reliability
  - inventory_shortage
  - competitor_activity
  - pricing_change
  - seasonal
  - regional_economic
```

---

## 5. Training Pipeline (offline, one-time, NOT part of the runtime request path)

```
Step A — Generate simulator episodes (Layer 1 + injected causal events), each with a known ground-truth label
Step B — Run each episode through: Stage 1 -> Stage 4 -> the SAME Step 0 + Step 1 feature functions from Section 2-3
Step C — Assemble training table: rows = episodes, columns = the signature features, label = injected cause
Step D — Stratified train/val/test split (stratify by cause label — classes will be imbalanced)
Step E — Train XGBoost multiclass classifier (objective="multi:softprob")
Step F — Calibrate output probabilities (Platt scaling) — same discipline as Component A's significance
          classifier; the confidence number is a product feature (drives 5b/5c routing), not just a label
Step G — Fit a SHAP TreeExplainer against the trained model
Step H — Evaluate: top-1/top-3 accuracy, confusion matrix, SHAP fidelity spot-check (Section 9)
Step I — Serialize both the classifier and the SHAP explainer to disk (joblib)
```

**Do not skip Step B's reuse requirement.** If training-time feature computation and runtime feature computation are written twice, they will drift, and the model's learned thresholds will silently stop matching what it sees in production. Import the same `feature_engineering.py` module in both the training script and the runtime module.

---

## 6. Runtime Classification (the actual Stage 5a request-path logic)

```python
def run_stage5a(stage4_output: dict) -> dict:
    rare_slices, limited_history = identify_rare_slices(stage4_output)  # Section 2

    if not rare_slices and limited_history:
        return route_to_stage5c(stage4_output, reason="no_confident_rare_slices")

    features = compute_signature(stage4_output, rare_slices)  # Section 3, shared module

    probs = classifier.predict_proba(features)          # loaded artifact from Section 5
    shap_values = shap_explainer(features)               # loaded artifact from Section 5

    top1, top2 = sorted(probs.items(), key=lambda x: -x[1])[:2]
    margin = top1[1] - top2[1]

    if margin < CONFOUND_MARGIN_THRESHOLD:                # config-tunable, default 0.20
        return route_to_stage5b(features, probs, shap_values, reason="split_confidence")

    if any_flagged_slice_is_limited_history(rare_slices):
        confidence_tier = "BORROWED"  # partially informed by thin data — flag, don't hide it
    else:
        confidence_tier = "HIGH" if top1[1] >= 0.6 else "MEDIUM"

    return assemble_output(features, probs, shap_values, confidence_tier, routing="PROCEED")
```

---

## 7. Exact Output Schema (to Stage 6/7, or the 5b/5c branch)

```json
{
  "cluster_id": "cluster_2026_08_c17",
  "window": {"start": "2026-08-01", "end": "2026-08-31"},
  "fingerprint_features": {
    "geo_spread_entropy": 0.15,
    "segment_spread_entropy": 0.10,
    "product_spread_entropy": null,
    "onset_shape_ratio": 0.13,
    "duration_days": 21
  },
  "cause_probabilities": {
    "product_reliability": 0.71,
    "competitor_activity": 0.18,
    "seasonal": 0.04,
    "marketing_reduction": 0.03,
    "inventory_shortage": 0.02,
    "pricing_change": 0.01,
    "regional_economic": 0.01,
    "churn": 0.00
  },
  "shap_attribution": {
    "onset_shape_ratio": 0.28,
    "geo_spread_entropy": 0.22,
    "duration_days": 0.15,
    "segment_spread_entropy": 0.09
  },
  "routing_decision": "PROCEED",
  "confidence_tier": "HIGH"
}
```

`routing_decision` is one of `PROCEED`, `BRANCH_5B_CONFOUNDED`, `BRANCH_5C_COLD_START`. **Full probability distribution is always passed forward, not just the top label** — Stage 7's hypothesis debate needs the ranked list, not a single committed answer, per its own design.

---

## 8. Module Breakdown (suggested file structure)

```
stage5a/
├── config/
│   └── cause_labels.yaml
├── feature_engineering.py       # Section 3 — SHARED between training and runtime, no exceptions
├── trailing_window_fetcher.py   # pulls short history from Stage 1 timeline, only for rare slices
├── training/
│   ├── generate_episodes.py     # calls the simulator, Step A
│   ├── train_classifier.py      # Steps C-I
│   └── artifacts/
│       ├── classifier.joblib
│       └── shap_explainer.joblib
├── router.py                    # margin check + eligibility check -> routing decision
├── classifier_runtime.py        # Section 6 end-to-end
├── output_schema.py             # validation model, Section 7
└── run_stage5a.py                # entrypoint: Stage 4 output in, Stage 6/7/5b/5c input out
```

---

## 9. Test Plan

### 9.1 Unit tests (feature engineering)
- `normalized_entropy`: uniform magnitudes across all slices → returns ~1.0; all magnitude in one slice → returns ~0.0.
- `onset_shape_ratio`: a synthetic step-function series → high ratio; a synthetic linear ramp → low ratio.
- `duration_days`: series crossing the threshold and staying there → correct day count; a one-day spike that reverts → returns 1, not the full window length.

### 9.2 Offline model evaluation (run once after training, Section 5 Step H)
- Top-1 / top-3 accuracy on held-out test episodes.
- Confusion matrix — explicitly check which cause pairs get confused (e.g., marketing-cut vs. seasonal-dip, both broad/gradual) and report this honestly as a real finding, not a bug to hide.
- SHAP fidelity spot-check: pick 3-5 test predictions, manually verify the SHAP attribution matches an intuitive read of the input features.

### 9.3 Integration / golden-path regression test
Feed the exact worked numbers from chat (`geo_spread_entropy≈0.15, segment_spread_entropy≈0.10, onset_shape_ratio≈0.13, duration_days=21`) through `classifier_runtime.py` and assert:
- `cause_probabilities["product_reliability"]` is the top prediction, roughly in the 0.6–0.8 range.
- `routing_decision == "PROCEED"` (margin should be well above the confound threshold given how dominant product_reliability is in this example).
- `shap_attribution` top two features are `onset_shape_ratio` and `geo_spread_entropy`, matching the manual walkthrough.

### 9.4 Routing edge cases
- Construct a synthetic input where two causes' probabilities are within 0.05 of each other → assert routing to `BRANCH_5B_CONFOUNDED`.
- Construct a synthetic input where all rare slices are `LIMITED_HISTORY` → assert routing to `BRANCH_5C_COLD_START` and that the classifier is not even called.
- Construct a synthetic input with `product_spread_entropy: null` but other features present → assert the classifier handles the missing feature gracefully (XGBoost natively handles missing values; confirm this isn't silently coerced to 0).

---

## 10. Explicit Non-Goals for This Implementation

- No deep learning — gradient-boosted trees only, per the original scope guard; a few hundred synthetic episodes would overfit anything heavier.
- No live/online training or model updates during a demo — the classifier is trained once, offline, and frozen before the pipeline runs.
- No `channel_mix_shift` feature — dropped, consistent with Stage 4 dropping `channel` as a decomposition dimension.
- No calibration beyond Platt scaling — more advanced calibration methods are out of scope for a hackathon timeline; state this as a known limitation if asked.
- No attempt to fingerprint a slice that Stage 4 already marked `INSUFFICIENT_DATA` — it routes to 5c instead, it does not get a forced feature value.
