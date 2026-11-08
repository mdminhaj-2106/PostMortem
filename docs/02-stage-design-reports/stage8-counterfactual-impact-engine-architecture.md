# Stage 8 — Counterfactual Impact Engine
## Detailed Implementation Architecture — AIC / PS3 BusinessIntelligence.ai

**Status:** Proposed architecture after design interview; ready for implementation after final review  
**Stage:** 8  
**Consumes:** Stage 7 ranked hypotheses, Stage 5b attribution where available, Stage 5c context where applicable, Stage 1–4 analytical context  
**Produces:** Time-resolved counterfactual KPI estimates, estimated cause impact, uncertainty intervals, and business-impact interpretation for Stage 9  
**Primary design goal:** Estimate what the KPI would have been under a specified intervention without pretending that hypothesis confidence is causal certainty.

---

# 1. Purpose

Stage 8 is the project's **counterfactual impact estimation layer**.

Stages 1–4 establish:

```text
what changed
where it changed
how unusual it was
```

Stages 5a–5c establish:

```text
which causes are plausible
how overlapping causes may contribute
how cold-start evidence is handled
```

Stage 6 establishes:

```text
what observational evidence exists
```

Stage 7 establishes:

```text
which hypotheses are best supported
```

Stage 8 now asks:

> **What would the KPI have been if a specific ranked hypothesis had not occurred?**

And, as a direct consequence:

> **How much KPI / business impact is attributable to that intervention under the model?**

The output is intentionally stronger than a narrative but weaker than a claim of proven causal truth.

---

# 2. Locked Design Decisions

The following decisions were confirmed before this architecture was written.

| Decision | Choice |
|---|---|
| Primary output | Counterfactual KPI + cause impact + observed KPI |
| Hypothesis coverage | Estimate every defensible ranked hypothesis, not only top-1 |
| Counterfactual engine | Independent Stage 8 engine |
| Example intervention | Revenue without the outage |
| Counterfactual modes | Support both “event never occurred” and “event removed from a specified intervention point” |
| Time resolution | Yes — time-resolved counterfactuals are first-class |
| Compound causes | Supported |
| 5b joint components | Remain jointly modeled; never split downstream |
| Independently identifiable causes | Support single-cause and combined interventions |
| Interaction effects | Support only when explicitly declared by causal configuration |
| Uncertainty | Point estimate + uncertainty interval |
| Stage 7 confidence propagation | Yes |
| Stage 1 data-quality propagation | Yes |
| Weak hypotheses without quantitative basis | Do not estimate; return unavailable |
| Stage 7 abstention | Stage 8 does not run |
| Stage 9 output | Include business-impact interpretation |
| Architecture | Generic Stage 8 interface with only validated intervention mechanisms implemented in MVP |

---

# 3. The Critical Conceptual Separation

The most important rule in Stage 8 is:

```text
Stage 7 confidence
        ≠
5b contribution
        ≠
Stage 8 counterfactual
```

Example:

```text
Stage 7:
product_outage = LIKELY
```

does not mean:

```text
product_outage caused 80% of the decline
```

Likewise:

```text
Stage 5b:
product_outage contribution = 70%
```

does not automatically mean:

```text
without product_outage:
KPI = observed / 0.30
```

Stage 8 performs an independent counterfactual calculation.

The upstream outputs are evidence and constraints supplied to that engine.

---

# 4. High-Level Architecture

```text
                         Stage 7
                   Ranked hypotheses
                          │
                          ▼
                ┌─────────────────────┐
                │  Stage 8 Validator  │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Hypothesis Adapter  │
                │ + Intervention Spec │
                └──────────┬──────────┘
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
       Stage 5b        Stage 1–4      Causal Config
       attribution     observations   / equations
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                ┌─────────────────────┐
                │ Counterfactual      │
                │ Engine               │
                │                     │
                │ 1. Baseline         │
                │ 2. Intervention     │
                │ 3. Propagation      │
                │ 4. Interaction      │
                │ 5. Reconstruction   │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Uncertainty Engine  │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Impact Calculator   │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Output Validator    │
                └──────────┬──────────┘
                           │
                           ▼
                         Stage 9
```

---

# 5. What Stage 8 Must Not Do

Stage 8 must not:

- generate new causal hypotheses;
- rank hypotheses;
- override Stage 7;
- convert Stage 5a probabilities into contribution shares;
- split a `NON_IDENTIFIABLE_JOINT` Stage 5b component;
- invent an intervention mechanism that has not been declared;
- use a generic percentage such as “cause probability × revenue loss” as a counterfactual;
- claim causal certainty merely because a numerical estimate was produced;
- silently ignore Stage 1 data-quality limitations;
- estimate an impact for an `UNKNOWN` hypothesis without a quantitative basis;
- run when Stage 7 has abstained.

---

# 6. Input Contract

Stage 8 consumes a validated Stage 7 result plus the upstream analytical context required to construct the counterfactual.

Conceptually:

```python
Stage8Input(
    stage7_result,
    stage5a_result,
    stage5b_results,
    stage5c_results,
    canonical_observations,
    causal_context,
    data_quality_context
)
```

Not every hypothesis will require every upstream object.

---

# 7. Required Stage 7 Information

For each ranked hypothesis:

```text
hypothesis_id
member_causes
hypothesis_type
rank
confidence_bucket
confidence_reason_codes
supporting_evidence
contradicting_evidence
identifiability
borrowed
```

Stage 8 only attempts estimation for hypotheses satisfying its eligibility rules.

---

# 8. Stage 5b Information

When available:

```text
observed_deviation
contributions
share
unexplained_share
fit_quality
identifiability_verdict
```

Stage 5b is treated as quantitative attribution evidence.

It is not treated as the counterfactual itself.

For an identified cause:

```text
cause contribution
```

can constrain the plausible magnitude of the Stage 8 intervention.

For a joint component:

```text
product_outage + marketing_cut
NON_IDENTIFIABLE_JOINT
```

the entire joint component is passed into the intervention model as one mechanism.

---

# 9. Stage 5c Information

If Stage 5c supplied a borrowed signal:

```text
borrowed_percentile
analog_used
confidence_tier = BORROWED
```

Stage 8 preserves:

```text
borrowed = true
```

in its output.

A borrowed signal alone is not sufficient to justify a numerical counterfactual unless an independent quantitative intervention mechanism exists.

This is important:

```text
BORROWED evidence
    ≠
quantitative causal effect
```

---

# 10. Stage 1–4 Context

Stage 8 may need:

```text
canonical KPI timeline
expected baseline
daily observed values
daily residuals
affected dimensions
window boundaries
eligibility
imputation flags
provenance
```

Stage 8 should reuse existing Stage 1–4 data-access and baseline machinery.

It must not create a second definition of expected KPI behavior.

---

# 11. Stage 8 Eligibility Gate

Before attempting a counterfactual:

```text
Stage 7 abstained?
    → STOP

Hypothesis UNKNOWN?
    → STOP unless explicit quantitative mechanism exists

No intervention mechanism?
    → UNAVAILABLE

No quantitative basis?
    → UNAVAILABLE

Required KPI data insufficient?
    → UNAVAILABLE / DATA_LIMITED

5b joint component?
    → preserve joint intervention

Otherwise:
    → eligible
```

The key principle is:

> **A hypothesis can be rankable without being counterfactually estimable.**

For example:

```text
competitor_launch
confidence = POSSIBLE
```

may remain a valid Stage 7 hypothesis but produce:

```text
counterfactual_status = UNAVAILABLE
reason = NO_VALIDATED_INTERVENTION_MECHANISM
```

This is preferable to inventing a number.

---

# 12. Intervention Semantics

Stage 8 supports two intervention semantics.

## 12.1 Event-never-occurred

Question:

> What would the KPI trajectory have been if this event had never occurred?

Example:

```text
Observed:
revenue falls after product outage

Intervention:
remove product outage from the entire episode

Counterfactual:
revenue trajectory without outage
```

This is the primary counterfactual for causal impact reporting.

---

## 12.2 Event-removal-from-time-t

Question:

> What would have happened if the event had been removed beginning at a specified intervention time?

Example:

```text
Outage:
Day 20 → Day 30

Intervention:
Day 25

Counterfactual:
Days 0–24 = observed world
Days 25+ = no-outage world
```

This supports operational questions such as:

```text
"What if we had fixed the outage on Day 25?"
```

Both intervention types use the same engine interface.

---

# 13. Intervention Specification

Every counterfactual request becomes an explicit `InterventionSpec`.

```python
@dataclass
class InterventionSpec:
    hypothesis_id: str

    member_causes: list[str]

    mode: str
    # "EVENT_NEVER_OCCURRED"
    # "REMOVE_FROM_TIME"

    intervention_day_offset: int | None

    mechanism_ids: list[str]

    interaction_policy: str
    # "NONE"
    # "DECLARED_ONLY"

    joint: bool

    source_basis: list[str]
```

No free-form causal instruction is passed into the numerical engine.

---

# 14. Mechanism Registry

The engine is generic, but the mechanisms are explicitly registered.

Example:

```python
INTERVENTION_MECHANISMS = {
    "product_outage": ProductOutageMechanism,
    "marketing_cut": MarketingCutMechanism,
    "competitor_launch": CompetitorLaunchMechanism,
    "inventory_shortage": InventoryShortageMechanism,
}
```

Only mechanisms present in this registry can be simulated.

If a hypothesis contains:

```text
pricing_change
```

but there is no validated pricing mechanism:

```text
NO_VALIDATED_INTERVENTION_MECHANISM
```

The system refuses the estimate.

This is the central protection against fake generality.

---

# 15. Generic Engine Interface

```python
class CounterfactualEngine:

    def estimate(
        self,
        observed,
        baseline,
        intervention,
        context
    ) -> CounterfactualTrajectory:
        ...
```

Each mechanism implements the same contract:

```python
class InterventionMechanism:

    def validate(self, context) -> ValidationResult:
        ...

    def apply(
        self,
        observed,
        baseline,
        intervention,
        context
    ) -> CounterfactualTrajectory:
        ...
```

The engine therefore remains generic while the MVP remains deliberately narrow.

---

# 16. Counterfactual Trajectory

The first-class internal representation is time-resolved.

```python
@dataclass
class CounterfactualPoint:
    day_offset: int

    observed_value: float
    baseline_value: float
    counterfactual_value: float

    estimated_cause_impact: float

    data_confidence: str
```

Example:

```text
Day    Observed   Baseline   Counterfactual   Impact
20       950       1000          1000           50
21       900       1000          1000          100
22       850       1000          1000          150
23       870       1000          1000          130
```

This is retained even when the public output also provides an aggregate.

---

# 17. Why Time Resolution Is Required

A single aggregate hides the most important behavior.

Suppose:

```text
Observed impact = ₹2M
```

That does not tell us whether:

```text
₹2M accumulated gradually
```

or:

```text
₹2M happened in two days
```

or:

```text
impact started immediately
then recovered
```

The trajectory allows Stage 9 to communicate the actual business impact pattern.

---

# 18. Baseline Construction

Stage 8 reuses the upstream baseline definition.

Conceptually:

```text
Expected KPI trajectory
```

comes from Stage 2's baseline machinery.

Stage 8 does not redefine:

```text
normal
expected
seasonal
trend
```

This prevents baseline drift across stages.

---

# 19. Baseline vs Counterfactual

They are deliberately different.

```text
Baseline:
"What normally would have happened?"

Counterfactual:
"What would have happened under a specified intervention?"
```

For some simple events they may be nearly identical.

For others they may not.

Example:

```text
baseline revenue = 1000/day

without outage:
950/day → 970/day → 1000/day
```

because the counterfactual can retain other contemporaneous conditions rather than blindly replacing the entire trajectory with the baseline.

---

# 20. Counterfactual Reconstruction Strategy

The MVP uses a **hybrid reconstruction strategy**.

Priority order:

```text
1. Explicit causal mechanism
2. Stage 5b quantitative contribution
3. Existing KPI structural equations
4. Upstream baseline / unaffected trajectory
5. Residual uncertainty
```

This is not a weighted equation.

It is a decision hierarchy.

The strongest available validated information is used first.

---

# 21. Mechanism-First Principle

If a validated mechanism exists:

```text
product_outage
```

Stage 8 should simulate the effect removal according to that mechanism.

It should not simply do:

```text
counterfactual =
observed + 5b_contribution
```

unless the mechanism explicitly defines that contribution as the appropriate intervention effect.

---

# 22. 5b Contribution as a Constraint

5b is valuable because it provides a quantitative decomposition of the observed movement.

Example:

```text
Observed revenue deviation = -₹3M

5b:
outage = ₹2.1M
marketing cut = ₹0.9M
```

Stage 8 can use:

```text
₹2.1M
```

as evidence for the scale of the outage mechanism.

But it still asks:

```text
How does that effect behave over time?
What happens after the intervention?
Does the causal mechanism imply recovery?
Is another cause still active?
```

Therefore:

```text
5b → quantitative constraint

Stage 8 → counterfactual trajectory
```

---

# 23. Single-Cause Counterfactual

Example:

```text
H1:
product_outage
```

Stage 8 constructs:

```text
Observed trajectory
        ↓
identify outage intervention
        ↓
remove outage effect
        ↓
propagate remaining system
        ↓
counterfactual trajectory
```

Aggregate:

```text
observed revenue = ₹9.0M
counterfactual revenue = ₹11.2M

estimated outage impact = ₹2.2M
```

---

# 24. Compound Counterfactual

Example:

```text
H1:
product_outage + marketing_cut
```

Stage 8 applies the two mechanisms jointly.

If the interaction is declared:

```text
outage + marketing cut
        ↓
joint mechanism
```

Otherwise:

```text
outage mechanism
+
marketing mechanism
```

is permitted only where the combination policy explicitly allows it.

---

# 25. Joint 5b Component

If Stage 5b says:

```text
product_outage + marketing_cut
NON_IDENTIFIABLE_JOINT
```

Stage 8 must produce:

```text
joint counterfactual
```

not:

```text
outage counterfactual
marketing counterfactual
```

Example:

```text
Observed revenue:
₹9M

Counterfactual without the joint mechanism:
₹11.5M

Combined estimated impact:
₹2.5M
```

No member-level decomposition is invented.

---

# 26. Independently Identifiable Causes

When two causes are independently identifiable:

```text
product_outage
marketing_cut
```

Stage 8 can produce three intervention scenarios:

```text
1. Remove outage
2. Remove marketing cut
3. Remove both
```

This is important because:

```text
impact(outage)
+
impact(marketing)
```

does not necessarily equal:

```text
impact(remove both)
```

when interaction exists.

---

# 27. Interaction Effects

Interaction modeling is allowed only when explicitly declared.

Example:

```yaml
interaction:
  causes:
    - product_outage
    - marketing_cut
  mechanism: multiplicative
```

Then the engine may calculate:

```text
effect(outage)
effect(marketing_cut)
effect(both)
interaction_effect
```

If no interaction is declared:

```text
interaction = NOT_MODELED
```

The engine does not infer an interaction merely because the observed effects appear non-additive.

---

# 28. Interaction Effect Output

For independently identifiable causes:

```python
@dataclass
class InteractionImpact:
    member_causes: list[str]

    individual_impact: dict[str, float]

    combined_impact: float

    interaction_impact: float

    interaction_status: str
```

Where:

```text
interaction_impact =
combined_effect
-
sum(individual_effects)
```

only when the relevant intervention mechanism supports that interpretation.

---

# 29. Time-Resolved Intervention

For:

```text
EVENT_NEVER_OCCURRED
```

the intervention applies from event onset.

For:

```text
REMOVE_FROM_TIME
```

the intervention begins at the requested day.

Example:

```text
event onset = day 20
fix = day 25
```

Then:

```text
day < 25
    observed world

day >= 25
    counterfactual no-event world
```

This distinction is preserved in output.

---

# 30. Recovery Modeling

A major source of fake counterfactuals is assuming immediate return to baseline.

Stage 8 therefore treats recovery as a mechanism property.

Possible declared modes:

```text
IMMEDIATE
LINEAR
OBSERVED_RECOVERY_PROFILE
NO_RECOVERY
```

MVP should implement only mechanisms justified by the simulator.

If the simulator says an outage instantly restores KPI behavior:

```text
IMMEDIATE
```

If it models gradual recovery:

```text
OBSERVED_RECOVERY_PROFILE
```

The engine does not invent recovery dynamics.

---

# 31. Causal Graph Propagation

Where the business model contains structural equations:

```text
Traffic
   ↓
Conversion
   ↓
Orders
   ↓
Revenue
```

an intervention may propagate through the graph.

Example:

```text
remove competitor launch
        ↓
traffic counterfactual
        ↓
orders counterfactual
        ↓
revenue counterfactual
```

This is preferable to independently estimating revenue without respecting the known KPI structure.

---

# 32. Structural Equations

Only declared equations are used.

Example:

```text
Revenue = Orders × AOV
```

Then:

```text
Revenue_cf =
Orders_cf × AOV_cf
```

If AOV is unaffected by the intervention:

```text
AOV_cf = AOV_observed
```

If an intervention mechanism explicitly affects AOV:

```text
AOV_cf = mechanism-adjusted AOV
```

The engine never assumes an equation merely because two KPIs happen to correlate.

---

# 33. Unaffected Variables

A counterfactual needs an explicit treatment for variables not affected by the intervention.

Possible statuses:

```text
HELD_CONSTANT
FOLLOW_BASELINE
FOLLOW_OBSERVED
MECHANISM_ADJUSTED
UNKNOWN
```

Example:

```yaml
product_outage:
  revenue:
    mechanism_adjusted
  traffic:
    follow_observed
  aov:
    held_constant
```

This makes the counterfactual assumptions auditable.

---

# 34. Uncertainty Model

Every numerical counterfactual includes:

```text
point estimate
lower bound
upper bound
confidence / data-quality tier
```

Example:

```text
Counterfactual revenue:
₹11.2M

Interval:
₹10.7M – ₹11.8M
```

The interval represents uncertainty in the estimation, not a probability that the hypothesis is true.

---

# 35. Sources of Counterfactual Uncertainty

The uncertainty interval may incorporate:

```text
Stage 5b fit uncertainty
baseline residual variability
Stage 1 data-quality limitations
mechanism uncertainty
interaction uncertainty
hypothesis confidence
```

These are tracked separately internally.

---

# 36. Confidence Propagation

Stage 7 confidence affects whether the estimate is allowed and how uncertainty is communicated.

Example policy:

```text
KNOWN
    → normal uncertainty

LIKELY
    → normal-to-expanded uncertainty

POSSIBLE
    → expanded uncertainty

UNKNOWN
    → no estimate
```

The system must not turn:

```text
LIKELY
```

into:

```text
90% causal probability
```

unless a future calibrated probabilistic model explicitly supports that interpretation.

---

# 37. Data-Quality Propagation

Stage 1 uncertainty is carried into Stage 8.

Example:

```text
Revenue:
HIGH quality

Orders:
MEDIUM quality

Traffic:
HEAVILY_IMPUTED
```

If revenue counterfactual depends materially on traffic:

```text
data_confidence = MEDIUM
```

and the uncertainty interval expands accordingly.

The exact numeric interval policy must remain mechanism-specific and empirically testable.

---

# 38. Interval Construction

The MVP should use a transparent uncertainty propagation mechanism rather than arbitrary confidence percentages.

For each model component:

```text
central estimate
+
estimated error contribution
```

are propagated through the mechanism.

Where Stage 5b supplies a validated residual / fit-quality signal, that becomes one uncertainty input.

Where no reliable uncertainty estimate exists:

```text
uncertainty_status = LIMITED
```

and the output must not pretend the interval is statistically calibrated.

---

# 39. Hypothesis Eligibility vs Confidence

These are separate.

Example:

```text
Hypothesis:
competitor_launch

Stage 7:
POSSIBLE

Mechanism:
validated

Data:
good

→ Stage 8 may estimate
```

Another:

```text
Hypothesis:
marketing_cut

Stage 7:
LIKELY

Mechanism:
not implemented

→ Stage 8 cannot estimate
```

The second is not a failure of Stage 7.

It is an explicit Stage 8 capability boundary.

---

# 40. Stage 7 Abstention

If:

```text
stage7_result.abstained == true
```

Stage 8 does not run.

There is no generic:

```text
"something caused ₹X"
```

counterfactual.

The system should preserve the unresolved state.

This prevents the counterfactual engine from bypassing the evidence-resolution gate.

---

# 41. Every Ranked Hypothesis

Stage 8 processes every ranked hypothesis that is:

```text
not UNKNOWN
+
counterfactually estimable
```

Example:

```text
Stage 7:

1. outage — LIKELY
2. competitor — POSSIBLE
3. inventory — POSSIBLE
4. marketing — UNKNOWN
```

Stage 8:

```text
outage
→ estimate

competitor
→ estimate

inventory
→ estimate

marketing
→ unavailable
```

This preserves Stage 7's ranked hypothesis set without forcing a numerical estimate where one cannot be justified.

---

# 42. Aggregate Impact

For each hypothesis:

```text
impact = counterfactual - observed
```

for a beneficial-removal intervention where the counterfactual is higher.

For KPI directionality, the engine must use the KPI's declared orientation rather than assume “higher is always better.”

Example:

```text
Revenue:
impact = counterfactual - observed
```

For a cost KPI:

```text
impact = observed - counterfactual
```

The output also carries:

```text
impact_direction
```

so the sign is never interpreted without context.

---

# 43. Business Impact Interpretation

Stage 8 produces business-impact fields, not narrative prose.

Example:

```json
{
  "observed_value": 9000000,
  "counterfactual_value": 11200000,
  "estimated_impact": 2200000,
  "impact_pct_of_observed": 24.4,
  "impact_pct_of_counterfactual": 19.6,
  "impact_unit": "USD"
}
```

These fields are what Stage 9 can turn into executive language.

---

# 44. Recovered Potential

Where meaningful:

```text
recovered_potential =
counterfactual - observed
```

Example:

```text
₹2.2M estimated recoverable revenue
```

This is not a forecast of actual recovery.

It means:

> Estimated gap between observed outcome and the specified counterfactual.

---

# 45. Counterfactual Scenarios

Each estimate explicitly identifies its scenario.

```text
scenario:
  EVENT_NEVER_OCCURRED
```

or:

```text
scenario:
  REMOVE_FROM_TIME
  intervention_day = 25
```

This prevents the UI from displaying a counterfactual number without explaining what intervention it represents.

---

# 46. Output Contract

```python
@dataclass
class CounterfactualPoint:
    day_offset: int

    observed_value: float
    baseline_value: float
    counterfactual_value: float

    estimated_impact: float

    point_lower: float | None
    point_upper: float | None

    data_confidence: str


@dataclass
class CounterfactualImpact:
    hypothesis_id: str
    member_causes: list[str]
    hypothesis_type: str

    scenario: str
    intervention_day_offset: int | None

    observed_aggregate: float
    counterfactual_aggregate: float
    estimated_impact: float

    impact_unit: str
    impact_direction: str

    impact_lower: float | None
    impact_upper: float | None

    trajectory: list[CounterfactualPoint]

    stage7_confidence: str

    data_confidence: str
    uncertainty_status: str

    stage5b_basis: dict | None

    identifiability: str
    borrowed: bool

    interaction: dict | None

    estimation_status: str
    estimation_reason_codes: list[str]


@dataclass
class Stage8Result:
    cluster_id: str
    window_start_day_offset: int
    window_end_day_offset: int

    estimates: list[CounterfactualImpact]

    skipped_hypotheses: list[dict]

    abstained_upstream: bool

    engine_version: str
```

---

# 47. Estimation Status

Allowed states:

```text
ESTIMATED
UNAVAILABLE
DATA_LIMITED
MECHANISM_UNAVAILABLE
INVALID_INPUT
```

`UNAVAILABLE` is not an error when the system intentionally refuses an unsupported counterfactual.

---

# 48. Reason Codes

Examples:

```text
VALIDATED_INTERVENTION_MECHANISM
STAGE5B_QUANTITATIVE_CONSTRAINT
STRUCTURAL_KPI_PROPAGATION
BASELINE_RECONSTRUCTION

NO_VALIDATED_INTERVENTION_MECHANISM
INSUFFICIENT_DATA
STAGE7_UNKNOWN
STAGE7_ABSTAINED
NON_IDENTIFIABLE_JOINT
BORROWED_ONLY
INTERACTION_NOT_DECLARED
UNCERTAINTY_UNCALIBRATED
```

No generated explanation is required in the numerical engine.

---

# 49. Example — Single Cause

Input:

```text
Observed revenue:
₹9.0M

Stage 7:
product_outage = LIKELY

Stage 5b:
outage contribution = ₹2.1M
```

Stage 8:

```text
Scenario:
EVENT_NEVER_OCCURRED

Counterfactual:
₹11.2M

Estimated impact:
₹2.2M

Interval:
₹10.7M–₹11.8M
```

Trajectory:

```text
Day 20:
Observed        ₹950k
Counterfactual ₹1.00M
Impact          ₹50k

Day 21:
Observed        ₹900k
Counterfactual ₹1.00M
Impact         ₹100k

...
```

---

# 50. Example — Two Identifiable Causes

Stage 7:

```text
product_outage = LIKELY
marketing_cut = POSSIBLE
```

Stage 5b:

```text
outage:
₹1.5M

marketing:
₹0.7M
```

Stage 8 may return:

```text
Without outage:
₹10.5M

Without marketing cut:
₹9.7M

Without both:
₹11.3M
```

If:

```text
impact(both)
≠
impact(outage) + impact(marketing)
```

then the difference is treated as an interaction only if the mechanism explicitly permits it.

---

# 51. Example — Non-Identifiable Joint Cause

Stage 5b:

```text
product_outage + marketing_cut
NON_IDENTIFIABLE_JOINT
```

Stage 7:

```text
compound hypothesis = LIKELY
```

Stage 8:

```text
Without joint mechanism:
₹11.4M

Observed:
₹9.0M

Combined impact:
₹2.4M
```

It must never output:

```text
outage = ₹1.7M
marketing = ₹0.7M
```

because the upstream system explicitly refused that split.

---

# 52. Example — Unsupported Hypothesis

Stage 7:

```text
competitor_launch = POSSIBLE
```

but no validated intervention mechanism exists.

Stage 8:

```json
{
  "hypothesis_id": "H3",
  "estimation_status": "MECHANISM_UNAVAILABLE",
  "estimation_reason_codes": [
    "NO_VALIDATED_INTERVENTION_MECHANISM"
  ]
}
```

No fabricated number.

---

# 53. Example — Stage 7 Abstention

Stage 7:

```text
abstained = true
```

Stage 8:

```text
DO NOT RUN
```

No counterfactual estimates are produced.

This is an explicit pipeline state.

---

# 54. Example — Data-Limited Estimate

Suppose:

```text
Stage 7:
product_outage = LIKELY

Mechanism:
available

Traffic:
heavily imputed
```

Stage 8 can still estimate if the mechanism remains mathematically usable.

Output:

```text
estimated_impact:
₹2.1M

impact_interval:
₹1.2M–₹3.0M

data_confidence:
LOW

uncertainty_status:
DATA_LIMITED
```

The uncertainty is propagated rather than hidden.

---

# 55. Module Architecture

Recommended implementation tree:

```text
pipeline/stage08_counterfactual_impact/
│
├── README.md
├── requirements.txt
│
├── models.py
├── config.py
│
├── input_validator.py
├── hypothesis_adapter.py
├── intervention_spec.py
│
├── engine/
│   ├── __init__.py
│   ├── base.py
│   ├── engine.py
│   ├── mechanism_registry.py
│   ├── propagation.py
│   ├── reconstruction.py
│   └── recovery.py
│
├── mechanisms/
│   ├── __init__.py
│   ├── product_outage.py
│   ├── marketing_cut.py
│   ├── competitor_launch.py
│   └── inventory_shortage.py
│
├── structural/
│   ├── __init__.py
│   ├── kpi_graph.py
│   ├── equations.py
│   └── propagation_rules.py
│
├── uncertainty/
│   ├── __init__.py
│   ├── baseline_uncertainty.py
│   ├── attribution_uncertainty.py
│   ├── data_quality.py
│   └── interval_propagation.py
│
├── impact/
│   ├── aggregate.py
│   ├── direction.py
│   └── business_impact.py
│
├── stage5b_bridge.py
├── stage1_stage2_bridge.py
├── stage7_bridge.py
│
├── output_schema.py
├── stage8.py
└── test_stage8.py
```

---

# 56. Responsibilities of Major Modules

## `input_validator.py`

Validates:

```text
cluster consistency
window consistency
hypothesis schema
identifiability constraints
confidence states
upstream provenance
```

---

## `hypothesis_adapter.py`

Converts Stage 7 hypotheses into an internal form:

```text
single cause
compound cause
joint cause
```

It does not generate hypotheses.

---

## `intervention_spec.py`

Creates the explicit intervention definition.

Example:

```text
product_outage
EVENT_NEVER_OCCURRED
```

or:

```text
product_outage
REMOVE_FROM_TIME
day 25
```

---

## `engine/base.py`

Defines the generic mechanism interface.

---

## `engine/engine.py`

Runs:

```text
validation
→ intervention
→ reconstruction
→ propagation
→ uncertainty
→ impact
```

---

## `mechanisms/*`

Contain only validated, project-supported causal mechanisms.

---

## `structural/*`

Reuses declared KPI relationships and equations.

No correlation-based causal discovery occurs here.

---

## `uncertainty/*`

Combines uncertainty from:

```text
baseline
5b
data quality
mechanism
interaction
```

---

## `impact/*`

Calculates:

```text
aggregate impact
percentage impact
recovered potential
direction
```

---

# 57. Build Order

## Step 1 — Finalize causal mechanism registry

Declare which hypotheses actually have executable counterfactual mechanisms.

This is blocking.

Do not pretend every Stage 7 cause can automatically be simulated.

---

## Step 2 — Define intervention semantics

Implement:

```text
EVENT_NEVER_OCCURRED
REMOVE_FROM_TIME
```

with explicit day-offset handling.

---

## Step 3 — Build internal models

Implement:

```text
InterventionSpec
CounterfactualPoint
CounterfactualImpact
Stage8Result
```

---

## Step 4 — Build Stage 7 adapter

Convert Stage 7 output without changing its meaning.

---

## Step 5 — Build baseline / canonical-data bridge

Reuse Stage 1/2 machinery.

Do not implement a second baseline model.

---

## Step 6 — Build first mechanism

Implement the most defensible simulator mechanism first.

Recommended:

```text
product_outage
```

because it has a clear event interval and strong relevance to the project's 5b confounding example.

---

## Step 7 — Build structural propagation

Implement only declared KPI relationships/equations that actually exist in the simulator.

---

## Step 8 — Add Stage 5b constraint integration

Use:

```text
contribution
fit_quality
unexplained_share
identifiability
```

as quantitative context.

Do not convert 5b shares directly into counterfactuals.

---

## Step 9 — Add interaction handling

Only implement configured interactions.

---

## Step 10 — Build uncertainty propagation

Start with transparent interval propagation.

Clearly label uncalibrated intervals.

---

## Step 11 — Add aggregate impact calculations

Produce:

```text
observed
counterfactual
impact
impact %
recovered potential
```

---

## Step 12 — Build output validation

Enforce:

```text
no joint split
no estimate without mechanism
no estimate after Stage 7 abstention
no UNKNOWN hypothesis estimate
trajectory matches aggregate
interval contains point estimate
```

---

## Step 13 — Build end-to-end runner

```python
run_stage8(
    stage7_result,
    stage5a_result,
    stage5b_results,
    stage5c_results,
    context
)
```

---

# 58. Test Architecture

Stage 8 needs much stronger testing than a simple "does it run" test.

The tests should compare the engine against the simulator's known causal mathematics.

---

# 59. Unit Test — No-Event Counterfactual

Construct a synthetic episode:

```text
baseline = 100
outage effect = -20
observed = 80
```

Expected:

```text
counterfactual = 100
impact = 20
```

---

# 60. Unit Test — Time-Resolved Counterfactual

Synthetic:

```text
Day 1–4:
no outage

Day 5–7:
outage
```

Expected:

```text
Days 1–4:
counterfactual == observed

Days 5–7:
counterfactual removes outage effect
```

---

# 61. Unit Test — Intervention From Time

Event:

```text
Day 5–10
```

Intervention:

```text
Day 8
```

Expected:

```text
Days <8:
observed world

Days >=8:
no-event world
```

---

# 62. Unit Test — Joint Cause

Input:

```text
product_outage + marketing_cut
NON_IDENTIFIABLE_JOINT
```

Expected:

```text
one counterfactual
one combined impact
```

Assert:

```text
no member-level estimates
```

---

# 63. Unit Test — Independent Causes

Input:

```text
outage
marketing_cut
```

Expected:

```text
outage-only counterfactual
marketing-only counterfactual
both counterfactual
```

No automatic interaction unless declared.

---

# 64. Unit Test — Interaction

Create a simulator-compatible synthetic mechanism with known interaction:

```text
effect_both = effect_a + effect_b + interaction
```

Assert Stage 8 recovers the configured interaction.

---

# 65. Unit Test — Unsupported Mechanism

Hypothesis:

```text
pricing_change
```

No registered mechanism.

Expected:

```text
MECHANISM_UNAVAILABLE
```

No numeric estimate.

---

# 66. Unit Test — Stage 7 Abstention

Input:

```text
abstained = true
```

Expected:

```text
Stage 8 does not execute estimation.
```

---

# 67. Unit Test — Unknown Hypothesis

Input:

```text
confidence = UNKNOWN
```

Expected:

```text
UNAVAILABLE
```

unless an explicitly configured exceptional quantitative mechanism exists.

---

# 68. Unit Test — 5b Joint Preservation

Feed:

```text
NON_IDENTIFIABLE_JOINT
```

through the complete pipeline.

Assert:

```text
member_causes remain unchanged
identifiability remains NON_IDENTIFIABLE_JOINT
no member-level impact exists
```

---

# 69. Unit Test — Stage 5a Probability Is Not Contribution

Construct:

```text
Stage 5a:
outage probability = 0.8

Stage 5b:
outage share = 0.4
```

Assert Stage 8 does not calculate:

```text
0.8 × observed_loss
```

as the impact.

This test is important enough to be a permanent regression test.

---

# 70. Unit Test — Stage 1 Data Quality

Create:

```text
traffic = heavily imputed
```

and ensure:

```text
data_confidence
```

is downgraded and uncertainty is widened / marked limited according to configured propagation rules.

---

# 71. Reconciliation Tests

For every time-resolved estimate:

```text
aggregate(counterfactual trajectory)
```

must equal:

```text
counterfactual_aggregate
```

within numerical tolerance.

Likewise:

```text
aggregate(estimated impact trajectory)
```

must reconcile with:

```text
estimated_impact
```

---

# 72. Ground-Truth Evaluation

The simulator is especially valuable here.

Where the generator knows:

```text
event
effect_fraction
event window
```

Stage 8 can compare:

```text
true no-event trajectory
```

against:

```text
estimated counterfactual trajectory
```

This should be the primary quantitative evaluation.

---

# 73. Metrics

At minimum:

### Counterfactual MAE

```text
MAE =
mean(
    |estimated_counterfactual - true_counterfactual|
)
```

---

### Impact MAE

```text
mean(
    |estimated_impact - true_impact|
)
```

---

### Aggregate impact error

Compare:

```text
estimated window impact
```

against:

```text
generator ground-truth impact
```

---

### Trajectory error

Measure time-resolved error across the event window.

This matters because a model can get the total right while getting the temporal shape completely wrong.

---

# 74. Coverage / Abstention Metric

Because refusing unsupported estimates is intentional, evaluate:

```text
valid estimates / attempted estimates
```

and:

```text
unsupported cases correctly abstained
```

The system should not be rewarded for estimating everything.

---

# 75. Joint-Cause Evaluation

For 5b `NON_IDENTIFIABLE_JOINT` cases:

Do not evaluate member-level attribution.

Evaluate:

```text
joint counterfactual error
```

against the simulator's combined true effect.

This respects the identifiability contract.

---

# 76. Scenario Evaluation

Evaluate separately:

```text
EVENT_NEVER_OCCURRED
```

and:

```text
REMOVE_FROM_TIME
```

because these are different interventions.

---

# 77. Golden End-to-End Example

Use a known outage case:

```text
Event:
product_outage

Window:
Day 20–30

Observed:
revenue down

Stage 7:
product_outage = LIKELY

Stage 5b:
outage contribution available
```

Expected Stage 8 output:

```text
observed trajectory
counterfactual trajectory
impact trajectory
aggregate impact
uncertainty interval
```

The test should compare the result against the generator's actual no-outage world.

---

# 78. Failure Modes

## Failure 1 — Probability-as-impact

Bad:

```text
Stage 5a = 0.7
Observed loss = ₹3M

Impact = ₹2.1M
```

Fix:

```text
use an intervention mechanism
```

---

## Failure 2 — Contribution-as-counterfactual

Bad:

```text
5b contribution = ₹2M
counterfactual = observed + ₹2M
```

without validating the intervention semantics.

Fix:

```text
5b = quantitative constraint
Stage 8 = independent counterfactual reconstruction
```

---

## Failure 3 — Fake member split

Bad:

```text
joint impact = ₹3M

outage = ₹1.7M
marketing = ₹1.3M
```

when 5b declared non-identifiability.

Fix:

```text
joint impact only
```

---

## Failure 4 — Immediate baseline restoration

Bad:

```text
event removed
→ KPI instantly equals baseline
```

when the mechanism actually has recovery dynamics.

Fix:

```text
mechanism-specific recovery
```

---

## Failure 5 — Uncertainty disappears

Bad:

```text
₹2.2M
```

with no indication that traffic was heavily imputed and the hypothesis was only POSSIBLE.

Fix:

```text
interval + data confidence + Stage 7 confidence
```

---

## Failure 6 — Unsupported cause gets a number

Bad:

```text
competitor_launch
→ estimated impact ₹1.4M
```

with no validated mechanism.

Fix:

```text
MECHANISM_UNAVAILABLE
```

---

## Failure 7 — Stage 7 abstention is bypassed

Bad:

```text
Stage 7:
ABSTAIN

Stage 8:
generic counterfactual
```

Fix:

```text
Stage 8 does not run.
```

---

# 79. Configuration

The configuration should declare only validated business/scenario knowledge.

Example:

```yaml
engine:
  version: "stage8-v1"

eligibility:
  minimum_confidence:
    - KNOWN
    - LIKELY
    - POSSIBLE

  allow_unknown: false

interventions:
  product_outage:
    mechanism: product_outage_v1
    recovery: immediate

  marketing_cut:
    mechanism: marketing_cut_v1

  competitor_launch:
    mechanism: competitor_launch_v1

  inventory_shortage:
    mechanism: inventory_shortage_v1

interaction:
  policy: DECLARED_ONLY

uncertainty:
  emit_intervals: true
```

The exact values should be finalized against the simulator before implementation.

---

# 80. API Boundary

The primary callable should be:

```python
def run_stage8(
    cur,
    episode_id,
    stage7_result,
    stage5a_result,
    stage5b_results,
    stage5c_results
) -> Stage8Result:
    ...
```

The implementation should also expose a pure computational interface so unit tests do not require a database:

```python
def estimate_counterfactual(
    observed,
    baseline,
    intervention_spec,
    causal_context
) -> CounterfactualImpact:
    ...
```

Database access remains at the bridge/input layer.

---

# 81. CLI

The CLI should support:

```bash
python -m pipeline.stage08_counterfactual_impact.stage8 \
    --episode-id 42
```

The CLI re-derives the required upstream pipeline outputs exactly as earlier stages do.

Optional future mode:

```bash
--hypothesis-id H1
```

for debugging a single estimate.

The default should process every eligible ranked hypothesis.

---

# 82. Logging

The numerical engine should log structured events such as:

```text
STAGE8_INPUT_VALIDATED
HYPOTHESIS_ELIGIBLE
INTERVENTION_SELECTED
COUNTERFACTUAL_ESTIMATED
UNCERTAINTY_PROPAGATED
HYPOTHESIS_SKIPPED
MECHANISM_UNAVAILABLE
JOINT_COMPONENT_PRESERVED
```

No narrative explanation needs to be generated here.

---

# 83. Output to Stage 9

Stage 9 should receive enough information to say:

```text
Observed revenue:
₹9.0M

Estimated revenue without product outage:
₹11.2M

Estimated impact:
₹2.2M

Estimated range:
₹1.7M–₹2.8M

Confidence:
LIKELY

Data confidence:
MEDIUM

Scenario:
event never occurred
```

For compound cases:

```text
Joint mechanism:
product outage + marketing cut

Estimated combined impact:
₹2.4M

Member split:
not identifiable
```

This is the proper input for action prioritization.

---

# 84. Stage 8 → Stage 9 Boundary

Stage 8 owns:

```text
what would have happened
estimated impact
uncertainty
scenario
quantitative business significance
```

Stage 9 owns:

```text
what should we do
which action is worth taking
trade-offs
priority
```

Stage 8 should not recommend:

```text
"Fix the outage immediately"
```

It should provide:

```text
"Estimated recoverable revenue under outage removal:
₹2.2M"
```

Stage 9 decides what action follows.

---

# 85. Final Architecture

The complete conceptual pipeline becomes:

```text
Stage 7
  │
  │ ranked hypotheses
  ▼
Stage 8 Eligibility
  │
  ├── Stage 7 abstained → STOP
  ├── unsupported hypothesis → UNAVAILABLE
  └── eligible
          │
          ▼
   Intervention Spec
          │
          ▼
   Independent Counterfactual Engine
          │
          ├── validated mechanism
          ├── baseline
          ├── 5b quantitative constraint
          ├── KPI structural equations
          ├── interaction if declared
          └── recovery dynamics
          │
          ▼
   Time-Resolved Counterfactual
          │
          ▼
   Uncertainty Propagation
          │
          ▼
   Business Impact Calculation
          │
          ▼
   Validated Stage 8 Result
          │
          ▼
       Stage 9
```

---

# 86. Final Design Position

Stage 8 should be treated as an **independent counterfactual estimation engine**, not a mathematical formatting layer around Stage 5b.

The critical chain is:

```text
Stage 5a
candidate probability
        ↓
Stage 5b
movement attribution
        ↓
Stage 6
observational evidence
        ↓
Stage 7
hypothesis resolution
        ↓
Stage 8
counterfactual intervention
        ↓
estimated impact
```

Each stage answers a different question.

The defining rule for Stage 8 is:

> **Never produce a counterfactual number unless the system can state what intervention produced that number and which validated mechanism connects the intervention to the KPI trajectory.**

This gives the project a clean distinction between:

```text
"We think this happened."
```

and:

```text
"If this mechanism had not occurred,
our model estimates the KPI would have been X instead of Y."
```

That distinction is what keeps the counterfactual layer defensible rather than turning it into a polished hallucination.
